import os
from core.config import get_data_path
from utils.json_io import write_json_atomic
from utils.json_io import read_json


def get_translation_path():
    path = get_data_path(
        "translation"
    )
    os.makedirs(
        path,
        exist_ok=True
    )
    return path


def save_translation(
    paper_id,
    blocks,
    **metadata
):
    data = {
        "paper_id": paper_id,
        "blocks": blocks,
        **metadata
    }
    file_path = os.path.join(
        get_translation_path(),
        paper_id + ".json"
    )
    write_json_atomic(
        file_path,
        data
    )
    return data


def get_translation(
    paper_id
):
    file_path = os.path.join(
        get_translation_path(),
        paper_id + ".json"
    )
    return read_json(
        file_path
    )
