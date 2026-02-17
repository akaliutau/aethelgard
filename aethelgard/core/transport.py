from abc import ABC, abstractmethod
from aethelgard.core.broker import BaseTaskBroker

class BaseServerTransport(ABC):
    """
    Abstract interface for the network layer receiving requests.
    """
    def __init__(self, broker: BaseTaskBroker):
        # Dependency Injection: The transport relies on the broker to manage state
        self.broker = broker

    @abstractmethod
    async def start(self, host: str, port: int):
        """Bootstraps the network listener (e.g., uvicorn.run for FastAPI)."""
        pass