import os
from functools import lru_cache
from core.config import get_data_path
from utils.json_io import read_json
from storage.reading_order import ordered_blocks

@lru_cache(maxsize=6)
def legacy_page_content(pdf_path,stamp):
    from storage.pdf_parser import parse_pdf
    return {page['page']:page['blocks'] for page in parse_pdf(pdf_path)['pages']}
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
    pages=paper.get('pages',[])
    # Early versions extracted a whole page into one record. Reconstruct its source
    # text in memory, preserving the record ID and all saved translations/notes.
    legacy=[page for page in pages if len(page.get('blocks',[]))==1 and not page['blocks'][0].get('rects') and len(page['blocks'][0].get('text',''))>1000]
    if legacy:
        pdf_path=os.path.join(get_data_path('library'),paper_id,'source.pdf')
        try:
            parsed=legacy_page_content(pdf_path,os.stat(pdf_path).st_mtime_ns)
            pages=[{**page,'blocks':[{**page['blocks'][0],'text':'\n\n'.join(b['text'] for b in parsed[page['page']]),'rects':[r for b in parsed[page['page']] for r in b['rects']]}]} if page in legacy and parsed.get(page['page']) else page for page in pages]
        except (OSError,RuntimeError,ValueError):pass
    return {
        "paper_id": paper_id,
        "pages": [{**page,'blocks':ordered_blocks(page.get('blocks',[]))} for page in pages]
    }
