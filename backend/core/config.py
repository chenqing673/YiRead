import json
import os

from utils.json_io import read_json
from core.runtime import APP_DIR

BASE_DIR = str(APP_DIR)
DATA_DIR = os.path.join(
    BASE_DIR,
    "data"
)
CONFIG_FILE = os.path.join(
    DATA_DIR,
    "config.json"
)

DEFAULT_CONFIG = {
    "data_dir": "data",
    "library_dir": "library",
    "translation_dir": "translation",
    "jobs_dir": "jobs"
}


def load_config():
    config = read_json(
        CONFIG_FILE
    )
    if not config:
        config = {}
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value
    return config


def get_config():
    return load_config()


def get_storage_path(name):
    config = load_config()
    base_dir = BASE_DIR
    data_dir = os.path.join(
        base_dir,
        config["data_dir"]
    )
    mapping = {
        "library": config["library_dir"],
        "translation": config["translation_dir"],
        "jobs": config["jobs_dir"]
    }
    sub_dir = mapping.get(
        name,
        name
    )
    return os.path.join(
        data_dir,
        sub_dir
    )


def get_data_path(name):
    return get_storage_path(
        name
    )
