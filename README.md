# 🛡️ Aethelgard

**Aethelgard** is a lightweight, pure-pull Federated Retrieval-Augmented Generation (FedRAG) framework. It allows you to query highly sensitive, distributed vector databases (like clinical patient data) without ever moving raw data or opening inbound corporate firewalls.
Unlike traditional federated learning frameworks that focus on *training* models across silos, Aethelgard focuses strictly on *inference and routing*.

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

4. (optional) **Run the Editable Install**

```bash
pip install -e .
```



### 🚀 Running examples (In-Memory Simulation)


Want to see it in action without configuring Redis? Run the local simulation in 3 lines of code:
```bash
pip install aethelgard
```


### 🏗️ How It Works (The Pure-Pull Workflow)

1. **Broadcast:** The global orchestrator drops a vectorized query into a secure mailbox (Broker).
2. **Pull:** The client node (behind a strict hospital firewall) wakes up on its 30-second heartbeat and asks, *"Do I have any mail?"*
3. **Local RAG:** The client executes a local vector search (e.g., LanceDB) and sanitizes the output.
4. **Upload:** The client pushes the safe, sanitized insight back to the orchestrator.



### 🔌 Extending the Framework



