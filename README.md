# 🛡️ Aethelgard: Decentralized Clinical Intelligence via Federated RAG

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
<img src="docs/assets/local_intelligence_node.png" width="85%" alt="Local Intelligence Node" />

<em>Figure 1: The concept of UI for the Local Intelligence Node (`samples/demo_app.py`). The current variant is built on the basis of NiceGUI</em>
</p>


### ✨ Key Features

* **Pure-Pull Architecture:** Edge nodes use outbound asynchronous polling. **Zero inbound port-forwarding required** by IT departments.
* **100% Pluggable:** Ships with FastAPI and Redis defaults, but core abstractions allow easy swapping to gRPC, Kafka, AWS SQS, or GCP Pub/Sub.
* **Semantic Firewall Ready:** Designed to easily integrate local LLM verification (e.g., MedGemma) to sanitize vector search 
results before they are transmitted back to the global orchestrator.

### 🏗️ Architecture 

<p align="center">
<img src="docs/assets/Diagram_1.png" width="75%" alt="Architecture of Aethelgard" />

<em>Figure 2: The abstract System Design of our protocol. Super-link is built on the basis of message queue</em>
</p>

### 🌌 The Vision

Solving the rare disease "Diagnostic Odyssey" requires more than a single application; it requires a paradigm shift in how 
clinical systems communicate. Healthcare is notoriously fragmented. Every hospital has a unique IT infrastructure, 
differing firewall policies, and strict, incompatible data governance laws (HIPAA, GDPR, etc.).

**We did not build an app. We built a protocol.**

Aethelgard is designed as a foundational **Federated Retrieval-Augmented Generation (FedRAG) Framework**. 
Applications are brittle and siloed; protocols scale. 
We engineered Aethelgard to act as the decentralized nervous system for clinical intelligence:
* **Agnostic to the UI:** Whether a hospital uses Epic, Cerner, or a custom legacy Electronic Health Record (EHR) system, 
  Aethelgard operates at the infrastructure layer, allowing local apps to hook into the global network seamlessly.
* **Adaptable to any IT Environment:** Built on strict Hexagonal Architecture, the core geometric and AI logic is completely 
  decoupled from the transport layer. 
* **Beyond Diagnostics:** While our primary demonstration focuses on rare disease diagnostics, the Aethelgard protocol can be 
  instantly adapted for pharmacovigilance (detecting rare adverse drug reactions globally), multi-center clinical trial matching, 
  and real-time epidemiological tracking - all without moving a single row of raw data.

### 🧮 Security Innovation: Empirical Noise vs. LDP

The most significant technical hurdle in Federated RAG is ensuring that transmitted semantic vectors cannot be reverse-engineered 
to reveal patient Protected Health Information (PHI). 

Our empirical evaluation of 1920-dimensional clinical vectors revealed that strict Local Differential Privacy (LDP) is 
mathematically incompatible with exact Top-1 retrieval utility in high-dimensional spaces. 
Applying standard LDP collapsed Top-1 retrieval accuracy to under 10%. 

To resolve this, Aethelgard utilizes an **Empirical Noise Strategy**. 
By applying a controlled Gaussian noise ($\sigma=0.2$) directly to the vectors, we degrade the raw vector similarity to 0.116 
(rendering exact inversion mathematically impossible) while perfectly preserving the relative spatial geometry. 

**Result:** 100% Top-1 Retrieval Accuracy across the network with zero raw data exposure.

👉 **[Privacy-Utility Trade-off Analysis](notebooks/LDP_and_Empirical_Noise_Parameter_Selection_Analysis.ipynb)** 
👉 **[Paper Draft](docs/Privacy_Utility_Tradeoff_Analysis.pdf)** 


## 📂 Project Structure

The codebase is organized to separate infrastructure from implementation logic.

