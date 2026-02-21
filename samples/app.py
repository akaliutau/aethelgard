import asyncio

from nicegui import ui

# ==========================================
# 1. Dummy Local Data (From your JSON)
# ==========================================
LOCAL_DATA = [
    {
        "demographics": {"age": 87, "sex": "Female"},
        "vitals": {"HR": 115, "BP": "140/85", "SpO2": 88, "Temp": 37.0},
        "hidden_diagnosis_label": "Acute Decompensated Heart Failure",
        "admission_note": "Patient is an 87-year-old female with a history of hypertension, hyperlipidemia, atrial fibrillation... (Shortened for UI)",
        "patient_id": "patient00002",
        # Using a reliable placeholder image for the demo sketch so it renders instantly
        "image_reference": "https://placehold.co/400x400/1e293b/ffffff?text=Chest+X-Ray\n(Frontal)"
    }
]


# ==========================================
# 2. Dummy Aethelgard Network Functions
# ==========================================
async def sanitize_and_vectorize(record, question):
    """Simulates the local Semantic Firewall stripping identifiers and fusing vectors."""
    await asyncio.sleep(0.5)  # Simulate local processing
    return {"status": "sanitized", "vector": [0.1, 0.8, 0.3], "query": question}


async def poll_remote_nodes():
    """Simulates the Orchestrator broadcasting, nodes processing, and returning consensus."""
    await asyncio.sleep(3.0)  # Simulate network delay and remote LLM inference

    # Mock aggregated insights returned from Hospital B and C
    return [
        {
            "node": "Hospital_B",
            "match_confidence": "94%",
            "insight": "High semantic match. Our localized silo contains 14 similar cases of ADHF with identical orthopnea presentation. Treatment consensus: NIPPV and IV Furosemide."
        },
        {
            "node": "Hospital_C",
            "match_confidence": "88%",
            "insight": "Match found. Note: In 3 of our similar demographic cases, underlying renal failure (CKD Stage 3) required adjusted diuretic dosing to prevent acute kidney injury."
        }
    ]


# ==========================================
# 3. UI Construction
# ==========================================
def build_ui():
    ui.colors(primary='#2c3e50', secondary='#34495e', accent='#3498db')

    # Header
    with ui.header(elevated=True).classes('bg-primary text-white items-center justify-between px-6 py-3'):
        ui.label('🛡️ Aethelgard Local Intelligence Node').classes('text-2xl font-bold')
        ui.label('Status: Securely Isolated').classes('text-sm text-green-300 font-mono')

    with ui.column().classes('w-full max-w-5xl mx-auto mt-8 gap-8'):
        # --- Local Data Section ---
        ui.label('Local Medical Record').classes('text-xl font-bold text-gray-800')
        patient = LOCAL_DATA[0]

        # The "Visual Medical Card"
        with ui.card().classes('w-full shadow-lg rounded-xl flex-row gap-6 p-6'):
            # Left: Image
            ui.image(patient['image_reference']).classes('w-64 h-64 rounded-lg shadow-sm object-cover')

            # Right: Clinical Details
            with ui.column().classes('flex-1 justify-between'):
                with ui.row().classes('w-full justify-between items-center border-b pb-2'):
                    ui.label(f"Patient ID: {patient['patient_id']}").classes('text-lg font-bold text-primary font-mono')
                    ui.badge(f"{patient['demographics']['age']} yo {patient['demographics']['sex']}", color='secondary')

                with ui.row().classes('gap-4 mt-2'):
                    ui.badge(f"HR: {patient['vitals']['HR']}").classes('bg-red-100 text-red-800')
                    ui.badge(f"BP: {patient['vitals']['BP']}").classes('bg-blue-100 text-blue-800')
                    ui.badge(f"SpO2: {patient['vitals']['SpO2']}%").classes('bg-gray-100 text-gray-800')

                ui.label('Clinical History Snippet:').classes('font-bold mt-2 text-sm text-gray-600')
                ui.label(patient['admission_note']).classes('text-gray-700 italic text-sm')

                ui.label(f"Local Diagnosis: {patient['hidden_diagnosis_label']}").classes(
                    'mt-4 font-bold text-green-700 bg-green-50 p-2 rounded')

        # --- Federated Search Section ---
        ui.label('Query the Federated Network').classes('text-xl font-bold text-gray-800 mt-4')

        with ui.card().classes('w-full shadow-md rounded-xl p-6 bg-slate-50'):
            question_input = ui.input(
                label='Add a specific clinical question (Optional)',
                placeholder='e.g., "What are the standard diuretic adjustment protocols for this presentation?"'
            ).classes('w-full mb-4')

            # Container to hold our dynamic results
            results_container = ui.column().classes('w-full gap-4 mt-4')

            async def execute_search():
                results_container.clear()  # Clear previous results

                with results_container:
                    # Show spinner
                    with ui.row().classes('items-center gap-4 text-accent'):
                        ui.spinner(size='lg')
                        ui.label('Sanitizing local record & polling remote hospital nodes...').classes(
                            'font-bold animate-pulse')

                # Execute backend logic
                await sanitize_and_vectorize(patient, question_input.value)
                remote_results = await poll_remote_nodes()

                # Clear spinner and show results
                results_container.clear()
                with results_container:
                    ui.label('🌍 Global Consensus Reached').classes('text-lg font-bold text-green-700 mb-2')

                    for res in remote_results:
                        with ui.card().classes('w-full border-l-4 border-accent p-4 shadow-sm'):
                            with ui.row().classes('justify-between w-full mb-2'):
                                ui.label(res['node']).classes('font-bold text-primary font-mono')
                                ui.badge(f"Confidence: {res['match_confidence']}", color='green')
                            ui.label(res['insight']).classes('text-gray-700')

            # Search Button triggers the async flow
            ui.button('Sanitize & Search Network', on_click=execute_search, icon='travel_explore').classes(
                'w-full py-3 shadow-md')


build_ui()
ui.run(title="Aethelgard Demo", port=8080)