import os
from core.config import get_data_path
from utils.json_io import read_json

def get_item(paper_id):
    file_path = os.path.join(
        get_data_path("library"),
        paper_id,
        "item.json"
    )
    return read_json(
        file_path
    )
