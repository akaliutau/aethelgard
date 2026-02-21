import argparse
import asyncio
import os

from dotenv import load_dotenv

from aethelgard.brokers.redis_broker import RedisBroker
from aethelgard.transports.fastapi_server import FastAPIServer

async def main(env_file: str):
    # Load the specific profile passed via CLI
    load_dotenv(env_file, override=False)
    port = int(os.getenv("SERVER_PORT"))

    broker = RedisBroker(redis_url=os.getenv("REDIS_URL"))
    server = FastAPIServer(broker=broker)

    await server.run(host=os.getenv("SERVER_HOST"), port=port)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aethelgard Server")
    parser.add_argument("--config", type=str, default=".env", help="Path to the .env profile")
    args = parser.parse_args()
    asyncio.run(main(args.config))