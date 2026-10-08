import os
from core.config import get_data_path
from utils.json_io import read_json
def get_paper(
paper_id
):
    paper_file = os.path.join(
        get_data_path(
            "library"
        ),
        paper_id,
        "paper.json"
    )
    paper = read_json(
        paper_file
    )
    if not paper:
        return None
    return {
        "paper_id": paper_id,
        "pages": paper.get(
            "pages",
            []
        )
    }
