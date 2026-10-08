import pymupdf
from storage.pdf_view import PDF_LOCK, normalized_rect


def parse_pdf(pdf_path):
    with PDF_LOCK, pymupdf.open(pdf_path) as document:
        if document.needs_pass:
            raise ValueError("encrypted PDF requires a password")
        pages = []
        for page_index, page in enumerate(document):
            blocks = []
            for block in page.get_text("dict", sort=True)["blocks"]:
                if block.get("type") != 0:
                    continue
                lines = block.get("lines", [])
                text = "\n".join("".join(span["text"] for span in line["spans"]) for line in lines).strip()
                if not text:
                    continue
                blocks.append({"id":f"p{page_index+1}_b{len(blocks)+1}", "text":text,
                               "rects":[normalized_rect(line["bbox"],page) for line in lines]})
            pages.append({"page":page_index+1,"width":page.rect.width,"height":page.rect.height,"blocks":blocks})
        return {"meta":{"page_count":len(document),"geometry_version":1},"pages":pages}
