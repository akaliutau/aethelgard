import json
from pathlib import Path

import lancedb
import litellm
import numpy as np
import pyarrow as pa
import torch
from PIL import Image
from dotenv import load_dotenv
from transformers import AutoImageProcessor, AutoModel

from aethelgard.core.smartfolder import SmartFolder

load_dotenv()

# ==========================================
# Configuration
# ==========================================
DATA_DIR = Path("./dataset/Hospital_A")
DB_PATH = "./lancedb_store"
TABLE_NAME = "patients"

# LiteLLM config for local Ollama text embeddings
TEXT_MODEL_EMB = "ollama/embeddinggemma"
API_BASE = "http://localhost:11434"

# Vision Model
VISION_MODEL_NAME = "google/medsiglip-448"

# Force the device to CPU explicitly
DEVICE = "cpu"

# Load the vision model (Ensure you ran `huggingface-cli login` in your terminal first!)
image_processor = AutoImageProcessor.from_pretrained(VISION_MODEL_NAME, trust_remote_code=True, use_fast=True)
vision_model = AutoModel.from_pretrained(VISION_MODEL_NAME, trust_remote_code=True).to(DEVICE)
vision_model.eval()

def get_text_embedding(text: str) -> np.ndarray:
    """Uses local Ollama to generate MedGemma 4B text embeddings."""
    response = litellm.embedding(
        model=TEXT_MODEL_EMB,
        input=text,
        api_base=API_BASE,
        caching=True
    )
    return np.array(response.data[0]['embedding'], dtype=np.float32)


def get_image_embedding(image_path: str) -> np.ndarray:
    """Runs MedSigLIP to generate a medical image embedding."""
    image = Image.open(image_path).convert('RGB')
    # The processor automatically handles the 448x448 medical normalization
    inputs = image_processor(images=image, return_tensors="pt").to(DEVICE)

    with torch.no_grad():
        # 1. Pass the inputs to the vision model (bypassing get_image_features)
        outputs = vision_model.vision_model(**inputs)
        # 2. Extract the actual 1152-d PyTorch tensor from the wrapper object
        embedding = outputs.pooler_output
        # 3. Standard practice: L2 normalize the vector for LanceDB cosine similarity
        embedding = torch.nn.functional.normalize(embedding, p=2, dim=-1)

    return embedding.squeeze().cpu().numpy().astype(np.float32)


class LocalIntelligenceNode:
    def __init__(self):
        print("Connecting to LanceDB...")
        self.db = lancedb.connect(DB_PATH)
        self.tracker = SmartFolder()

        # Define the schema: Fused vector, raw JSON string, and unique ID
        # Assume (768 from embeddinggemma + 1152 from MedSigLIP)
        self.schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), 1920)),
            pa.field("metadata", pa.string())
        ])

        have_tables = self.db.list_tables()
        if have_tables and TABLE_NAME not in have_tables.tables:
            self.table = self.db.create_table(TABLE_NAME, schema=self.schema)
        else:
            self.table = self.db.open_table(TABLE_NAME)


    def _fuse_vectors(self, text_vec: np.ndarray, image_vec: np.ndarray) -> list:
        """Concatenates the multimodal vectors
           Normalize before fusion to prevent one modality from dominating
        """
        text_norm = text_vec / np.linalg.norm(text_vec)
        img_norm = image_vec / np.linalg.norm(image_vec)

        fused = np.concatenate([img_norm, text_norm])
        return fused.tolist()

    def sync_database(self):
        """On-demand sync. Only processes files flagged by the SQLite tracker."""
        new_data = []
        processed_files = []

        print("Scanning file system for changes...")

        # This loop acts exactly like a 'git add' diff
        for filepath, timestamp, size in self.tracker.get_changed_files(DATA_DIR):
            try:
                json_path = Path(filepath)
                patient_id = json_path.stem
                print(f"Detected new/changed data: {patient_id}")

                with open(json_path, 'r') as f:
                    records = json.load(f)
                    patient_record = records[0]

                img_path = DATA_DIR / patient_record.get("image_reference", "")
                if not img_path.exists():
                    print(f"  -> Skipping {patient_id}: Image missing.")
                    continue
                if 'error' in patient_record:
                    print(f"  -> Skipping {patient_id}: {patient_record['error']}")
                    continue

                # Generate Embeddings & Fuse
                txt_vec = get_text_embedding(json.dumps(patient_record["admission_note"]))
                img_vec = get_image_embedding(img_path)
                fused_vector = self._fuse_vectors(txt_vec, img_vec)

                new_data.append({
                    "id": patient_id,
                    "vector": fused_vector,
                    "metadata": json.dumps(patient_record)
                })

                # Queue the tracker update
                processed_files.append((filepath, timestamp, size))
            except Exception as e:
                print(e)

        if new_data:
            print(f"Inserting {len(new_data)} new records into LanceDB...")
            self.table.add(new_data)

            # Commit the new state to SQLite ONLY if vector insertion succeeds
            for filepath, timestamp, size in processed_files:
                self.tracker.mark_processed(filepath, timestamp, size)

            #Check how many rows are in the table
            #num_rows = self.table.count_rows()
            #self.table.create_index(metric="cosine", vector_column_name="vector")
            print("Sync complete!")
        else:
            print("No changes detected.")

if __name__ == "__main__":
    node = LocalIntelligenceNode()
    node.sync_database()