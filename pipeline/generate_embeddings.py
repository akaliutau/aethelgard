import json
from pathlib import Path

import lancedb
import litellm
import numpy as np
import pyarrow as pa
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel

# ==========================================
# Configuration
# ==========================================
DATA_DIR = Path("./dataset/Hospital_A")
DB_PATH = "./lancedb_store"
TABLE_NAME = "patients"

# LiteLLM config for local Ollama text embeddings
TEXT_MODEL = "ollama/gemma:4b"
API_BASE = "http://localhost:11434"

# Vision Model (Mocking MedSigLIP for 128-d output)
VISION_MODEL_NAME = "google/siglip-base-patch16-224"

# Force the device to CPU explicitly
DEVICE = "cpu"

# Load the vision model (Downloads ~400MB)
image_processor = AutoImageProcessor.from_pretrained(VISION_MODEL_NAME)
vision_model = AutoModel.from_pretrained(VISION_MODEL_NAME).to(DEVICE)


def get_text_embedding(text: str) -> np.ndarray:
    """Uses local Ollama to generate MedGemma 4B text embeddings."""
    response = litellm.embedding(
        model=TEXT_MODEL,
        input=text,
        api_base="http://localhost:11434"
    )
    return np.array(response.data[0]['embedding'], dtype=np.float32)[:2048]


def get_image_embedding(image_path: str) -> np.ndarray:
    """Runs the vision model natively on the CPU."""
    image = Image.open(image_path).convert('RGB')
    inputs = image_processor(images=image, return_tensors="pt").to(DEVICE)

    with torch.no_grad():
        outputs = vision_model(**inputs)
        # Flatten and project to 128-d
        return outputs.pooler_output.numpy().flatten()[:128].astype(np.float32)

class LocalIntelligenceNode:
    def __init__(self):
        print("Connecting to LanceDB...")
        self.db = lancedb.connect(DB_PATH)

        # Define the schema: Fused vector, raw JSON string, and unique ID
        # Assume 128-d (image) + 2048-d (Gemma text) = 2176-d fused vector
        self.schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), 2176)),
            pa.field("metadata", pa.string())
        ])


    def fuse_vectors(self, text_vec: np.ndarray, image_vec: np.ndarray) -> list:
        """Concatenates the multimodal vectors: $V_{fused} = V_{image} \oplus V_{text}$"""
        # Normalize before fusion to prevent one modality from dominating
        text_norm = text_vec / np.linalg.norm(text_vec)
        img_norm = image_vec / np.linalg.norm(image_vec)

        fused = np.concatenate([img_norm, text_norm])
        return fused.tolist()

    def sync_database(self):
        """Idempotent sync: only processes new files not already in LanceDB."""
        if TABLE_NAME in self.db.table_names():
            table = self.db.open_table(TABLE_NAME)
            existing_ids = set(table.to_pandas()['id'].tolist())
            print(f"Found {len(existing_ids)} existing records. Checking for new data...")
        else:
            table = self.db.create_table(TABLE_NAME, schema=self.schema)
            existing_ids = set()
            print("Created new LanceDB table.")

        new_data = []

        # Scan the local directory for JSON files
        for json_path in DATA_DIR.glob("*.json"):
            patient_id = json_path.stem

            if patient_id in existing_ids:
                continue  # Skip, already processed (Idempotency)

            print(f"Processing new patient: {patient_id}")

            with open(json_path, 'r') as f:
                records = json.load(f)
                patient_record = records[0]  # Assuming array of 1 based on previous script

            img_path = DATA_DIR / patient_record.get("image_reference", "")
            if not img_path.exists():
                print(f"  -> Skipping {patient_id}: Image missing.")
                continue

            # 1. Generate Embeddings
            txt_vec = get_text_embedding(json.dumps(patient_record["admission_note"]))
            img_vec = get_image_embedding(img_path)

            # 2. Vector Fusion
            fused_vector = self.fuse_vectors(txt_vec, img_vec)

            new_data.append({
                "id": patient_id,
                "vector": fused_vector,
                "metadata": json.dumps(patient_record)  # Store raw payload for the firewall
            })

        if new_data:
            print(f"Inserting {len(new_data)} new records into LanceDB...")
            table.add(new_data)

            # Rebuild the IVF-PQ index for fast retrieval
            print("Optimizing IVF-PQ Index...")
            table.create_index(metric="cosine", vector_column_name="vector")
            print("Sync complete!")
        else:
            print("Local database is already perfectly in sync.")


if __name__ == "__main__":
    node = LocalIntelligenceNode()
    node.sync_database()