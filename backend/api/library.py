from api.base import success
from storage.library import list_library
from storage.translation_status import (
    get_translation_status
)


def handle_library(handler):
    from urllib.parse import urlparse, parse_qs
    query = urlparse(
        handler.path
    ).query
    params = parse_qs(
        query
    )
    keyword = params.get(
        "q",
        [""]
    )[0]
    papers = list_library(
        keyword
    )
    items = []
    for item in papers:
        translation_status = (
            get_translation_status(
                item["id"]
            )
        )
        item["translation_status"] = (
            translation_status
        )
        items.append(item)
    success(
        handler,
        {
            "count": len(items),
            "items": items
        }
    )
