from api.base import success, error
from storage.translation import (
    get_translation_result
)
from storage.reading_alignment import attach_reading_units
from storage.translation_store import translation_revision


def handle_translation_result(handler, paper_id):
    result = get_translation_result(
        paper_id
    )
    if not result:
        error(
            handler,
            "translation not found",
            404
        )
        return
    result['revision']=translation_revision(result)
    success(
        handler,
        attach_reading_units(paper_id,result)
    )
