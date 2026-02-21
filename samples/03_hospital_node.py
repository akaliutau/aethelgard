import argparse
import asyncio
import os
import lancedb

from dotenv import load_dotenv
from aethelgard.core.config import get_logger
from aethelgard.node import Node
from aethelgard.transports.httpx_client import HttpxClientTransport
from aethelgard.firewall.litellm_firewall import LiteLLMFirewall

logger = get_logger(__name__)

async def main(env_file: str):
    load_dotenv(env_file, override=True)

    # 1. Load configurations
    node_id = os.getenv("NODE_ID")
    table_name = os.getenv("TABLE_NAME")
    # 2. Connect to local LanceDB using the dynamic path
    db = lancedb.connect(uri=os.getenv("DB_PATH"))

    logger.info(f"Booting Hospital Node: {node_id}")

    async def lancedb_search(query_vector: list) -> str | None:
        """
        Searches LanceDB using the incoming fused vector.
        Returns the raw JSON metadata of the closest match.
        """
        try:
            table = db.open_table(table_name)
            # Perform similarity search and grab the top 1 result
            results = table.search(query_vector).limit(1).to_pandas()
            if results.empty:
                return None

            # Return the raw, highly sensitive clinical text (metadata)
            return results.iloc[0]['metadata']
        except Exception as e:
            logger.error(f"Database search failed: {e}")
            return None

    # Initialize the Semantic Firewall using LiteLLM + Local Ollama
    firewall = LiteLLMFirewall(
        model=os.getenv("TEXT_MODEL"),
        api_base=os.getenv("LLM_API_BASE"),
        retriever_fn=lancedb_search,
        temperature=0.05 # min temperature to max security
    )

    transport = HttpxClientTransport(server_url=os.getenv("SERVER_URL"))

    # The firewall's sanitize() method natively matches the search_fn requirement
    node = Node(
        client_id=node_id,
        transport=transport,
        search_fn=firewall.sanitize
    )

    logger.info("Listening for incoming federated queries...")
    await node.heartbeat_loop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aethelgard Hospital Node")
    parser.add_argument("--config", type=str, default=".env", help="Path to the .env profile")
    args = parser.parse_args()
    asyncio.run(main(args.config))