import os
from storage.pdf_parser import parse_pdf
from utils.json_io import write_json_atomic


def create_paper_json(paper_dir):
    pdf_path = os.path.join(paper_dir, "source.pdf")
    data = parse_pdf(pdf_path)
    data["id"] = os.path.basename(paper_dir)
    paper_json = os.path.join(paper_dir, "paper.json")
    write_json_atomic(paper_json, data)
    return data
