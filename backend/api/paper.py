from api.base import success, error
from storage.paper_reader import get_paper
def handle_paper(
handler,
paper_id
):
    paper = get_paper(
        paper_id
    )
    if not paper:
        error(
            handler,
            "paper not found",
            404
        )
        return
    success(
        handler,
        paper
    )
