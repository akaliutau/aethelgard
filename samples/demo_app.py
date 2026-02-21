import asyncio
import json
import base64
from typing import Optional, Dict, Any, List
from nicegui import ui, app, events
from aethelgard.core.config import get_logger

logger = get_logger(__name__)

# ==========================================
# 1. State & Constants
# ==========================================

# Holds the current patient data
CURRENT_PATIENT: Optional[Dict[str, Any]] = None
# Temporarily holds an uploaded image if it's uploaded before the JSON
PENDING_IMAGE_B64: Optional[str] = None


# ==========================================
# 2. Aethelgard Network Simulation
# ==========================================
async def sanitize_and_vectorize(record, question):
    await asyncio.sleep(1.0)
    return {"status": "sanitized", "vector": [0.1, 0.8, 0.3], "query": question}


async def poll_remote_nodes():
    await asyncio.sleep(2.0)
    return [
        {
            "node": "Hospital_B",
            "match_confidence": "94%",
            "insight": "High semantic match. Our localized silo contains 14 similar cases of ADHF with identical orthopnea presentation. Treatment consensus: NIPPV and IV Furosemide."
        },
        {
            "node": "Hospital_C",
            "match_confidence": "88%",
            "insight": "Match found due to CKD comorbidity. Note: In similar demographic cases, renal failure required adjusted diuretic dosing to prevent acute kidney injury."
        }
    ]


# ==========================================
# 3. Upload Logic
# ==========================================
async def handle_upload(e: events.UploadEventArguments):
    """Processes bytes streamed from the browser (no absolute paths)."""
    global CURRENT_PATIENT, PENDING_IMAGE_B64

    filename = e.file.name.lower()
    content = await e.file.read()  # Read the raw bytes

    if filename.endswith('.json'):
        try:
            # Decode bytes to string, parse JSON
            data: List[Dict] = json.loads(content.decode('utf-8'))

            # Handle case where JSON is a list (like the patient00002.json example)

            CURRENT_PATIENT = data[0] if isinstance(data, list) and len(data) > 0 else {}

            # Attach image if it was uploaded first
            if PENDING_IMAGE_B64:
                CURRENT_PATIENT['image_base64'] = PENDING_IMAGE_B64
                PENDING_IMAGE_B64 = None

            ui.notify(f'Patient record {filename} loaded!', type='positive')
            ui_state.card_expanded = False
            await render_patient_area.refresh()

        except Exception as ex:
            ui.notify(f'Invalid JSON format: {ex}', type='negative')

    elif filename.endswith(('.jpg', '.jpeg', '.png')):
        # Convert raw image bytes to a Base64 string for the browser to render
        b64_str = base64.b64encode(content).decode('utf-8')
        mime_type = "image/jpeg" if filename.endswith(('.jpg', '.jpeg')) else "image/png"
        data_uri = f"data:{mime_type};base64,{b64_str}"

        if CURRENT_PATIENT:
            CURRENT_PATIENT['image_base64'] = data_uri
            await render_patient_area.refresh()
        else:
            PENDING_IMAGE_B64 = data_uri
        ui.notify(f'Image {filename} attached.', type='info')


# ==========================================
# 4. UI Components & Logic
# ==========================================
class UIState:
    def __init__(self):
        self.card_expanded = False


ui_state = UIState()


