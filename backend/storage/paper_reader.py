import os
from functools import lru_cache
from core.config import get_data_path
from utils.json_io import read_json
from storage.reading_order import ordered_blocks
from storage.diagram_labels import pdf_labels, annotate_blocks, translatable, chemical_label

@lru_cache(maxsize=6)
def legacy_page_content(pdf_path,stamp):
    from storage.pdf_parser import parse_pdf
    return {page['page']:page['blocks'] for page in parse_pdf(pdf_path)['pages']}

def spans_columns(block):
    rects=block.get('rects',[])
    narrow=[r for r in rects if .12<r[2]-r[0]<.50]
    return bool(rects and max(r[2] for r in rects)-min(r[0] for r in rects)>.70
                and sum(r[2]<.51 for r in narrow)>=2 and sum(r[0]>.49 for r in narrow)>=2)
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
    pdf_path=os.path.join(get_data_path('library'),paper_id,'source.pdf')
    regions={};labels={}
    try:
        from storage.pdf_parser import pdf_reading_regions
        regions=pdf_reading_regions(pdf_path,os.stat(pdf_path).st_mtime_ns)
        labels=pdf_labels(pdf_path,os.stat(pdf_path).st_mtime_ns)
    except (OSError,RuntimeError,ValueError):pass
    # Early versions extracted a whole page into one record. Reconstruct its source
    # text in memory, preserving the record ID and all saved translations/notes.
    legacy=[page for page in pages if len(page.get('blocks',[]))==1 and
            ((not page['blocks'][0].get('rects') and len(page['blocks'][0].get('text',''))>1000) or spans_columns(page['blocks'][0]))]
    if legacy:
        try:
            parsed=legacy_page_content(pdf_path,os.stat(pdf_path).st_mtime_ns)
            reconstructed=[]
            for page in pages:
                if page in legacy and parsed.get(page['page']):
                    sources=[b for b in parsed[page['page']] if translatable(b)]
                    parent=page['blocks'][0]
                    parts=[dict(b,id=parent['id']+'__layout_'+b['id']) for b in sources]
                    page={**page,'blocks':[{**parent,'text':'\n\n'.join(b['text'] for b in sources),
                                          'rects':[r for b in sources for r in b['rects']], 'layout_sources':parts}]}
                reconstructed.append(page)
            pages=reconstructed
        except (OSError,RuntimeError,ValueError):pass
    display_pages=[]
    for page in pages:
        blocks=page.get('blocks',[])
        candidates=[b for b in blocks if not b.get('rects') and chemical_label(b.get('text',''))]
        if candidates and labels.get(page['page']):
            try:
                import pymupdf
                from storage.pdf_view import PDF_LOCK, locate_legacy_blocks
                with PDF_LOCK,pymupdf.open(pdf_path) as document:
                    found={b['id']:b['rects'] for b in locate_legacy_blocks(document[page['page']-1],candidates)}
                blocks=[dict(b,rects=found[b['id']]) if b['id'] in found else b for b in blocks]
            except (OSError,RuntimeError,ValueError):pass
        display_pages.append({**page,'blocks':ordered_blocks(annotate_blocks(blocks,labels.get(page['page'],[])),**regions.get(page['page'],{}))})
    return {
        "paper_id": paper_id,
        "pages": display_pages
    }
