"""Read-only, original-color crops for figures and tables in flowing reading."""
import hashlib
import os
import re
import logging
from functools import lru_cache

import pymupdf
from storage.paper_reader import get_paper
from storage.pdf_view import PDF_LOCK, source_path, normalized_rect, locate_legacy_blocks
from storage.translation_layout import overlap, ruled_table_regions
from storage.diagram_labels import page_labels
from core.config import get_data_path

CAPTION=re.compile(r'^(Fig(?:ure)?\.?|Scheme|Table)\s*[-–.]?\s*(?:\d+|[IVX]+)\b',re.I)


def merged_rects(rects,gap=5):
    groups=[]
    for rect,weight in rects:
        current=pymupdf.Rect(rect);count=weight
        changed=True
        while changed:
            changed=False
            for index,(other,n) in enumerate(groups):
                if (current+(-gap,-gap,gap,gap)).intersects(other):
                    current|=other;count+=n;groups.pop(index);changed=True;break
        groups.append((current,count))
    return groups


def page_regions(page,blocks):
    geometry={b['id']:b['rects'] for b in locate_legacy_blocks(page,blocks)}
    captions=[]
    for b in page.get_text('blocks'):
        match=CAPTION.match(b[4].strip())
        if match:captions.append({'kind':'table' if match[1].lower()=='table' else 'figure','box':normalized_rect(b[:4],page)})
    def table_caption(box):
        return next((c for c in reversed(captions) if c['kind']=='table' and -.015<=box[1]-c['box'][3]<.18 and c['box'][0]<box[2] and c['box'][2]>box[0]),None)
    words=[(w[4],normalized_rect(w[:4],page)) for w in page.get_text('words')]
    def table_headers(box):
        text=' '.join(word for word,r in words if overlap(r,box)>.6)
        return bool(re.search(r'\b(?:Entry|Yield|Solvent|Catalyst|Time|Temperature|Reference|Sample)\b',text,re.I) and len(re.findall(r'\b\d+(?:\.\d+)?\b',text))>=3)
    tables=ruled_table_regions(page)
    grid_tables=[]
    try:grid_tables=[normalized_rect(t.bbox,page) for t in page.find_tables(strategy='lines_strict').tables if t.row_count>=2 and t.col_count>=2]
    except (RuntimeError,ValueError,AttributeError):pass
    # Repeated chemical bonds can resemble three horizontal rules. A table
    # needs a nearby table caption or a detected grid of cells.
    tables=[box for box in tables if table_caption(box) or table_headers(box) or any(overlap(box,g)>.8 for g in grid_tables)]+grid_tables
    tables=[box for i,box in enumerate(tables) if box[2]-box[0]>.1 and box[3]-box[1]>.02 and not any(overlap(box,prior)>.85 for prior in tables[:i])]
    expanded_tables=[]
    for box in tables:
        caption=table_caption(box)
        if caption:box=[min(box[0],caption['box'][0]),caption['box'][1],max(box[2],caption['box'][2]),box[3]]
        # Small footnote lines immediately below the bottom rule belong to the
        # table, but a normal paragraph must remain in the reading stream.
        for b in blocks:
            rects=geometry.get(b['id'],[])
            if rects and len(b.get('text',''))<220 and re.match(r'^(?:[a-z][\s.)]|[*†‡]|Note\b|Abbreviations\b)',b.get('text','').strip()):
                r=rects[0]
                if -.015<=r[1]-box[3]<.02 and r[0]>=box[0]-.02 and r[2]<=box[2]+.02:box=[box[0],box[1],box[2],max(box[3],max(r[3] for r in rects))]
        expanded_tables.append(box)
    tables=expanded_tables
    regions=[{'kind':'table','box':box} for box in tables]
    def crosses_prose(box):
        return any(len(b.get('text',''))>180 and any(overlap(r,box)>.2 and overlap(r,box)<.95 for r in geometry.get(b['id'],[])) for b in blocks)
    images=[]
    for image in page.get_image_info():
        box=normalized_rect(image['bbox'],page)
        if box[1]>.075 and box[3]<.94 and box[2]-box[0]>.08 and box[3]-box[1]>.03 and not crosses_prose(box) and not any(overlap(box,t)>.5 for t in tables):
            images.append(box)
    drawings=[]
    for drawing in page.get_drawings():
        rect=pymupdf.Rect(drawing['rect'])
        box=normalized_rect(rect,page)
        if box[1]<.075 or box[3]>.94 or any(overlap(box,t)>.3 for t in tables):continue
        if rect.width>page.rect.width*.7 and rect.height<3:continue
        if rect.width*rect.height>page.rect.width*page.rect.height*.2:continue
        if drawing.get('type')=='f' and rect.width>80 and rect.height>40:continue
        if drawing.get('type')=='f' and drawing.get('fill') and min(drawing['fill'])>.65 and rect.height>15:continue
        drawings.append((rect+(-.5,-.5,.5,.5),max(1,len(drawing['items']))))
    chemical=page_labels(page)
    vectors=[]
    for rect,count in merged_rects(drawings,gap=8):
        box=normalized_rect(rect,page)
        if count<3 or box[2]-box[0]<.04 or box[3]-box[1]<.025 or crosses_prose(box):continue
        caption=next((c for c in captions if c['kind']=='figure' and 0<=c['box'][1]-box[3]<.10 and (c['box'][0]<box[2]+.12 and c['box'][2]>box[0]-.12 or .4<(c['box'][0]+c['box'][2])/2<.6)),None)
        labels=[r for _,r in chemical if r[0]<box[2]+.025 and r[2]>box[0]-.025 and r[1]<box[3]+.025 and r[3]>box[1]-.025]
        if not caption and len(labels)<2:continue
        # Bond strokes omit letters and compound IDs. Include nearby original
        # glyphs without extending down into the caption or surrounding prose.
        for r in labels:box=[min(box[0],r[0]),min(box[1],r[1]),max(box[2],r[2]),max(box[3],r[3])]
        if caption:
            r=caption['box'];box=[min(box[0],r[0]),min(box[1],r[1]),max(box[2],r[2]),max(box[3],r[3])]
        vectors.append((box,caption))
    # Panels sharing the same caption are one complete figure.
    grouped={}
    for box,caption in vectors:
        key=tuple(caption['box']) if caption else tuple(box)
        previous=grouped.get(key)
        grouped[key]=[min(previous[0],box[0]),min(previous[1],box[1]),max(previous[2],box[2]),max(previous[3],box[3])] if previous else box
    for box in images+list(grouped.values()):
        if not any(overlap(box,r['box'])>.8 for r in regions):regions.append({'kind':'figure','box':box})
    result=[]
    for region in sorted(regions,key=lambda r:(r['box'][1],r['box'][0])):
        box=region['box']
        box=[max(0,box[0]-.012),max(0,box[1]-.008),min(1,box[2]+.012),min(1,box[3]+.008)]
        covered=[b['id'] for b in blocks if geometry.get(b['id']) and all(overlap(rect,box)>.8 for rect in geometry[b['id']]) and not CAPTION.match(b.get('text','').strip())]
        caption_blocks=[b for b in blocks if CAPTION.match(b.get('text','').strip()) and geometry.get(b['id'])]
        caption_id=None
        for b in caption_blocks:
            r=geometry[b['id']][0]
            kind='table' if CAPTION.match(b['text'].strip())[1].lower()=='table' else 'figure'
            if kind!=region['kind']:continue
            gap=r[1]-box[3] if region['kind']=='figure' else box[1]-r[3]
            if overlap(r,box)>.8 or (-.015<=gap<.12 and r[0]<box[2]+.12 and r[2]>box[0]-.12):
                caption_id=b['id'];break
        anchor=caption_id if region['kind']=='figure' else next((b['id'] for b in blocks if b['id'] in covered),None)
        if not anchor:
            after=[b for b in blocks if geometry.get(b['id']) and geometry[b['id']][0][1]>=box[3] and geometry[b['id']][0][0]<box[2] and geometry[b['id']][0][2]>box[0]]
            anchor=min(after,key=lambda b:geometry[b['id']][0][1])['id'] if after else None
        result.append({**region,'box':box,'covered':covered,'anchor':anchor,'caption_id':caption_id})
    return result


