import logging
from pathlib import Path
import colorlog
from colorlog import ColoredFormatter
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "dataset"
CACHE_DIR = ROOT_DIR / ".cache"

LOG_LEVEL = "INFO"
APP_VERSION = "0.1.0"

print(f"Project Root Directory: {ROOT_DIR}")
print(f"DATA_DIR Directory: {DATA_DIR}")

handler = colorlog.StreamHandler()
handler.setFormatter(ColoredFormatter(
    '%(log_color)s%(asctime)s - %(levelname)s - %(message)s',
    log_colors={
        'INFO': 'green',
        'DEBUG': 'cyan',
        'WARNING': 'yellow',
        'ERROR': 'red'
    }
))

def get_logger(module_name: str):
    logger = colorlog.getLogger(module_name)
    logger.addHandler(handler)
    logger.setLevel(level=logging.DEBUG)
    return logger

# logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

def mute_openai_logging(level=logging.WARNING):
    # Silence third‑party libraries used by the OpenAI client
    for name in (
            "LiteLLM",  # primary LiteLLM logger
            "litellm",  # some modules may use package name
            "litellm.utilities",
            "litellm.router",
            "litellm.proxy",
            "openai",
            "litellm",
            "httpx",
            "httpcore",
            "pydantic"
    ):
        lg = logging.getLogger(name)
        lg.setLevel(level)  # Hide INFO; show only WARNING/ERROR/CRITICAL
        lg.propagate = False  # Prevent bubbling to the root handlers


mute_openai_logging()

def configure():
    pass