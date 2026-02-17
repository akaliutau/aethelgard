from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseTaskBroker(ABC):
    """
    Abstract interface for managing the state of queries and insights.
    """
    @abstractmethod
    async def enqueue_query(self, client_id: str, request_id: str, query_vector: List[float]):
        """Pushes a task to a specific client's queue."""
        pass

    @abstractmethod
    async def dequeue_queries(self, client_id: str) -> List[Dict[str, Any]]:
        """Pops all pending tasks for a specific client."""
        pass

    @abstractmethod
    async def save_insight(self, request_id: str, client_id: str, insight: str):
        """Saves a computed insight toward the global consensus."""
        pass