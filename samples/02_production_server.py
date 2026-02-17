import asyncio
from aethelgard.brokers.redis_broker import RedisBroker
from aethelgard.transports.fastapi_server import FastAPITransport
from aethelgard.orchestrator import FedRagOrchestrator


async def main():
    broker = RedisBroker(redis_url="redis://localhost:6379")
    transport = FastAPITransport(broker=broker)
    server = FedRagOrchestrator(transport=transport)

    await server.run(host="0.0.0.0", port=8000)


if __name__ == "__main__":
    asyncio.run(main())