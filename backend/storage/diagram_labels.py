"""Identify chemical labels using both notation and nearby PDF bond geometry.

Labels stay in the original PDF. Classification is read-only and keeps record IDs;
letters in prose, abbreviations without bonds and table headings are not excluded.
"""
import re
import unicodedata
from functools import lru_cache

import pymupdf
from storage.pdf_view import PDF_LOCK, normalized_rect

ATOM = re.compile(r'(?:(?:Cl|Br|Si|Na|Li|Mg|Ca|Zn|Fe|Cu|Me|Et|Ph|Ac|Bn|Boc|[CHNOSPFBIKR])\d*|[()+−\-·=])+$')


def chemical_label(text):
    text = re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))
    return bool(text and len(text) <= 24 and re.search(r'[A-Za-z]', text) and ATOM.fullmatch(text))


def page_labels(page):
    lines = []
    for drawing in page.get_drawings():
        for item in drawing['items']:
            if item[0] != 'l':
                continue
            a, b = item[1:3]
            length = abs(a-b)
            if 2 <= length <= 50:
                lines.append((pymupdf.Rect(min(a.x,b.x),min(a.y,b.y),max(a.x,b.x),max(a.y,b.y)), abs(a.x-b.x)>2 and abs(a.y-b.y)>2))
    images = [pymupdf.Rect(image['bbox']) for image in page.get_image_info()]
    labels = []
    for block in page.get_text('dict')['blocks']:
        if block.get('type') != 0:
            continue
        groups=[]
        for line in block['lines']:
            group=[]
            for span in sorted(line['spans'],key=lambda s:s['bbox'][0]):
                if group and span['bbox'][0]-group[-1]['bbox'][2]>max(18,span['size']*2.5):
                    groups.append(group);group=[]
                group.append(span)
            if group:groups.append(group)
        for spans in groups:
            text = ''.join(s['text'] for s in spans).strip()
            box = pymupdf.Rect(spans[0]['bbox'])
            for span in spans[1:]:box|=pymupdf.Rect(span['bbox'])
            if not chemical_label(text) or box.width > 75 or box.height > 35:
                continue
            close = pymupdf.Rect(box.x0-18,box.y0-18,box.x1+18,box.y1+18)
            context = pymupdf.Rect(box.x0-65,box.y0-65,box.x1+65,box.y1+65)
            # A short bond near the glyph and a sloping bond in its neighborhood
            # distinguishes structures from C/N/O column headings in ruled tables.
            bonded = any(close.intersects(r + (-.5,-.5,.5,.5)) for r,_ in lines) and any(slope and context.intersects(r) for r,slope in lines)
            in_image = any(image.contains(box.tl+(box.br-box.tl)*.5) for image in images)
            if bonded or in_image:
                labels.append((text, normalized_rect(box,page)))
    return labels


@lru_cache(maxsize=6)
def pdf_labels(path, stamp):
    with PDF_LOCK, pymupdf.open(path) as document:
        return {i+1:page_labels(page) for i,page in enumerate(document)}


def annotate_blocks(blocks, labels):
    """Exclude confirmed diagram lines without changing persisted source records."""
    result = []
    for block in blocks:
        lines = block.get('text','').splitlines()
        rects = block.get('rects', [])
        def matches(text, rect=None):
            for label, box in labels:
                if re.sub(r'\s+','',label) != re.sub(r'\s+','',text):
                    continue
                if rect is not None and (abs(rect[0]-box[0])>.01 or abs(rect[1]-box[1])>.01):
                    continue
                if rect is None:
                    continue  # Never exclude an ambiguous old record by text alone.
                return True
            return False
        removed = [matches(text,rect) for text,rect in zip(lines,rects)] if len(lines)==len(rects) else []
        if removed and all(removed):
            result.append(dict(block, role='diagram-label'))
        elif any(removed):
            result.append(dict(block,text='\n'.join(t for t,skip in zip(lines,removed) if not skip),
                               rects=[r for r,skip in zip(rects,removed) if not skip]))
        else:
            result.append(block)
    return result


def translatable(block):
    return block.get('role') != 'diagram-label' and bool(block.get('text','').strip())
