from api.base import success, error
from storage.item import get_item

def handle_item(handler, paper_id):
    item = get_item(
        paper_id
    )
    if not item:
        error(
            handler,
            "item not found",
            404
        )
        return
    success(
        handler,
        item
    )
