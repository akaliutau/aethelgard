import asyncio
from aethelgard.node import HospitalNode
from aethelgard.transports.httpx_client import HttpxClientTransport
from aethelgard.firewall.litellm_firewall import LiteLLMFirewall


# 1. Define your local database search function (e.g., LanceDB)
async def my_lancedb_search(query_vector: list) -> str:
    # Assume lancedb logic here...
    return "Patient John Doe, 45, treated with Albuterol for severe Asthma at Stanford Hospital."


# 2. Initialize the Semantic Firewall Adapter (Using local Ollama)
firewall = LiteLLMFirewall(
    model="ollama/gemma",  # Tell LiteLLM to route locally
    api_base="http://0.0.0.0:11434",  # Standard Ollama port
    retriever_fn=my_lancedb_search  # Inject the DB logic
)


# 3. Boot the Node
async def main():
    transport = HttpxClientTransport(server_url="http://localhost:8000")

    # The firewall's sanitize() method natively matches the required Callable signature!
    node = HospitalNode(client_id="Hospital_A", transport=transport, search_fn=firewall.sanitize)

    await node.heartbeat_loop()


if __name__ == "__main__":
    asyncio.run(main())