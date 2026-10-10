"""Read-only page backgrounds and positioned text for the optional layout view.

Only confident prose regions are cleared. Graphics, images, mathematical text,
table cells and untranslatable/legacy regions remain in the source background.
No model calls and no modification of the user's PDF or saved translations.
"""
import hashlib
import os
import re
from functools import lru_cache

import pymupdf
from core.config import get_data_path
from storage.paper_reader import get_paper
from storage.pdf_view import PDF_LOCK, source_path, locate_legacy_blocks, normalized_rect
from storage.translation_store import get_translation, translation_revision


def overlap(a, b):
    width=max(0,min(a[2],b[2])-max(a[0],b[0]))
    height=max(0,min(a[3],b[3])-max(a[1],b[1]))
    return width*height/max(.000001,(a[2]-a[0])*(a[3]-a[1]))


def ruled_table_regions(page):
    """Protect three-rule journal tables, which need no vertical grid lines."""
    groups=[]
    for drawing in page.get_drawings():
        for item in drawing['items']:
            if item[0]=='re' and item[1].height<=1:
                a,b=item[1].tl,item[1].br
            elif item[0]=='l':a,b=item[1:3]
            else:continue
            x0,x1=sorted((a.x,b.x))
            if abs(a.y-b.y)>1 or x1-x0<page.rect.width*.15:
                continue
            group=next((g for g in groups if abs(g[0]-x0)<2 and abs(g[1]-x1)<2),None)
            if group is None:
                group=[x0,x1,[]];groups.append(group)
            group[2].append((a.y+b.y)/2)
    regions=[]
    for x0,x1,ys in groups:
        ys=sorted(set(round(y,1) for y in ys))
        for i in range(len(ys)-2):
            # A nearby rule separates the header; a later rule closes the data.
            if 4<=ys[i+1]-ys[i]<=30 and 12<=ys[i+2]-ys[i+1] and ys[i+2]-ys[i]<page.rect.height*.5:
                regions.append(normalized_rect((x0,ys[i]-1,x1,ys[i+2]+1),page))
    return regions


def region_kind(block, box, tables, images, font_size=10, bold=False):
    text = block.get('text', '').strip()
    if block.get('role') == 'diagram-label':
        return 'preserve', '结构式标签保留在原图中'
    if box[1] < .065 or box[3] > .94:
        return 'preserve', '页眉、页脚或页边文字'
    if any(overlap(box, area) > .15 for area in tables):
        return 'preserve', '表格保留原样'
    if any(overlap(box, area) > .25 for area in images):
        return 'preserve', '图内文字保留原样'
    if re.match(r'^\[\d+\]', text) or re.search(r'https?://|@|\bdoi\b', text, re.I):
        return 'preserve', '参考文献或联系方式保留原样'
    words=len(re.findall(r'[A-Za-z]{2,}', text))
    if words < 10 and len(re.findall(r'[=∑∫√±→⇌δαβγΔλ]', text)) >= 3:
        return 'preserve', '公式或实验符号密集区域保留原样'
    if re.match(r'^(?:Fig(?:ure)?\.?|Scheme|Table)\s*\d+', text, re.I):
        return 'caption', ''
    if font_size >= 12 and box[1] < .30 and len(text) > 16 and len(re.findall(r'[A-Za-z]{2,}', text)) >= 2:
        return 'heading', ''
    if text.isupper() and 6 <= len(text) <= 100 and re.search(r'[A-Za-z]{6}',text):
        return 'heading', ''
    if re.match(r'^\d+(?:\.\d+)*\.?\s+[A-Za-z]', text) and len(text) < 140:
        return 'heading', ''
    if (len(text) >= 80 and words >= 10) or (len(text) >= 25 and words >= 3 and box[2]-box[0] >= .10):
        # Comma-separated author names/affiliations should not be laid out as prose.
        if box[1] < .4 and (re.search(r'\b(?:Department|University|College|Institute)\b', text) or text.count(',') >= 5):
            return 'preserve', '作者和单位保留原样'
        return ('heading' if box[1] < .30 and box[3]-box[1] < .12 else 'body'), ''
    return 'preserve', '短标签、符号或不确定区域保留原样'


def stamps(paper_id):
    source = source_path(paper_id)
    paper_file = os.path.join(get_data_path('library'), paper_id, 'paper.json')
    translated_file = os.path.join(get_data_path('translation'), paper_id+'.json')
    return (os.stat(source).st_mtime_ns, os.stat(paper_file).st_mtime_ns,
            os.stat(translated_file).st_mtime_ns if os.path.exists(translated_file) else 0)


def get_translation_layout(paper_id, page_number):
    for _ in range(3):
        before=stamps(paper_id)
        plan=_layout(paper_id,page_number,*before)
        if stamps(paper_id)==before:return plan
    raise ValueError('translation is changing')


