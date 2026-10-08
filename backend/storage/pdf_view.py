"""PDF page rendering and paragraph geometry, without changing existing block IDs."""
import os
import re
import threading
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
import pymupdf
from core.config import get_data_path
from utils.json_io import read_json

# MuPDF objects must not be shared across concurrent HTTP worker threads.
PDF_LOCK = threading.RLock()

def normalized_rect(rect, page):
    rect = pymupdf.Rect(rect) * page.rotation_matrix
    bound = page.rect
    return [round(max(0, min(1, (rect.x0-bound.x0)/bound.width)),6),
            round(max(0, min(1, (rect.y0-bound.y0)/bound.height)),6),
            round(max(0, min(1, (rect.x1-bound.x0)/bound.width)),6),
            round(max(0, min(1, (rect.y1-bound.y0)/bound.height)),6)]


def source_path(paper_id):
    return os.path.join(get_data_path("library"), paper_id, "source.pdf")


def tokens(text):
    return re.findall(r"\w+", unicodedata.normalize('NFKC', text).casefold().replace('\u00ad',''))


def locate_legacy_blocks(page, blocks, within=None, word_geometry=None):
    # Match old pypdf text to actual PDF words; preserve IDs and existing translations.
    words = [word for word,box in word_geometry] if word_geometry is not None else page.get_text("words", sort=False)
    if within is not None:
        # Restrict repeated sentences to their known paragraph/column, not the whole page.
        filtered = []
        geometry=word_geometry if word_geometry is not None else ((word,normalized_rect(word[:4],page)) for word in words)
        for word,box in geometry:
            x,y=(box[0]+box[2])/2,(box[1]+box[3])/2
            if any(rect[0]-.002<=x<=rect[2]+.002 and rect[1]-.002<=y<=rect[3]+.002 for rect in within):filtered.append(word)
        words = filtered
    stream, locations = [], []
    for index, word in enumerate(words):
        for token in tokens(word[4]):
            stream.append(token); locations.append(index)
    starts={}
    for index,token in enumerate(stream):starts.setdefault(token,[]).append(index)
    used = set()
    results = []
    for block in blocks:
        if block.get("rects"):
            results.append({"id": block["id"], "rects": block["rects"]}); continue
        query = tokens(block.get("text", ""))
        matched = []
        if query:
            for start in starts.get(query[0],[]):
                if stream[start:start+len(query)] == query and not any(index in used for index in range(start,start+len(query))):
                    matched = list(range(start, start+len(query))); break
            if not matched and len(query) <= len(stream)*1.15:
                matcher = SequenceMatcher(None, query, stream, autojunk=False)
                pieces = matcher.get_matching_blocks()
                coverage = sum(piece.size for piece in pieces) / len(query)
                if coverage >= .85:
                    matched = [index for piece in pieces for index in range(piece.b,piece.b+piece.size) if index not in used]
                    # Reject sparse matches that jump through unrelated columns/paragraphs.
                    if len(matched) / len(query) < .85 or (matched and max(matched)-min(matched)+1 > max(len(query)*1.3,len(query)+3)):
                        matched = []
        used.update(matched)
        line_rects = {}
        for index in sorted(set(locations[position] for position in matched)):
            word = words[index]
            key = (word[5], word[6])
            if key not in line_rects:
                line_rects[key] = pymupdf.Rect(word[:4])
            else:
                line_rects[key] |= pymupdf.Rect(word[:4])
        results.append({"id": block["id"], "rects": [normalized_rect(rect, page) for rect in line_rects.values()]})
    return results


@lru_cache(maxsize=8)
def _layout(path, pdf_stamp, paper_file, paper_stamp):
    paper = read_json(paper_file)
    with PDF_LOCK, pymupdf.open(path) as document:
        pages = []
        for original in paper.get("pages", []):
            index = original["page"] - 1
            if not 0 <= index < len(document):
                continue
            page = document[index]
            pages.append({"page": index+1, "width":page.rect.width, "height":page.rect.height,
                          "blocks":locate_legacy_blocks(page, original.get("blocks", []))})
        return {"pages": pages}


def get_pdf_layout(paper_id):
    path = source_path(paper_id)
    paper_file = os.path.join(get_data_path("library"), paper_id, "paper.json")
    if not os.path.isfile(path) or not os.path.isfile(paper_file):
        return None
    return _layout(path, os.stat(path).st_mtime_ns, paper_file, os.stat(paper_file).st_mtime_ns)


@lru_cache(maxsize=6)
def _page_png(path, stamp, page_number):
    # An expendable, bounded disk cache supplements the small in-memory cache.
    import hashlib,time
    from pathlib import Path
    cache=Path(get_data_path('pdf_cache'))
    key=hashlib.sha256((os.path.abspath(path)+str(stamp)+'-png-v1-'+str(page_number)).encode()).hexdigest()
    saved=cache/(key+'.png')
    try:
        data=saved.read_bytes()
        if data.startswith(b'\x89PNG'):
            os.utime(saved,None);return data
    except OSError:pass
    with PDF_LOCK, pymupdf.open(path) as document:
        if not 1 <= page_number <= len(document):
            raise ValueError("page not found")
        page = document[page_number-1]
        scale = min(2.2, 2500/max(page.rect.width,page.rect.height), (6000000/(page.rect.width*page.rect.height))**.5)
        data=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale), alpha=False).tobytes("png")
        try:
            cache.mkdir(parents=True,exist_ok=True)
            temp=cache/(key+'-'+str(time.monotonic_ns())+'.tmp');temp.write_bytes(data);os.replace(temp,saved)
            entries=sorted(((p.stat().st_mtime,p.stat().st_size,p) for p in cache.glob('*.png')),reverse=True)
            size=0
            for index,(_,length,p) in enumerate(entries):
                size+=length
                if index>=128 or size>128*1024*1024:p.unlink(missing_ok=True)
        except OSError:pass  # Rendering remains available when caching is unavailable.
        return data


def render_pdf_page(paper_id, page_number):
    path = source_path(paper_id)
    if not os.path.isfile(path):
        return None
    return _page_png(path, os.stat(path).st_mtime_ns, page_number)
