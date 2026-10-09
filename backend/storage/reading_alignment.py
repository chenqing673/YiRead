"""Read-only sentence anchors for existing translations; no model calls or file rewrites."""
import os
import re
import json
import hashlib
from functools import lru_cache
import pymupdf
from core.config import get_data_path
from core.alignment import sentence_spans
from storage.pdf_view import PDF_LOCK, source_path, locate_legacy_blocks
from utils.json_io import read_json
from storage.paper_reader import get_paper


def numeric_anchors(text):
    # Normalize spacing/decimal formatting, but never assume changed experimental values match.
    return sorted(re.findall(r'\d+(?:\.\d+)?', text))


def paired_spans(source, translated):
    if not source.strip() or not translated.strip() or '|' in translated or re.search(r'^#{1,4}\s', translated, re.M):
        return []
    left, right = sentence_spans(source), sentence_spans(translated)
    if len(left) != len(right) or not left:
        return []
    # Old translations are positional alignment, not a claim of semantic verification.
    for (a,b),(c,d) in zip(left,right):
        if numeric_anchors(source[a:b]) != numeric_anchors(translated[c:d]):return []
    return list(zip(left,right))


def translation_signature(result):
    content=[(target.get('id'),target.get('text'),target.get('translation'))
             for block in result.get('blocks',[]) for target in block.get('segments') or [block]]
    return hashlib.sha256(json.dumps(content,ensure_ascii=False).encode('utf8')).hexdigest()


@lru_cache(maxsize=6)
def _reading_units(pdf_file, pdf_stamp, paper_file, paper_stamp, translation_file, translation_stamp, expected=None):
    paper_id = os.path.basename(os.path.dirname(paper_file))
    library_file = os.path.join(get_data_path('library'), paper_id, 'paper.json')
    paper = get_paper(paper_id) if os.path.normcase(os.path.abspath(paper_file)) == os.path.normcase(os.path.abspath(library_file)) else read_json(paper_file)
    translated = read_json(translation_file)
    # A worker may replace the translation between the API read and geometry calculation.
    if expected and translation_signature(translated)!=expected:return {}
    outputs = {block['id']:block for block in translated.get('blocks',[])}
    result = {}
    with PDF_LOCK, pymupdf.open(pdf_file) as doc:
        for original_page in paper.get('pages',[]):
            number = original_page['page']
            if not 1 <= number <= len(doc):continue
            page = doc[number-1]
            original_blocks = [block for block in original_page.get('blocks',[]) if block['id'] in outputs]
            if not original_blocks:continue
            # Normalize each PDF word once per page, rather than once per translated paragraph.
            from storage.pdf_view import normalized_rect
            word_geometry=[(word,normalized_rect(word[:4],page)) for word in page.get_text('words',sort=False)]
            parents = locate_legacy_blocks(page,original_blocks,word_geometry=word_geometry)
            for original,parent in zip(original_blocks,parents):
                output = outputs.get(original['id'],{})
                if not parent['rects']:continue
                targets = output.get('segments') or [dict(output,text=original.get('text',''))]
                # Locate all sentence units together so identical repeated text uses distinct words.
                pending = []
                for target in targets:
                    source, translation = target.get('text',''),target.get('translation','')
                    spans = paired_spans(source,translation)
                    if not spans:continue
                    direct = output.get('alignment_version',0) >= 2 and len(spans)==1
                    for index,((a,b),(start,end)) in enumerate(spans):
                        pending.append({'id':target['id']+'__read'+str(index+1),'text':source[a:b],
                                        'target':target['id'],'start':start,'end':end,
                                        'kind':'sentence' if direct else 'sentence-order'})
                if not pending:continue
                geometry = locate_legacy_blocks(page,pending,within=parent['rects'],word_geometry=word_geometry)
                grouped = {}
                for unit,position in zip(pending,geometry):
                    grouped.setdefault(unit['target'],[]).append({
                        'id':unit['id'],'start':unit['start'],'end':unit['end'],
                        'kind':unit['kind'],'rects':position['rects']})
                for target_id,units in grouped.items():
                    # Partial anchors could make the reader jump over unmatched sentences.
                    if all(unit['rects'] for unit in units):result[target_id]=units
    return result


def attach_reading_units(paper_id,result):
    pdf_file = source_path(paper_id)
    paper_file = os.path.join(get_data_path('library'),paper_id,'paper.json')
    translation_file = os.path.join(get_data_path('translation'),paper_id+'.json')
    try:
        paths = (pdf_file,paper_file,translation_file)
        args = [value for path in paths for value in (path,os.stat(path).st_mtime_ns)]
        mapping = _reading_units(*args,translation_signature(result))
        for block in result.get('blocks',[]):
            for target in block.get('segments') or [block]:
                target['reading_units'] = mapping.get(target['id'],[])
    except (OSError,RuntimeError,ValueError,TypeError,KeyError):
        pass  # Missing PDF / legacy data keeps safe paragraph-level fallback.
    return result