@ui.refreshable
def render_patient_area():
    global CURRENT_PATIENT

    if CURRENT_PATIENT is None:
        # --- State A: Standard NiceGUI Uploader ---
        with ui.column().classes(
                'w-full items-center justify-center gap-4 py-8 border-4 border-dashed border-gray-300 rounded-xl bg-gray-50'):
            ui.label('Upload Patient JSON and X-Ray Image').classes('text-xl font-semibold text-gray-500')
            ui.label('You can select multiple files or drag and drop them here.').classes('text-sm text-gray-400')

            # This standard component handles drag-and-drop and file selection natively
            ui.upload(multiple=True, auto_upload=True, on_upload=handle_upload).classes('max-w-md w-full')

    else:
        # --- State B: The Expandable Patient Card ---
        patient = CURRENT_PATIENT
        img_src = patient.get('image_base64', "https://placehold.co/400x600/1e293b/ffffff?text=Image+Not+Found")

        with ui.card().classes('w-full shadow-lg rounded-xl p-0 overflow-hidden relative bg-white'):
            content_classes = 'flex-row gap-6 p-6 w-full transition-all duration-500 ease-in-out'
            height_classes = 'max-h-[350px] overflow-hidden' if not ui_state.card_expanded else 'h-auto overflow-visible'

            with ui.row().classes(f'{content_classes} {height_classes}'):
                # Left: Image
                ui.image(img_src).classes('w-64 h-80 rounded-lg shadow-sm object-cover shrink-0')

                # Right: Clinical Details
                with ui.column().classes('flex-1 justify-start h-full'):
                    with ui.row().classes('w-full justify-between items-center border-b pb-2'):
                        pid = patient.get('patient_id', 'Unknown ID')
                        ui.label(f"Patient ID: {pid}").classes('text-lg font-bold text-primary font-mono')
                        demos = patient.get('demographics', {})
                        ui.badge(f"{demos.get('age', 'N/A')} yo {demos.get('sex', 'N/A')}", color='secondary')

                    vitals = patient.get('vitals', {})
                    with ui.row().classes('gap-4 mt-2'):
                        ui.badge(f"HR: {vitals.get('HR', '--')}").classes('bg-red-100 text-red-800')
                        ui.badge(f"BP: {vitals.get('BP', '--')}").classes('bg-blue-100 text-blue-800')
                        ui.badge(f"SpO2: {vitals.get('SpO2', '--')}%").classes('bg-gray-100 text-gray-800')

                    ui.label(f"Local Diagnosis: {patient.get('hidden_diagnosis_label', 'Pending')}").classes(
                        'mt-4 font-bold text-green-700 bg-green-50 p-2 rounded self-start')

                    ui.label('Admission Note / Clinical History:').classes('font-bold mt-4 text-sm text-gray-600')
                    note_text = patient.get('admission_note') or patient.get(
                        'clinical_history') or "No details available."
                    ui.markdown(note_text).classes('text-gray-700 text-sm overflow-y-auto pr-2')

            # --- Fade Out Gradient Overlay ---
            if not ui_state.card_expanded:
                with ui.element('div').classes(
                        'absolute bottom-0 left-0 w-full h-24 bg-gradient-to-t from-white via-white/90 to-transparent pointer-events-none'):
                    pass

            # --- Toggle Button Bar ---
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

    # Header
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

        # Reactive Area
        render_patient_area()

        # Federated Search Area
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
                            ui.label('Stripping PII & vectorizing clinical features.').classes('text-sm')

                await sanitize_and_vectorize(CURRENT_PATIENT, question_input.value)

                results_container.clear()
                with results_container:
                    with ui.row().classes('items-center gap-4 text-accent py-4'):
                        ui.spinner(size='lg', thickness=2, color='purple')
                        with ui.column():
                            ui.label('Phase 2: Orchestrator polling remote nodes...').classes(
                                'font-bold text-purple-600 animate-pulse')
                            ui.label('Broadcasting homomorphic encrypted query vectors.').classes('text-sm')

                remote_results = await poll_remote_nodes()

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
                            ui.label(res['insight']).classes('text-gray-700 leading-relaxed')

            ui.button('Search Network', on_click=execute_search, icon='travel_explore') \
                .classes('w-full py-3 shadow-md text-lg font-bold') \
                .bind_enabled_from(globals(), 'CURRENT_PATIENT', backward=lambda x: x is not None)


build_ui()
app.storage.general['upload_limit'] = 1_000_000  # 20 MB limit
ui.run(title="Aethelgard Interactive Demo", port=8080, favicon='🛡️')