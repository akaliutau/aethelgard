import abc
from aethelgard.core.broker import BaseTaskBroker

class BaseServerTransport(abc.ABC):
    """Abstract interface for the network layer receiving and routing requests."""
    def __init__(self, broker: BaseTaskBroker):
        # Dependency Injection: Transport relies on Broker
        self.broker = broker

    @abc.abstractmethod
    async def start(self, host: str, port: int) -> None:
        pass

class BaseClientTransport(abc.ABC):
    """Abstract interface for the client-side outbound poller."""
    @abc.abstractmethod
    async def poll_tasks(self, client_id: str) -> list:
        pass

    @abc.abstractmethod
    async def submit_insight(self, client_id: str, request_id: str, insight: str) -> None:
        pass