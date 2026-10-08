import os
import json

from core.config import get_data_path
from core.config import load_config


def get_library_path():
    config = load_config()
    library_dir = config.get(
        "library_dir",
        "library"
    )
    return get_data_path("library")


def list_library(
        keyword=""
):
    library_path = get_library_path()
    papers = []
    if not os.path.exists(library_path):
        return papers
    for item in os.listdir(library_path):
        item_path = os.path.join(
            library_path,
            item
        )
        if not os.path.isdir(item_path):
            continue
        json_file = os.path.join(
            item_path,
            "item.json"
        )
        if not os.path.exists(json_file):
            continue
        try:
            with open(
                json_file,
                "r",
                encoding="utf-8"
            ) as f:
                data = json.load(f)
            if keyword:
                title = data.get(
                    "title",
                    ""
                )
                file_name = data.get(
                    "file_name",
                    ""
                )
                if (
                    keyword.lower()
                    not in title.lower()
                    and
                    keyword.lower()
                    not in file_name.lower()
                ):
                    continue
            papers.append(data)
        except Exception:
            continue
    return papers
