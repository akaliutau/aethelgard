import asyncio
import logging
import colorlog
from aethelgard.brokers.redis_broker import RedisBroker
from aethelgard.transports.fastapi_server import FastAPIServer


def setup_logging():
    """Sets up beautiful colored logging for the terminal."""
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    ))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


async def main():
    setup_logging()

    broker = RedisBroker(redis_url="redis://localhost:6379")
    server = FastAPIServer(broker=broker)
    await server.run(host="0.0.0.0", port=8010)


if __name__ == "__main__":
    asyncio.run(main())