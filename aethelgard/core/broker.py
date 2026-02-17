import abc
from typing import List, Dict, Any


class BaseTaskBroker(abc.ABC):
    """Abstract interface for managing the state of queries and insights."""

    @abc.abstractmethod
    async def enqueue_query(self, client_id: str, request_id: str, query_vector: List[float]) -> None:
        """Pushes a task to a specific client's queue."""
        pass

    @abc.abstractmethod
    async def dequeue_queries(self, client_id: str) -> List[Dict[str, Any]]:
        """Pops all pending tasks for a specific client."""
        pass

    @abc.abstractmethod
    async def save_insight(self, request_id: str, client_id: str, insight: str) -> None:
        """Saves a computed insight toward the global consensus."""
        pass

    @abc.abstractmethod
    async def get_consensus(self, request_id: str) -> List[Dict[str, Any]]:
        """Retrieves all aggregated insights for a specific query."""
        pass