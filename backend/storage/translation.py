from storage.translation_store import (
    get_translation
)


def get_translation_result(
    paper_id
):
    translation = get_translation(
        paper_id
    )
    if not translation:
        return None
    return translation
