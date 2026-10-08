import os

from core.config import (
    load_config,
    get_data_path
)


def init_data():
    config = load_config()
    library_dir = config.get(
        "library_dir",
        "library"
    )
    library_path = get_data_path("library")
    os.makedirs(
        library_path,
        exist_ok=True
    )
    return library_path
