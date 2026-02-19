"""
This script reads the CheXpert CSV and templates the prompts.
Critically, it outputs two files: the input.jsonl for Vertex AI, and a metadata.json file.
Because Batch Prediction is asynchronous, we need the metadata file to map the returned predictions back
to the correct patient and image.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader

from dotenv import load_dotenv

# ==========================================
# Configuration
# ==========================================

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT_DIR / "templates"
DATA_DIR = ROOT_DIR / "dataset"

LOG_LEVEL = "INFO"
APP_VERSION = "0.1.0"

print(f"Project Root Directory: {ROOT_DIR}")
print(f"TEMPLATES Directory: {TEMPLATES_DIR}")

TARGET_PATHOLOGIES = ["Atelectasis", "Cardiomegaly", "Consolidation", "Edema", "Pleural Effusion"]

def new_entry() -> Dict[str, Any]:
    return {"images": [], "sex": "", "age": ""}

def main(dataset_dir: str, limit: int):
    csv_path = Path(dataset_dir) / "train.csv"
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("generate_patient.j2")

    patients_dict: Dict[str, Any] = defaultdict(new_entry)

    # 1. Parse CSV
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            parts = row["Path"].split('/')
            if len(parts) < 5: continue

            pid = parts[2]
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

            patients_dict[pid]["sex"] = row["Sex"]
            patients_dict[pid]["age"] = row["Age"]
            patients_dict[pid]["images"].append({
                "original_path": row["Path"],
                "pict_name": pict_name,
                "positive_findings": pos,
                "negative_findings": neg,
                "uncertain_findings": unc
            })

            if len(patients_dict) >= limit and pid not in patients_dict:
                break

    # 2. Write JSONL and Metadata Map
    metadata_map = {}
    line_index = 0

    with open("batch_input.jsonl", "w", encoding="utf-8") as f_out:
        for pid, data in list(patients_dict.items())[:limit]:
            for img in data["images"]:
                prompt_text = template.render(
                    age=data["age"], sex=data["sex"],
                    positive_findings=img["positive_findings"],
                    negative_findings=img["negative_findings"],
                    uncertain_findings=img["uncertain_findings"]
                )

                # Write to JSONL for Vertex
                payload = {"instances": [{"prompt": prompt_text, "max_tokens": 2048, "temperature": 0.2}]}
                f_out.write(json.dumps(payload) + "\n")

                # Track Metadata locally
                metadata_map[str(line_index)] = {
                    "patient_id": pid,
                    "image_reference": f"{pid}_{img['pict_name']}.jpg",
                    "original_path": img["original_path"],
                    "all_pathologies": img["positive_findings"]
                }
                line_index += 1

    with open("batch_metadata.json", "w", encoding="utf-8") as meta_f:
        json.dump(metadata_map, meta_f, indent=4)

    print(f"✅ Prepared {line_index} prompts for Vertex AI Batch Prediction.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_dir", type=str, required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    main(args.dataset_dir, args.limit)