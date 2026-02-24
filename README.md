# 🛡️ Aethelgard

<p>
 <a><img alt="Status" src="https://img.shields.io/badge/status-research_prototype-6a5acd"></a>
 <a><img alt="Python" src="https://img.shields.io/badge/Python-3.12%2B-blue"></a>
 <a><img alt="License" src="https://img.shields.io/badge/license-MIT-lightgrey"></a>
</p>

**Aethelgard** is a lightweight, pure-pull Federated Retrieval-Augmented Generation (FedRAG) framework. 
It allows you to query highly sensitive, distributed vector databases (like clinical patient data) without ever moving 
raw data or opening inbound corporate firewalls.
Unlike traditional federated learning frameworks that focus on *training* models across silos, 
Aethelgard focuses strictly on *inference and routing*.

<p align="center">
<img src="docs/local_intelligence_node.png" width="85%" alt="Local Intelligence Node" />

<em>Figure 1: The concept of UI for the Local Intelligence Node (`samples/demo_app_2.py`)</em>
</p>


### ✨ Key Features

* **Pure-Pull Architecture:** Edge nodes use outbound asynchronous polling. **Zero inbound port-forwarding required** by IT departments.
* **100% Pluggable:** Ships with FastAPI and Redis defaults, but core abstractions allow easy swapping to gRPC, Kafka, AWS SQS, or GCP Pub/Sub.
* **Semantic Firewall Ready:** Designed to easily integrate local LLM verification (e.g., MedGemma) to sanitize vector search 
results before they are transmitted back to the global orchestrator.

Aethelgard is built on Hexagonal Architecture. Don't want to use Redis? Write your own Broker:

```python
from aethelgard.core.broker import BaseTaskBroker
```
TBA


## 📂 Project Structure

The codebase is organized to separate infrastructure from geometric logic.

```text
aethelgard/
├── aethelgard/               # The core Python package
│   ├── __init__.py
│   ├── core/                 # Abstract Base Classes (The "Ports")
│   │   ├── broker.py         # Defines TaskBroker interface
│   │   └── transport.py      # Defines ServerTransport & ClientTransport
│   ├── brokers/              # Concrete state managers (The "Adapters")
│   │   ├── in_memory.py      # For local testing (no dependencies)
│   │   └── redis_broker.py   # For production (requires Redis)
│   ├── transports/           # Concrete web servers/clients
│   │   ├── fastapi_server.py # REST/HTTP implementation
│   │   └── httpx_client.py   # Async HTTP client implementation
│   ├── orchestrator.py       # The central SuperLink logic
│   └── client_node.py        # The hospital SuperNode logic
├── samples/                 
│   ├── 01_local_simulation.py    # The minimal PoC - used only for internal logic tests 
│   ├── 02_production_server.py   # Integration tests
│   └── 03_gemma_pipeline.py      # Full semantic firewall pipeline
├── tests/
├── docker-compose.yml        # Instantly spins up the environment
├── pyproject.toml            # Modern Python packaging
└── README.md
```

---

## ⚡ Quick Start

### 1. Dev Environment Setup

Ensure you have the Google Cloud SDK installed and authenticated.

1. **Clone the repository**

```bash
git clone https://github.com/akaliutau/aethelgard.git
cd aethelgard
```

2. **Create and activate a Conda environment**

```bash
conda create -n aethelgard python=3.12 -y
conda activate aethelgard
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Install ollama and Gemma/CXR models**

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
ollama pull embeddinggemma
ollama pull gemma3:4b
# quick test
ollama run gemma3:4b "What is the capital of France?"
```

Auth for Gated Models (important since we are using CXR models - `google/cxr-foundation`!)

* Accept the Terms: You cannot download this anonymously. You must log in to Hugging Face, navigate to the `google/cxr-foundation` page, 
  and review the Health AI Developer Foundations terms of use. Once you click to agree, your access request is processed immediately.
* Generate a Token: Go to your Hugging Face account settings and generate an Access Token (Read permission) and store in `.env` file under HF


