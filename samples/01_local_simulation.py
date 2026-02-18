import asyncio
from aethelgard.brokers.in_memory import InMemoryBroker
from aethelgard.transports.fastapi_server import FastAPITransport
from aethelgard.orchestrator import FedRagOrchestrator
from aethelgard.node import HospitalNode
from aethelgard.core.transport import BaseClientTransport


# A mock transport that talks directly to memory (bypassing HTTP for simulation)
class InMemoryClientTransport(BaseClientTransport):
    def __init__(self, broker: InMemoryBroker):
        self.broker = broker

    async def poll_tasks(self, client_id): return await self.broker.dequeue_queries(client_id)

    async def submit_insight(self, client_id, request_id, insight): await self.broker.save_insight(request_id,
                                                                                                   client_id, insight)


async def mock_local_rag(query_vector):
    await asyncio.sleep(1)  # Simulating GPU time
    return "Sanitized local insight: Match found."


async def main():
    broker = InMemoryBroker()
    server = FedRagOrchestrator(FastAPITransport(broker))
    client_transport = InMemoryClientTransport(broker)

    node_a = HospitalNode("Hospital_A", client_transport, mock_local_rag)
    node_b = HospitalNode("Hospital_B", client_transport, mock_local_rag)

    # Simulate an automated clinician request
    async def simulate_query():
        await asyncio.sleep(3)
        print("\n[Clinician] Submitting Query to SuperLink...")
        await broker.enqueue_query("Hospital_A", "req_123", [0.1, 0.2, 0.3])
        await asyncio.sleep(3)
        print("\n[Clinician] Global Consensus:", await broker.get_consensus("req_123"))

    await asyncio.gather(
        server.run("127.0.0.1", 8000),
        node_a.heartbeat_loop(),
        node_b.heartbeat_loop(),
        simulate_query()
    )


if __name__ == "__main__":
    asyncio.run(main())