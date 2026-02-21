import asyncio

from aethelgard.brokers.redis_broker import RedisBroker
from aethelgard.transports.fastapi_server import FastAPIServer

async def main():
    broker = RedisBroker(redis_url="redis://localhost:6379")
    server = FastAPIServer(broker=broker)
    await server.run(host="0.0.0.0", port=8010)

if __name__ == "__main__":
    asyncio.run(main())