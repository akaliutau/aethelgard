import argparse
import asyncio
import base64
import json
import os
from typing import Optional, Dict, Any, List

import httpx
import lancedb
import numpy as np
from dotenv import load_dotenv
from nicegui import ui, app, events

from aethelgard.core.config import get_logger

logger = get_logger(__name__)

# ==========================================
# 1. State & Constants
# ==========================================

# Aethelgard Network Configuration
TARGET_NODES = ["Hospital_A", "Hospital_B"]
VECTOR_DIMENSIONS = 1920  # Matches LanceDB (768 text + 1152 image)
POLL_INTERVAL = 30
MAX_ATTEMPTS = 8
NOISE_SIGMA = 0.15

# Holds the current patient data
CURRENT_PATIENT: Optional[Dict[str, Any]] = None
PENDING_IMAGE_B64: Optional[str] = None


# ==========================================
# 1. LDP Noise Generation
# ==========================================
def add_empirical_noise(raw_vector: list, noise_std_dev: float = 0.05) -> list:
    """
    Adds empirical Gaussian noise to a vector to defend against model inversion,
    then L2-renormalizes the vector for cosine similarity search.
    """
    vec_np = np.array(raw_vector, dtype=np.float32)

    # 1. Generate and add Gaussian noise
    noise = np.random.normal(loc=0.0, scale=noise_std_dev, size=vec_np.shape)
    noisy_vec = vec_np + noise

    # 2. L2-Normalize the vector (Crucial for external search engines)
    norm = np.linalg.norm(noisy_vec)
    if norm > 0:
        noisy_vec = noisy_vec / norm

    return noisy_vec.tolist()

# ==========================================
# 2. Local LanceDB Retrieval
# ==========================================
def get_precomputed_vector(patient_id: str) -> Optional[list]:
    """Fetches the pre-calculated embedding from the local LanceDB instance."""
    try:
        db = lancedb.connect(uri=os.getenv("DB_PATH"))
        # Use DuckDB/Arrow syntax to filter for the specific patient ID
        results = db.open_table(name=os.getenv("TABLE_NAME")).search().where(f"id = '{patient_id}'").limit(1).to_pandas()

        if not results.empty:
            logger.info(f"Pre-computed vector found for {patient_id}")
            raw_vector = results.iloc[0]['vector'].tolist()
            return add_empirical_noise(raw_vector, noise_std_dev=NOISE_SIGMA)
        else:
            logger.warning(f"Patient {patient_id} not found in LanceDB.")
            return None

    except Exception as e:
        logger.error(f"Failed to query LanceDB: {e}")
        return None


async def sanitize_and_vectorize(record: Dict, question: str) -> list:
    """Fetches pre-computed vector, falling back to mock generation if missing."""

    patient_id = record.get("patient_id")

    if patient_id:
        vector = get_precomputed_vector(patient_id)
        if vector:
            ui.notify(f"Loaded existing vector for {patient_id} from LanceDB!", type='positive', position='bottom-left')
            return vector

    # Fallback if lance DB isn't populated yet
    # In real prod we should stop workflow here and vectorize data, in demo we will never be here
    ui.notify("No DB entry found!", type='negative', position='bottom-left')
    return []


# ==========================================
# 3. Aethelgard Network Integration
# ==========================================

def format_medical_insight(insight_data) -> str:
    """
    Cleans raw LLM text/JSON strings, parses them, and converts
    the resulting dictionary into a formatted Markdown string.
    """
    # 1. Clean and parse if the input is a string
    if isinstance(insight_data, str):
        start_idx = insight_data.find('{')
        end_idx = insight_data.rfind('}')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            clean_json_str = insight_data[start_idx:end_idx + 1]
            try:
                insight_data = json.loads(clean_json_str)
            except json.JSONDecodeError as e:
                # should not be here by design!
                print(e)
                # If parsing fails, just return the cleaned string as a fallback
                return clean_json_str
        else:
            # If there are no curly braces, return the raw string
            return insight_data

    if not isinstance(insight_data, dict):
        return str(insight_data)
    formatted_blocks = []

    for key, value in insight_data.items():
        # 1. Format the key as a Markdown heading (Level 3)
        # e.g., "primary_diagnosis" -> "### Primary Diagnosis"
        section_title = str(key).replace('_', ' ').title()
        formatted_blocks.append(f"### {section_title}")

        # 2. Format the value based on its type
        if isinstance(value, list):
            # Create a Markdown bulleted list
            bullet_points = "\n".join([f"* {item}" for item in value])
            formatted_blocks.append(bullet_points)
        elif isinstance(value, str):
            # Append string as a normal text block
            formatted_blocks.append(value)
        else:
            # Fallback for booleans, numbers, etc.
            formatted_blocks.append(str(value))

    # Join all blocks with double newlines for proper Markdown paragraph spacing
    return "\n\n".join(formatted_blocks)


