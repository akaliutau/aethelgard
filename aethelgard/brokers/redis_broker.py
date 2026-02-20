import json
from typing import List, Dict, Any
from aethelgard.core.broker import BaseTaskBroker
import redis.asyncio as redis

class RedisBroker(BaseTaskBroker):
    """Production broker using Redis for distributed state management."""
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        print("starting redis broker")

    async def enqueue_query(self, client_id: str, request_id: str, query_vector: List[float]) -> None:
        task = {"request_id": request_id, "query_vector": query_vector}
        await self.redis.lpush(f"queue:{client_id}", json.dumps(task))

    async def dequeue_queries(self, client_id: str) -> List[Dict[str, Any]]:
        tasks = []
        source_queue = f"queue:{client_id}"
        processing_queue = f"processing:{client_id}"

        while True:
            # Atomically move from main queue to processing queue
            task_data = await self.redis.lmove(source_queue, processing_queue, "RIGHT", "LEFT")
            if not task_data:
                break
            tasks.append(json.loads(task_data))
        return tasks

    async def ack(self, client_id: str, request_id: str) -> None:
        """Removes the task from the processing queue once explicitly acknowledged."""
        processing_queue = f"processing:{client_id}"

        # We need to find and remove the specific task.
        # In a high-throughput system, Redis Streams (XACK) is better,
        # but for this list-based architecture, LREM works perfectly.
        tasks = await self.redis.lrange(processing_queue, 0, -1)
        for task_data in tasks:
            task = json.loads(task_data)
            if task["request_id"] == request_id:
                await self.redis.lrem(processing_queue, 1, task_data)
                break

    async def save_insight(self, request_id: str, client_id: str, insight: str) -> None:
        payload = {"client_id": client_id, "insight": insight}
        await self.redis.lpush(f"request:{request_id}:insights", json.dumps(payload))

    async def get_consensus(self, request_id: str) -> List[Dict[str, Any]]:
        raw_insights = await self.redis.lrange(f"request:{request_id}:insights", 0, -1)
        return [json.loads(i) for i in raw_insights]