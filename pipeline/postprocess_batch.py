import argparse
import json
import os
import random
import shutil
from pathlib import Path

import google.auth
import google.auth.transport.requests
import requests
from dotenv import load_dotenv
from tqdm import tqdm

# ==========================================
# Configuration
# ==========================================
load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT_DIR / "templates"
DATA_DIR = ROOT_DIR / "dataset"
CACHE_DIR = ROOT_DIR / "cache"
INPUT_JSONL = Path("batch_input.jsonl")
OUTPUT_JSONL = CACHE_DIR / "batch_output" / "results.jsonl"

LOG_LEVEL = "INFO"
APP_VERSION = "0.1.0"

HOSPITALS = ["Hospital_A", "Hospital_B"]
BLIND_SPOT_DISEASE = "Consolidation"


# ==========================================
# 1. GCP Auth & Inference Helpers
# ==========================================
def get_gcp_token() -> str:
    """Dynamically fetches the GCP bearer token using default credentials."""
    # Explicitly request the cloud-platform scope required for Vertex REST APIs
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials, project = google.auth.default(scopes=scopes)
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token


def run_inference(endpoint_url: str):
    """Reads the local JSONL input, fires HTTP POSTs to Vertex AI, and saves results."""
    print(f"\n==========================================")
    print(f"1. Submitting Requests to Deployed Endpoint")
    print(f"==========================================")
    print(f"🔗 Target URL: {endpoint_url}")

    if not INPUT_JSONL.exists():
        raise FileNotFoundError(f"❌ Input file {INPUT_JSONL} not found!")

    # Ensure output directory exists and clear previous results
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_JSONL.exists():
        OUTPUT_JSONL.unlink()

    # Read all lines
    with open(INPUT_JSONL, 'r', encoding='utf-8') as f:
        payloads = [line.strip() for line in f if line.strip()]

    token = get_gcp_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }

    print(f"Starting inference for {len(payloads)} records...")

    with open(OUTPUT_JSONL, 'w', encoding='utf-8') as out_f:
        # Wrap the loop with tqdm for a sleek progress bar
        for idx, payload in enumerate(tqdm(payloads, desc="Processing Patients", unit="req")):
            try:
                response = requests.post(endpoint_url, headers=headers, data=payload, timeout=60)

                # Check for HTTP errors or Vertex AI specific errors
                if response.status_code != 200 or '"error"' in response.text:
                    print(f"\n❌ Error on record {idx + 1}: {response.text}")

                # Strip newlines to maintain strict JSONL format
                clean_response = response.text.replace('\n', '')
                out_f.write(clean_response + "\n")

            except Exception as e:
                print(f"\n❌ Network exception on record {idx + 1}: {e}")

    print(f"\n✅ Batch Inference Complete! Saved to: {OUTPUT_JSONL}")


# ==========================================
# 2. Post-Processing Helpers
# ==========================================
def _extract_json_from_text(text: str) -> dict:
    """Helper to strip markdown and extract the raw JSON dictionary from the LLM output."""
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != 0:
            return json.loads(text[start:end])
        return {"error": "Could not parse JSON", "raw": text}
    except Exception as error:
        return {"error": f"Invalid JSON generated: {error}", "raw": text}


def process_results(dataset_dir: str):
    """Parses the generated JSONL and silos the data and images."""
    print(f"\n==========================================")
    print(f"2. Running Python Post-Processing")
    print(f"==========================================")

    for h in HOSPITALS:
        os.makedirs(DATA_DIR / h, exist_ok=True)

    with open("batch_metadata.json", "r") as f:
        metadata = json.load(f)

    if not OUTPUT_JSONL.exists():
        print(f"❌ No prediction JSONL file found at {OUTPUT_JSONL}")
        return

    patient_records = {}

    with open(OUTPUT_JSONL, "r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f):
            if not line.strip(): continue
            data = json.loads(line)

            # Extract prediction (Handle Vertex standard "predictions" array)
            # Depending on model configuration, it could be 'predictions' or 'prediction'
            predictions = data.get("predictions", data.get("prediction", []))
            raw_prediction = predictions[0] if isinstance(predictions, list) and predictions else str(predictions)

            parsed_record = _extract_json_from_text(raw_prediction)

            # Marry with metadata
            meta = metadata[str(line_idx)]
            pid = meta["patient_id"]

            parsed_record["patient_id"] = pid
            parsed_record["image_reference"] = meta["image_reference"]

            if pid not in patient_records:
                patient_records[pid] = {"records": [], "meta": meta}

            patient_records[pid]["records"].append(parsed_record)

    # Silo Routing
    for pid, p_data in patient_records.items():
        if BLIND_SPOT_DISEASE in p_data["meta"]["all_pathologies"]:
            target_hospital = "Hospital_B"
        else:
            target_hospital = random.choice(HOSPITALS)

        hospital_dir = DATA_DIR / target_hospital

        with open(hospital_dir / f"{pid}.json", "w") as f:
            json.dump(p_data["records"], f, indent=4)

        src_image = Path(dataset_dir) / p_data["meta"]["original_path"]
        dst_image = hospital_dir / p_data["meta"]["image_reference"]
        if src_image.exists():
            shutil.copy(src_image, dst_image)

        print(f"✅ Saved {pid} to {target_hospital}")


# ==========================================
# Main Execution
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Aethelgard Inference and Post-Processor")
    parser.add_argument("--dataset_dir", type=str, required=True, help="Path to original CheXpert data")
    parser.add_argument("--endpoint", type=str, required=True, help="Endpoint URL")
    args = parser.parse_args()

    run_inference(args.endpoint)
    process_results(args.dataset_dir)

if __name__ == "__main__":
    main()