@lru_cache(maxsize=16)
def _layout(paper_id, page_number, source_stamp, paper_stamp, translation_stamp):
    paper = get_paper(paper_id)
    original = next((p for p in (paper or {}).get('pages', []) if p['page'] == page_number), None)
    if original is None:
        raise ValueError('page not found')
    translated = get_translation(paper_id) or {}
    outputs = {b['id']: b for b in translated.get('blocks', [])}
    # Re-translated legacy pages retain their parent ID but save positioned parts.
    source_blocks=[]
    for block in original.get('blocks', []):
        output=outputs.get(block['id'], {})
        if output.get('layout_version') == 1 and output.get('segments'):
            for segment in output['segments']:
                source_blocks.append(segment)
                outputs[segment['id']]=segment
        else:
            source_blocks.append(block)
    entries = []
    with PDF_LOCK, pymupdf.open(source_path(paper_id)) as document:
        if not 1 <= page_number <= len(document):
            raise ValueError('page not found')
        page = document[page_number-1]
        geometry = locate_legacy_blocks(page, source_blocks)
        tables = []
        try:
            tables = [normalized_rect(table.bbox, page) for table in page.find_tables(strategy='lines_strict').tables]
        except (ValueError, RuntimeError, AttributeError):
            pass
        tables.extend(ruled_table_regions(page))
        images = [normalized_rect(image['bbox'], page) for image in page.get_image_info()]
        spans = [(span,normalized_rect(span['bbox'],page)) for b in page.get_text('dict')['blocks'] if b.get('type') == 0
                 for line in b['lines'] for span in line['spans']]
        for block, position in zip(source_blocks, geometry):
            rects = position.get('rects', [])
            value = outputs.get(block['id'], {}).get('translation', '')
            if not translated.get('engine') and value.startswith('[译文]'):
                value = ''
            entry = {'id': block['id'], 'placement': 'untranslated' if not value else 'preserve', 'reason': '没有可靠位置'}
            if rects:
                box = [min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects)]
                font_spans = [s for s,span_box in spans if any(overlap(span_box, r) > .65 for r in rects)]
                sizes = sorted(s['size'] for s in font_spans)
                font_size=round(sizes[len(sizes)//2] if sizes else 10, 2)
                bold=bool(font_spans and sum(bool(s.get('flags', 0) & 16) for s in font_spans) > len(font_spans)/2)
                kind, reason = region_kind(block, box, tables, images,font_size,bold)
                if page.rotation:
                    kind, reason = 'preserve', '旋转文字保留原样，请展开查看译文'
                # A record with lines in both columns cannot become one rectangular overlay.
                narrow=[r for r in rects if .12 < r[2]-r[0] < .50]
                if box[2]-box[0] > .70 and sum(r[2]<.51 for r in narrow)>=2 and sum(r[0]>.49 for r in narrow)>=2 and box[3]-box[1] > .12:
                    kind, reason = 'preserve', '文字跨越多个栏位'
                entry.update(box=box, rects=rects, kind=kind, reason=reason,
                             font_size=font_size,bold=bold)
                if value and kind != 'preserve':
                    entry['placement'] = 'replace'
            entries.append(entry)
        # Prevent overlapping paragraph boxes from obscuring another text region.
        candidates = [e for e in entries if e['placement'] == 'replace']
        for entry in candidates:
            if any(other is not entry and (overlap(entry['box'], other['box']) > .08 or overlap(other['box'], entry['box']) > .08) for other in candidates):
                entry.update(placement='preserve', reason='文字区域重叠，保留原文')
        fallback = None
        if not any(e['placement']=='replace' for e in entries) and any(e['placement']=='preserve' and e.get('reason') in ('文字跨越多个栏位','没有可靠位置','文字区域重叠，保留原文') for e in entries):
            fallback = '此页旧译文缺少段落位置，已显示完整译文；重译本页后可按原栏位排版。'
        version = hashlib.sha256(repr((paper_id, page_number, source_stamp, paper_stamp, translation_stamp, 'layout-v6')).encode()).hexdigest()[:24]
        return {'page': page_number, 'width': page.rect.width, 'height': page.rect.height,
                'version': version, 'blocks': entries, 'fallback': fallback, 'revision':translation_revision(translated),
                'background': f'/api/translation-background/{paper_id}/{page_number}?v={version}'}


def background_document(paper_id, plan):
    """Caller holds PDF_LOCK; returns an in-memory document that caller must close."""
    document = pymupdf.open(source_path(paper_id))
    try:
        page = document[plan['page']-1]
        for block in plan['blocks']:
            if block['placement'] != 'replace':
                continue
            for r in block['rects']:
                display = pymupdf.Rect(r[0]*page.rect.width, r[1]*page.rect.height, r[2]*page.rect.width, r[3]*page.rect.height)
                page.add_redact_annot(display * page.derotation_matrix, fill=False, cross_out=False)
        # Never remove images or vector drawings. No white rectangle over diagrams.
        if any(b['placement'] == 'replace' for b in plan['blocks']):
            page.apply_redactions(images=0, graphics=0)
        return document
    except Exception:
        document.close()
        raise


@lru_cache(maxsize=8)
def _render_background(paper_id, page_number, version):
    plan = get_translation_layout(paper_id, page_number)
    if plan['version'] != version:
        raise ValueError('layout changed')
    with PDF_LOCK, background_document(paper_id, plan) as document:
        page = document[page_number-1]
        scale = min(2.2, 2500/max(page.rect.width, page.rect.height))
        return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')


def render_translation_background(paper_id, page_number, version):
    # A versioned URL keeps backgrounds and positioned text from different revisions apart.
    plan = get_translation_layout(paper_id, page_number)
    if plan['version'] != version:
        raise ValueError('layout changed')
    return _render_background(paper_id, page_number, version)
