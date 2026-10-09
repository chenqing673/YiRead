import pymupdf
from storage.pdf_view import PDF_LOCK, normalized_rect
from storage.reading_order import order_items


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
            blocks=[];previous=None
            for fragment in order_items(fragments):
                # A merged MuPDF block can span both columns. Never rejoin across a gutter.
                join=previous is not None and previous['parent']==fragment['parent'] and abs(previous['box'][0]-fragment['box'][0])<.08 and abs(previous['box'][2]-fragment['box'][2])<.15
                if join:
                    output=blocks[-1];output['text']+='\n'+fragment['text'];output['rects'].append(fragment['rect'])
                    b=output['reading_bbox'];f=fragment['box'];output['reading_bbox']=[min(b[0],f[0]),min(b[1],f[1]),max(b[2],f[2]),max(b[3],f[3])]
                else:blocks.append({'id':f"p{page_index+1}_b{len(blocks)+1}",'text':fragment['text'],'rects':[fragment['rect']],'reading_bbox':fragment['box']})
                previous=fragment
            pages.append({"page":page_index+1,"width":page.rect.width,"height":page.rect.height,"blocks":blocks})
        return {"meta":{"page_count":len(document),"geometry_version":1,"reading_order_version":1},"pages":pages}
