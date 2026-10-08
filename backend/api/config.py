from api.base import success
from core.config import load_config


def handle_config(handler):
    config = load_config()
    success(
        handler,
        {
            "config": config
        }
    )
