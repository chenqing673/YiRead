from api.base import success
from storage.translation_status import (
    get_translation_status
)

def handle_translation_status(
    handler,
    paper_id
):
    status = get_translation_status(
        paper_id
    )
    success(
        handler,
        status
    )
