import asyncio
import lancedb

from aethelgard.core.config import get_logger
from aethelgard.node import Node
from aethelgard.transports.httpx_client import HttpxClientTransport
from aethelgard.firewall.litellm_firewall import LiteLLMFirewall

# ==========================================
# Connect to the local LanceDB store
# ==========================================
NODE_ID="LOCAL_NODE"
DB_PATH = "./lancedb_store"
TABLE_NAME = "patients"
TEXT_MODEL = "ollama/gemma3:4b"
db = lancedb.connect(DB_PATH)

logger = get_logger(__name__)

async def lancedb_search(query_vector: list) -> str | None:
    """
    Searches LanceDB using the incoming fused vector.
    Returns the raw JSON metadata of the closest match.
    """
    try:
        table = db.open_table(TABLE_NAME)
        # Perform similarity search and grab the top 1 result
        results = table.search(query_vector).limit(1).to_pandas()
        if results.empty:
            return None

        # Return the raw, highly sensitive clinical text (metadata)
        return results.iloc[0]['metadata']
    except Exception as e:
        logger.error(f"Database search failed: {e}")
        return None


async def main():
    logger.info(f"Booting Hospital Node: {NODE_ID}")

    # Initialize the Semantic Firewall using LiteLLM + Local Ollama
    firewall = LiteLLMFirewall(
        model=TEXT_MODEL,
        api_base="http://localhost:11434",
        retriever_fn=lancedb_search,
        temperature=0.05 # min temperature to max security
    )

    transport = HttpxClientTransport(server_url="http://localhost:8010")

    # The firewall's sanitize() method natively matches the search_fn requirement
    node = Node(
        client_id="Hospital_A",
        transport=transport,
        search_fn=firewall.sanitize
    )

    logger.info("Listening for incoming federated queries...")
    await node.heartbeat_loop()


if __name__ == "__main__":
    asyncio.run(main())