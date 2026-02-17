import asyncio
from typing import Callable, Awaitable
from aethelgard.core.transport import BaseClientTransport


class HospitalNode:
    """The localized edge node. Wakes up, works, sleeps."""

    def __init__(self, client_id: str, transport: BaseClientTransport, search_fn: Callable[[list], Awaitable[str]]):
        self.client_id = client_id
        self.transport = transport
        self.search_fn = search_fn  # Dependency Injection of the specific Local ML logic
        self.polling_interval = 5

    async def heartbeat_loop(self):
        print(f"[{self.client_id}] Started secure outbound heartbeat...")
        while True:
            tasks = await self.transport.poll_tasks(self.client_id)
            for task in tasks:
                req_id = task['request_id']
                print(f"[{self.client_id}] Processing Task: {req_id}")

                # Execute the Semantic Firewall (LanceDB + MedGemma)
                insight = await self.search_fn(task['query_vector'])

                # Securely return insight
                await self.transport.submit_insight(self.client_id, req_id, insight)
                print(f"[{self.client_id}] ✅ Insight securely uploaded.")

            await asyncio.sleep(self.polling_interval)