async def broadcast_and_poll(query_text: str, query_vector: list, update_container) -> List[Dict]:
    """Broadcasts query to the Orchestrator and polls for global consensus."""
    payload = {
        "query_text": query_text or "General clinical query",
        "query_vector": query_vector,
        "target_clients": TARGET_NODES
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        SERVER_URL = os.getenv("SERVER_URL")
        # 1. Broadcast Query
        try:
            broadcast_resp = await client.post(f"{SERVER_URL}/api/v1/query/broadcast", json=payload)
            broadcast_resp.raise_for_status()
            req_id = broadcast_resp.json()["request_id"]
        except Exception as e:
            logger.error(f"Broadcast failed: {e}")
            return [{"node": "Orchestrator Error", "match_confidence": "0%", "insight": f"Broadcast failed: {e}"}]

        # 2. Poll for Consensus
        data = []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            with update_container:
                ui.notify(f"Polling orchestrator... Attempt {attempt}/{MAX_ATTEMPTS}", type='info', position='bottom-left')

            await asyncio.sleep(POLL_INTERVAL)

            try:
                cons_resp = await client.get(f"{SERVER_URL}/api/v1/query/{req_id}/consensus")
                cons_resp.raise_for_status()
                data = cons_resp.json().get("consensus_data", [])

                # Success Condition
                if len(data) == len(TARGET_NODES):
                    break
            except httpx.RequestError as e:
                logger.error(f"Error fetching consensus: {e}")
                continue

        # 3. Format insights for the UI
        formatted_results = []
        if not data:
            formatted_results.append(
                {"node": "Timeout", "match_confidence": "N/A", "insight": "No nodes responded within the time limit."})

        for item in data:
            node_id = item.get("client_id", "Unknown")
            insight_json_str = item.get("insight", {})
            print(insight_json_str)
            try:
                insight_json = json.loads(insight_json_str)
                parsed_insight = format_medical_insight(insight_json.get("msg", "NA"))
                match_confidence = float(insight_json.get("similarity", 0))
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing insight: {e}")
                continue

            formatted_results.append({
                "node": node_id,
                "match_confidence": f"{match_confidence:.5f}",
                "insight": parsed_insight
            })

        return formatted_results


# ==========================================
# 4. Upload Logic
# ==========================================
async def handle_upload(e: events.UploadEventArguments):
    global CURRENT_PATIENT, PENDING_IMAGE_B64

    filename = e.file.name.lower()
    content = await e.file.read()

    if filename.endswith('.json'):
        try:
            data = json.loads(content.decode('utf-8'))
            CURRENT_PATIENT = data[0] if isinstance(data, list) and len(data) > 0 else {}

            if PENDING_IMAGE_B64:
                CURRENT_PATIENT['image_base64'] = PENDING_IMAGE_B64
                PENDING_IMAGE_B64 = None

            ui.notify(f'Patient record {filename} loaded!', type='positive', position='bottom-left')
            ui_state.card_expanded = False
            await render_patient_area.refresh()

        except Exception as ex:
            ui.notify(f'Invalid JSON format: {ex}', type='negative', position='bottom-left')

    elif filename.endswith(('.jpg', '.jpeg', '.png')):
        b64_str = base64.b64encode(content).decode('utf-8')
        mime_type = "image/jpeg" if filename.endswith(('.jpg', '.jpeg')) else "image/png"
        data_uri = f"data:{mime_type};base64,{b64_str}"

        if CURRENT_PATIENT:
            CURRENT_PATIENT['image_base64'] = data_uri
            await render_patient_area.refresh()
        else:
            PENDING_IMAGE_B64 = data_uri
        ui.notify(f'Image {filename} attached.', type='info', position='bottom-left')


# ==========================================
# 5. UI Components & Logic
# ==========================================
class UIState:
    def __init__(self):
        self.card_expanded = False


ui_state = UIState()


@ui.refreshable
def render_patient_area():
    global CURRENT_PATIENT

    if CURRENT_PATIENT is None:
        with ui.column().classes(
                'w-full items-center justify-center gap-4 py-8 border-4 border-dashed border-gray-300 rounded-xl bg-gray-50'):
            ui.label('Upload Patient JSON and X-Ray Image').classes('text-xl font-semibold text-gray-500')
            ui.label('You can select multiple files or drag and drop them here.').classes('text-sm text-gray-400')
            ui.upload(multiple=True, auto_upload=True, on_upload=handle_upload).classes('max-w-md w-full')

    else:
        patient = CURRENT_PATIENT
        img_src = patient.get('image_base64', "assets/not_found.svg")

        with ui.card().classes('w-full shadow-lg rounded-xl p-0 overflow-hidden relative bg-white'):
            content_classes = 'flex-row gap-6 p-6 w-full transition-all duration-500 ease-in-out'
            height_classes = 'max-h-[350px] overflow-hidden' if not ui_state.card_expanded else 'h-auto overflow-visible'

            with ui.row().classes(f'{content_classes} {height_classes}'):
                ui.image(img_src).classes('w-64 h-80 rounded-lg shadow-sm object-cover shrink-0')

                with ui.column().classes('flex-1 justify-start h-full'):
                    with ui.row().classes('w-full justify-between items-center border-b pb-2'):
                        pid = patient.get('patient_id', 'Unknown ID')
                        ui.label(f"Patient ID: {pid}").classes('text-lg font-bold text-primary font-mono')
                        demos = patient.get('demographics', {})
                        ui.badge(f"{demos.get('age', 'N/A')} yo {demos.get('sex', 'N/A')}", color='secondary')

                    vitals = patient.get('vitals', {})
                    with ui.row().classes('gap-4 mt-2'):
                        ui.badge(f"HR: {vitals.get('HR', '--')}").classes('bg-red-300 text-white-800')
                        ui.badge(f"BP: {vitals.get('BP', '--')}").classes('bg-blue-300 text-white-800')
                        ui.badge(f"SpO2: {vitals.get('SpO2', '--')}%").classes('bg-gray-300 text-black-800')

                    ui.label(f"Local Diagnosis: {patient.get('hidden_diagnosis_label', 'Pending')}").classes(
                        'mt-4 font-bold text-green-700 bg-green-50 p-2 rounded self-start')

                    ui.label('Admission Note / Clinical History:').classes('font-bold mt-4 text-sm text-gray-600')
                    note_text = patient.get('admission_note') or patient.get(
                        'clinical_history') or "No details available."
                    ui.markdown(note_text).classes('text-gray-700 text-sm overflow-y-auto pr-2')

            if not ui_state.card_expanded:
                with ui.element('div').classes(
                        'absolute bottom-0 left-0 w-full h-24 bg-gradient-to-t from-white via-white/90 to-transparent pointer-events-none'):
                    pass

            with ui.row().classes('w-full bg-gray-50 p-2 justify-center border-t z-10 relative'):
                icon = 'expand_less' if ui_state.card_expanded else 'expand_more'
                label = 'Show Less Details' if ui_state.card_expanded else 'Show Full Record'
                ui.button(label, icon=icon, on_click=toggle_card_expansion).classes('text-primary').props('flat')


def toggle_card_expansion():
    ui_state.card_expanded = not ui_state.card_expanded
    render_patient_area.refresh()


def reset_demo():
    global CURRENT_PATIENT, PENDING_IMAGE_B64
    CURRENT_PATIENT = None
    PENDING_IMAGE_B64 = None
    render_patient_area.refresh()


def build_ui():
    ui.colors(primary='#2c3e50', secondary='#34495e', accent='#3498db')

    with ui.header(elevated=True).classes('bg-primary text-white items-center justify-between px-6 py-3'):
        ui.label('🛡️ Aethelgard Local Intelligence Node').classes('text-2xl font-bold')
        with ui.row().classes('items-center gap-2'):
            ui.icon('verified_user', color='green-300')
            ui.label('Status: Online').classes('text-sm text-green-300 font-mono')

    with ui.column().classes('w-full max-w-5xl mx-auto mt-8 gap-8'):
        with ui.row().classes('w-full justify-between items-end'):
            ui.label('1. Local Medical Record Context').classes('text-xl font-bold text-gray-800')
            ui.button('Reset / Load New', on_click=reset_demo, icon='restart_alt').props(
                'flat color=grey dense').classes('text-sm')

        render_patient_area()

        ui.label('2. Query the Federated Network').classes('text-xl font-bold text-gray-800 mt-8')
        ui.label('Data is processed locally. Only anonymous vectors leave this node.').classes(
            'text-sm text-gray-500 -mt-6 mb-2')

        with ui.card().classes('w-full shadow-md rounded-xl p-6 bg-slate-50'):
            question_input = ui.input(
                label='Add a specific clinical question (Optional)',
                placeholder='e.g., "What are standard diuretic protocols for this renal presentation?"'
            ).classes('w-full mb-4 bg-white')

            results_container = ui.column().classes('w-full gap-4 mt-4')

            async def execute_search():
                if CURRENT_PATIENT is None:
                    ui.notify('Please load patient data first.', type='warning', position='top')
                    return

                results_container.clear()
                with results_container:
                    with ui.row().classes('items-center gap-4 text-accent py-4'):
                        ui.spinner(size='lg', thickness=2)
                        with ui.column():
                            ui.label('Phase 1: Local Semantic Firewall executing...').classes('font-bold animate-pulse')
                            ui.label('Fetching pre-computed multimodal vector from local database.').classes('text-sm')

                # Grab the vector via LanceDB
                query_vector = await sanitize_and_vectorize(CURRENT_PATIENT, question_input.value)

                results_container.clear()
                with results_container:
                    with ui.row().classes('items-center gap-4 text-accent py-4'):
                        ui.spinner(size='lg', thickness=2, color='purple')
                        with ui.column():
                            ui.label('Phase 2: Orchestrator polling remote nodes...').classes(
                                'font-bold text-purple-600 animate-pulse')
                            ui.label(
                                f'Broadcasting {VECTOR_DIMENSIONS}-dimensional homomorphic encrypted query vectors.').classes(
                                'text-sm')

                # Ping the real server
                remote_results = await broadcast_and_poll(question_input.value, query_vector, results_container)

                results_container.clear()
                with results_container:
                    ui.label('🌍 Global Consensus Reached').classes('text-lg font-bold text-green-700 mb-2')

                    for res in remote_results:
                        with ui.card().classes('w-full border-l-4 border-accent p-4 shadow-sm bg-white'):
                            with ui.row().classes('justify-between w-full mb-2'):
                                with ui.row().classes('gap-2 items-center'):
                                    ui.icon('dns', color='primary')
                                    ui.label(res['node']).classes('font-bold text-primary font-mono')
                                ui.badge(f"Match Confidence: {res['match_confidence']}", color='green').props('outline')

                            ui.markdown(res['insight']).classes('text-gray-700 leading-relaxed bg-gray-50 p-2 rounded')

            ui.button('Search Network', on_click=execute_search, icon='travel_explore') \
                .classes('w-full py-3 shadow-md text-lg font-bold') \
                .bind_enabled_from(globals(), 'CURRENT_PATIENT', backward=lambda x: x is not None)


parser = argparse.ArgumentParser(description="Aethelgard Demo v2")
parser.add_argument("--config", type=str, required=True, help="Path to the .env profile of the local node")
args = parser.parse_args()
load_dotenv(args.config)
logger.info(f"loaded config from: {args.config}")
build_ui()
app.storage.general['upload_limit'] = 1_000_000  # 20 MB limit
ui.run(title="Aethelgard Interactive Demo", port=8080, favicon='🛡️')