def media_version(paper_id):
    paper_file=os.path.join(get_data_path('library'),paper_id,'paper.json')
    return hashlib.sha256(repr((paper_id,os.stat(source_path(paper_id)).st_mtime_ns,os.stat(paper_file).st_mtime_ns,'media-v3')).encode()).hexdigest()[:24]


def get_reading_media(paper_id):
    return _manifest(paper_id,media_version(paper_id))


@lru_cache(maxsize=6)
def _manifest(paper_id,version):
    paper=get_paper(paper_id)
    pages=[]
    with PDF_LOCK,pymupdf.open(source_path(paper_id)) as document:
        for original in (paper or {}).get('pages',[]):
            page=document[original['page']-1]
            try:regions=page_regions(page,original['blocks'])
            except (ValueError,RuntimeError,AttributeError):
                logging.warning('Original media detection failed for %s page %s',paper_id,original['page'],exc_info=True);regions=[]
            assets=[]
            for index,region in enumerate(regions):
                asset_id='p'+str(original['page'])+'_media'+str(index+1)
                assets.append({**region,'id':asset_id,'url':f'/api/reading-media-image/{paper_id}/{original["page"]}/{asset_id}?v={version}',
                               'width':(region['box'][2]-region['box'][0])*page.rect.width,'height':(region['box'][3]-region['box'][1])*page.rect.height})
            pages.append({'page':original['page'],'assets':assets})
    return {'version':version,'pages':pages}


@lru_cache(maxsize=16)
def render_reading_media(paper_id,page_number,asset_id,version):
    if version!=media_version(paper_id):raise ValueError('media changed')
    manifest=get_reading_media(paper_id)
    asset=next((a for p in manifest['pages'] if p['page']==page_number for a in p['assets'] if a['id']==asset_id),None)
    if not asset:raise LookupError('media not found')
    with PDF_LOCK,pymupdf.open(source_path(paper_id)) as document:
        page=document[page_number-1];b=asset['box'];clip=pymupdf.Rect(b[0]*page.rect.width,b[1]*page.rect.height,b[2]*page.rect.width,b[3]*page.rect.height)
        scale=min(3,2000/max(clip.width,clip.height))
        return page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),clip=clip,alpha=False).tobytes('png')