5. (optional) **Run the Editable Install**

```bash
pip install -e .
```

6. Build all images

```bash
sudo docker build -t aethelgard-server:latest .
sudo docker images
```

7. (optional) **Re-Generate datasets from scratch**

A. First we need to lift the limitations for Spot GPUs and models, from 0 -> 1:

* Go to the Google Cloud Console in your browser.
* Search for Quotas (IAM & Admin -> Quotas).
* In the Filter bar, paste exactly these metrics: custom_model_serving_nvidia_a100_80gb_gpus, CustomModelServingPreemptibleCPUsPerProjectPerRegion.
  and CustomModelServingPreemptibleA10080GBGPUsPerProjectPerRegion
* Ensure the location is set to us-central1.
* Select the checkbox next to the quota, click Edit Quotas, and request a limit of 1 (or 12 for CustomModelServingPreemptibleCPUsPerProjectPerRegion)

B. Generate a small dataset from CheXpert, using notebook `notebooks/dataset-small.ipynb` and unpack the archive to `.cache/CheXpert`

C. Deploy infra and run pipeline:

```bash
scripts/deploy_infra.sh
gcloud ai models list --region=us-central1
scripts/run_batch_gcp.sh .cache/CheXpert
```

The generated synthetic notes will be saved to /dataset.

To complete the data preparation, we must generate the embeddings for data, using scripts 



### 🚀 Running examples

First, we have to validate all workflow via running integration test

Run the following command to build and start the persistent Redis broker and super-link (the latter is available at http://localhost:8010/docs): 

```bash
sudo docker compose up --build --remove-orphans
sudo docker ps
```

It will start a container with redis, exposing `redis://localhost:6379` for requests.
A cache folder will automatically appear in your project directory containing the `/appendonlydir` data.

The super-link that should be available at `http://localhost:8010/docs`

If everything is green, run the demo app:

```bash
python samples/demo_app_2.py
```
Run

### 🏗️ How It Works (The Pure-Pull Workflow)

1. **Broadcast:** The global orchestrator drops a vectorized query into a secure mailbox (Broker).
2. **Pull:** The client node (behind a strict hospital firewall) wakes up on its 10-second heartbeat and asks, *"Do I have any mail?"*
3. **Local RAG:** The client executes a local vector search (e.g., LanceDB) and sanitizes the output.
4. **Upload:** The client pushes the safe, sanitized insight back to the orchestrator.

Text Embedding: Gemma 4B via Ollama

* Installation: Download the installer from ollama.com for your specific OS.
* Downloading the Model: Open your terminal and run ollama pull gemma:4b. This fetches the weights from the Ollama registry.
* Execution: Ollama runs a background service automatically. When `get_text_embedding()` function uses LiteLLM to hit `localhost:11434`, 
  Ollama dynamically loads the model into your RAM/VRAM, generates the 2048-dimensional vector, and unloads it after a period of inactivity.
* Cache Location: The model weights (typically a .gguf file) are cached securely on local disk:
** Linux: `/usr/share/ollama/.ollama/models`

Image Embedding: Google's CXR Foundation Models

The script currently mocks the 128-dimensional vision output using `google/siglip-base-patch16-224`. 
To swap this out for a dedicated medical foundation model (like Google's CXR models or similar open-weights variants), 
you utilize the transformers library which is already in your `requirements.txt`.

* Downloading the Model: When `AutoModel.from_pretrained("model-name")` is called, the transformers library automatically 
  connects to the Hugging Face Hub, downloads the model weights, and caches them locally.
* Execution: The script explicitly forces the model to run on the CPU (line DEVICE = "cpu"), which is highly compatible 
  but slower than using a GPU. The transformers library handles tokenization and passes the tensors through the network to generate the embeddings.
* Cache Location: By default, Hugging Face stores these large files in:
** Linux/macOS: `~/.cache/huggingface/hub`


### 🔌 Extending the Framework

Want to see it in action without configuring Redis? Run the local simulation in 3 lines of code:
```bash
pip install aethelgard
```


