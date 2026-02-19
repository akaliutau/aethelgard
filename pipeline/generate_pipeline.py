import argparse
import asyncio
import csv
import json
import os
import random
import shutil
from collections import defaultdict
from pathlib import Path
from typing import List
from dataclasses import dataclass

from jinja2 import Environment, FileSystemLoader
from aethelgard.core.llm_middleware import call_llm, ModelConfig, coerce_to_json
from dotenv import load_dotenv

# ==========================================
# Configuration & Dataclasses
# ==========================================

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT_DIR / "templates"
DATA_DIR = ROOT_DIR / "dataset"

LOG_LEVEL = "INFO"
APP_VERSION = "0.1.0"

print(f"Project Root Directory: {ROOT_DIR}")
print(f"TEMPLATES Directory: {TEMPLATES_DIR}")


# ==========================================
# Configuration & Dataclasses
# ==========================================
HOSPITALS = ["Hospital_A", "Hospital_B"]
BLIND_SPOT_DISEASE = "Consolidation"  # Hospital_A will never see this

TARGET_PATHOLOGIES = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion"
]


@dataclass
class ChexpertImageRecord:
    original_path: str
    pict_name: str
    positive_findings: List[str]
    negative_findings: List[str]
    uncertain_findings: List[str]


@dataclass
class ChexpertPatient:
    patient_id: str
    sex: str
    age: str
    images: List[ChexpertImageRecord]


# ==========================================
# Helper Functions
# ==========================================
def parse_chexpert_csv(csv_path: str, limit: int) -> List[ChexpertPatient]:
    """Reads the CheXpert CSV and groups multiple image records by patient."""
    patients_dict = defaultdict(lambda: {"images": [], "sex": "", "age": ""})

    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Path format: CheXpert-v1.0-small/train/patient00005/study1/view1_frontal.jpg
            # https://www.kaggle.com/datasets/ashery/chexpert
            parts = row["Path"].split('/')
            if len(parts) < 5:
                continue

            patient_id = parts[2]
            # Create a unique picture name, e.g., "study1_view1_frontal"
            pict_name = f"{parts[3]}_{parts[4].replace('.jpg', '')}"

            pos, neg, unc = [], [], []
            for path in TARGET_PATHOLOGIES:
                val = row.get(path, "")
                if val == "1.0":
                    pos.append(path)
                elif val == "0.0":
                    neg.append(path)
                elif val == "-1.0":
                    unc.append(path)

            patients_dict[patient_id]["sex"] = row["Sex"]
            patients_dict[patient_id]["age"] = row["Age"]
            patients_dict[patient_id]["images"].append(
                ChexpertImageRecord(
                    original_path=row["Path"],
                    pict_name=pict_name,
                    positive_findings=pos,
                    negative_findings=neg,
                    uncertain_findings=unc
                )
            )

            # Stop accumulating new patients if we hit the limit
            if len(patients_dict) >= limit and patient_id not in patients_dict:
                break

    # Convert to dataclasses
    patients = []
    for pid, data in list(patients_dict.items())[:limit]:
        patients.append(ChexpertPatient(
            patient_id=pid,
            sex=data["sex"],
            age=data["age"],
            images=data["images"]
        ))
    return patients


# ==========================================
# Main Pipeline Logic
# ==========================================
async def generate_dataset(dataset_dir: str, limit: int):
    csv_path = Path(dataset_dir) / "train.csv"

    # 1. Setup Directories
    for h in HOSPITALS:
        os.makedirs(DATA_DIR / h, exist_ok=True)

    # 2. Setup Jinja2 Template
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("generate_patient.j2")

    # 3. Configure GCP Gemini via Middleware
    config = ModelConfig(
        name="synthetic-generator",
        model="gemini/gemini-2.0-flash-thinking-exp-1219",
        temperature=0.7,
        retries=3
    )

    print(f"Loading CheXpert records from {csv_path}...")
    patients = parse_chexpert_csv(str(csv_path), limit=limit)
    print(f"Loaded {len(patients)} unique patients. Generating JSON arrays...")

    for patient in patients:
        patient_json_array = []
        all_patient_pathologies = set()

        # Determine hospital routing for the ENTIRE patient to keep records siloed properly
        for img in patient.images:
            all_patient_pathologies.update(img.positive_findings)

        if BLIND_SPOT_DISEASE in all_patient_pathologies:
            target_hospital = "Hospital_B"
        else:
            target_hospital = random.choice(HOSPITALS)

        hospital_dir = DATA_DIR / target_hospital

        # Generate a distinct note for each image/study
        for img in patient.images:
            prompt_text = template.render(
                age=patient.age,
                sex=patient.sex,
                positive_findings=img.positive_findings,
                negative_findings=img.negative_findings,
                uncertain_findings=img.uncertain_findings
            )

            messages = [{"role": "user", "content": prompt_text}]

            try:
                synthetic_json = await call_llm(
                    messages=messages,
                    config=config,
                    transformer=coerce_to_json,
                    metadata={}
                )

                # Attach tracking metadata
                synthetic_json["patient_id"] = patient.patient_id
                synthetic_json["image_reference"] = f"{patient.patient_id}_{img.pict_name}.jpg"
                patient_json_array.append(synthetic_json)

                # Copy and rename the image file
                src_image = Path(dataset_dir) / img.original_path
                dst_image = hospital_dir / f"{patient.patient_id}_{img.pict_name}.jpg"

                if src_image.exists():
                    shutil.copy(src_image, dst_image)
                else:
                    print(f"Warning: Image {src_image} not found.")

            except Exception as e:
                print(f"Failed to generate record for {patient.patient_id} - {img.pict_name}: {e}")

        # Save the combined JSON array for the patient
        if patient_json_array:
            json_path = hospital_dir / f"{patient.patient_id}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(patient_json_array, f, indent=4)

            print(f"Saved {patient.patient_id} ({len(patient.images)} images) to {target_hospital}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Aethelgard Synthetic Dataset from CheXpert")
    parser.add_argument("--dataset_dir", type=str, required=True,
                        help="Path to the extracted CheXpert dataset directory (must contain train.csv)")
    parser.add_argument("--limit", type=int, default=2, help="Number of unique patients to process")

    args = parser.parse_args()

    # Ensure GEMINI_API_KEY is exported in the environment
    asyncio.run(generate_dataset(args.dataset_dir, args.limit))