import asyncio
from typing import List, Dict, Any
from aethelgard.core.broker import BaseTaskBroker

class InMemoryBroker(BaseTaskBroker):
    """Zero-dependency mock broker strictly for local testing/CI."""
    def __init__(self):
        self.queues: Dict[str, List[Dict[str, Any]]] = {}
        self.insights: Dict[str, List[Dict[str, Any]]] = {}
        self.lock = asyncio.Lock()

    async def enqueue_query(self, client_id: str, request_id: str, query_vector: List[float]) -> None:
        async with self.lock:
            if client_id not in self.queues:
                self.queues[client_id] = []
            self.queues[client_id].append({"request_id": request_id, "query_vector": query_vector})

    async def dequeue_queries(self, client_id: str) -> List[Dict[str, Any]]:
        async with self.lock:
            tasks = self.queues.get(client_id, [])
            self.queues[client_id] = []  # Clear after popping
            return tasks

    async def save_insight(self, request_id: str, client_id: str, insight: str) -> None:
        async with self.lock:
            if request_id not in self.insights:
                self.insights[request_id] = []
            self.insights[request_id].append({"client_id": client_id, "insight": insight})

    async def get_consensus(self, request_id: str) -> List[Dict[str, Any]]:
        async with self.lock:
            return self.insights.get(request_id, [])