import asyncio
from typing import Callable, Awaitable

from aethelgard.core.config import get_logger
from aethelgard.core.transport import BaseClientTransport

logger = get_logger(__name__)

class Node:
    """The localized edge node. Wakes up, works, sleeps."""

    def __init__(self, client_id: str, transport: BaseClientTransport, search_fn: Callable[[list], Awaitable[str | None]]):
        self.client_id = client_id
        self.transport = transport
        self.search_fn = search_fn  # Dependency Injection of the specific Local ML logic
        self.polling_interval = 5

    async def heartbeat_loop(self):
        logger.info(f"[{self.client_id}] Started secure outbound heartbeat...")
        while True:
            tasks = await self.transport.poll_tasks(self.client_id)
            for task in tasks:
                req_id = task['request_id']
                logger.info(f"[{self.client_id}] Processing Task: {req_id}")

                try:
                    # Execute the Semantic Firewall
                    insight = await self.search_fn(task['query_vector'])

                    if insight is not None:
                        await self.transport.submit_insight(self.client_id, req_id, insight)
                        logger.info(f"[{self.client_id}] ✅ Insight securely uploaded.")
                    else:
                        logger.info(f"[{self.client_id}] ⚪ No relevant data found.")

                except Exception as e:
                    logger.error(f"[{self.client_id}] ❌ Error processing task {req_id}: {e}")
                    continue  # Do NOT ack if processing catastrophically failed

                finally:
                    # ALWAYS explicitly ACK after successful processing (even if no insight found)
                    await self.transport.ack(self.client_id, req_id)
                    logger.info(f"[{self.client_id}] 🔒 Task {req_id} acknowledged.")

            await asyncio.sleep(self.polling_interval)