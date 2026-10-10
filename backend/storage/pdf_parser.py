import pymupdf
from functools import lru_cache
from storage.pdf_view import PDF_LOCK, normalized_rect
from storage.reading_order import order_items
from storage.diagram_labels import page_labels, annotate_blocks


def page_separators(page):
    width,height=page.cropbox.width,page.cropbox.height
    positions={.065,.94}
    for drawing in page.get_drawings():
        for shape in drawing['items']:
            if shape[0]=='l':
                a,b=shape[1:3]
                if abs(a.y-b.y)<1 and abs(a.x-b.x)>width*.70:positions.add((a.y+b.y)/2/height)
    return [[0,y,1,y] for y in sorted(positions) if 0<y<1]


@lru_cache(maxsize=6)
def pdf_reading_regions(pdf_path,stamp):
    with PDF_LOCK,pymupdf.open(pdf_path) as document:
        return {i+1:{'separators':page_separators(page),'rotation':page.rotation} for i,page in enumerate(document)}


def parse_pdf(pdf_path):
    with PDF_LOCK, pymupdf.open(pdf_path) as document:
        if document.needs_pass:
            raise ValueError("encrypted PDF requires a password")
        pages = []
        for page_index, page in enumerate(document):
            fragments=[];width=page.cropbox.width;height=page.cropbox.height
            for parent,block in enumerate(page.get_text("dict", sort=False)["blocks"]):
                if block.get("type") != 0:
                    continue
                for line in block.get('lines',[]):
                    groups=[];group=[]
                    for span in sorted(line['spans'],key=lambda s:s['bbox'][0]):
                        if group and span['bbox'][0]-group[-1]['bbox'][2]>max(18,span['size']*2.5):groups.append(group);group=[]
                        group.append(span)
                    if group:groups.append(group)
                    for spans in groups:
                        text=''.join(s['text'] for s in spans).strip()
                        if not text:continue
                        box=pymupdf.Rect(spans[0]['bbox'])
                        for span in spans[1:]:box|=pymupdf.Rect(span['bbox'])
                        fragments.append({'parent':parent,'text':text,'rect':normalized_rect(box,page),'box':[box.x0/width,box.y0/height,box.x1/width,box.y1/height]})
            separators=page_separators(page)
            fragments.extend({'box':box,'separator':True} for box in separators)
            blocks=[];previous=None
            for fragment in order_items(fragments):
                if fragment.get('separator'):previous=None;continue
                # A merged MuPDF block can span both columns. Never rejoin across a gutter.
                join=previous is not None and previous['parent']==fragment['parent'] and abs(previous['box'][0]-fragment['box'][0])<.08 and abs(previous['box'][2]-fragment['box'][2])<.15
                if join:
                    output=blocks[-1];output['text']+='\n'+fragment['text'];output['rects'].append(fragment['rect'])
                    b=output['reading_bbox'];f=fragment['box'];output['reading_bbox']=[min(b[0],f[0]),min(b[1],f[1]),max(b[2],f[2]),max(b[3],f[3])]
                else:blocks.append({'id':f"p{page_index+1}_b{len(blocks)+1}",'text':fragment['text'],'rects':[fragment['rect']],'reading_bbox':fragment['box']})
                previous=fragment
            pages.append({"page":page_index+1,"width":page.rect.width,"height":page.rect.height,"blocks":annotate_blocks(blocks,page_labels(page))})
        return {"meta":{"page_count":len(document),"geometry_version":1,"reading_order_version":2},"pages":pages}