Here are the main components:
```text
aethelgard/
├── aethelgard/                   # The core Python package
│   ├── __init__.py
│   ├── core/                     # Abstract Base Classes & Core Utilities (The "Ports")
│   │   ├── broker.py             # Defines the BaseTaskBroker interface
│   │   ├── config.py             # Global logging and environment configuration
│   │   ├── llm_middleware.py     # Model-agnostic LLM routing (powered by LiteLLM)
│   │   ├── smartfolder.py        # SQLite-based state tracker for local file changes
│   │   └── transport.py          # Defines ServerTransport & ClientTransport interfaces
│   ├── brokers/                  # Concrete state managers (The "Adapters")
│   │   └── redis_broker.py       # Distributed task queue implementation using Redis
│   ├── firewall/                 # Security & Sanitization
│   │   └── litellm_firewall.py   # The MedGemma-powered generative sanitization adapter
│   ├── transports/               # Concrete network protocols
│   │   ├── fastapi_server.py     # REST/HTTP Orchestrator API implementation
│   │   └── httpx_client.py       # Async HTTP client for outbound node polling
│   └── node.py                   # The Edge Node heartbeat and execution loop
├── pipeline/                     # Scripts for GCP batch inference and data prep - 
│                                 #     only if a new dataset for experiments is needed
├── profiles/                     # .env configuration files for different network nodes
├── samples/                      # Demonstration scripts and interactive UIs
│   ├── demo_app.py             # The example of interactive clinician app built on NiceGUI
│   ├── test_integration.py       # Full network broadcast and consensus simulation for smoke tests
│   └── ...
├── tests/                        # Unit and integration test suite
├── docker-compose.yml            # Instantly spins up the Redis & FastAPI Orchestrator
├── Dockerfile                    # Container definition for the SuperLink server
├── pyproject.toml                # Modern Python packaging configuration
└── README.md```
```

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

4. **Install ollama and Gemma/embedding models**

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
ollama pull embeddinggemma
ollama pull gemma3:4b
# quick test
ollama run gemma3:4b "What is the capital of France?"
```
Cache Location: The model weights (typically a .gguf file) are cached securely on local disk:
** Linux: `/usr/share/ollama/.ollama/models`


NOTE: Extra steps for using Gated Models

* Accept the Terms: You cannot download these models anonymously. If they are hosted at Hugging Face, you must log in to Hugging Face, navigate to the model card page, 
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

Note: this step is only needed if you need to re-create dataset for your experiments.
See the instructions in [dedicated page](dataset/readme.md)


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


In other terminal run the local node using profile for the Hospital B:

```bash
python samples/03_hospital_node.py --config profiles/node_b.env
```

If everything is green, run the demo app using profile for the Hospital A:

```bash
python samples/demo_app.py --config profiles/node_a.env
```
The UI page of application will automatically open in browser.

### 🏗️ How It Works (The Pure-Pull Workflow)

1. **Broadcast:** The global orchestrator drops a vectorized query into a secure mailbox (Broker).
2. **Pull:** The client node (behind a strict hospital firewall) wakes up on its 10-second heartbeat and asks, *"Do I have any mail?"*
3. **Local RAG:** The client executes a local vector search (e.g., LanceDB) and sanitizes the output.
4. **Upload:** The client pushes the safe, sanitized insight back to the orchestrator (super-link on the diagram).


## 🚀 Future Roadmap: Scaling Aethelgard

Aethelgard is a foundation ready for enterprise scaling. Our immediate roadmap focuses on making the protocol completely invisible to the end-user while expanding its security and interoperability:

- [ ] **Native OS Daemon & Zero-Touch Ollama Integration:** Package the Aethelgard edge node as a lightweight, 
        headless background service (e.g., `systemd` for Linux, Windows Service). 
        This daemon will natively orchestrate local Ollama instances, dynamically loading and unloading MedGemma weights 
        and managing the inference lifecycle automatically - requiring zero technical overhead or terminal usage from clinicians.
- [ ] **Automated FHIR/HL7 EHR Ingestion:** Build native data pipelines to continuously ingest, vectorize, and index clinical notes and 
        imaging directly from standard Electronic Health Record (EHR) systems (like Epic and Cerner) in real-time, completely replacing manual data uploads.
- [ ] **Enterprise Message Brokers:** Expand the `BaseTaskBroker` port beyond Redis. Ship drop-in adapters for state-scale deployments using 
        **Apache Kafka**, **GCP Pub/Sub**, or **AWS SQS** with zero changes to the core geometric logic.
- [ ] **Hardware-Level Enclaves (TEE):** Integrate Trusted Execution Environments (e.g., Intel SGX, AMD SEV) for the SuperLink Message Queue 
        to guarantee mathematically and at the hardware level that the centralized routing infrastructure cannot inspect even the heavily obfuscated query vectors.
- [ ] **Specialized Multi-Agent Semantic Firewalls:** Evolve the single MedGemma instance into a local multi-agent system. Deploy specialized 
        sub-agents for distinct tasks (e.g., a Genomic Privacy Agent, a Radiographic Reasoning Agent) that debate and synthesize the final, hyper-secure outbound payload.
- [ ] **gRPC Multiplexing:** Upgrade the FastAPI/HTTPX transports to multiplexed **gRPC** to support low-latency, high-volume vector polling 
        across tens of thousands of concurrent hospital nodes globally.


## ⚖️ License

Project Aethelgard is open-source software distributed under the **MIT License**. 

By keeping the core routing and security protocol open and accessible, we aim to lower the barrier to entry for underfunded 
rural clinics and state-scale hospital networks alike. See the [LICENSE](LICENSE) file for more details.

---
*Built for the [MedGemma Impact Challenge](https://www.kaggle.com/competitions/med-gemma-impact-challenge/writeups/project-aethelgard-decentralized-clinical-intelli) organized by Google Research.* <br>
*Sharing knowledge to save lives.*


