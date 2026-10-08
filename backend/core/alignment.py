"""Deterministic source segments; each translation keeps its own source geometry."""
import re
import textwrap
import pymupdf
from storage.pdf_view import PDF_LOCK, source_path, locate_legacy_blocks


def sentence_spans(text):
    """Offsets into the unchanged text; protect experimental decimals and abbreviations."""
    ends = []
    for match in re.finditer(r'[.!?。！？][\"\'”’）)]*|\n\s*\n', text):
        end = match.end()
        if match.group().startswith('.'):
            position = match.start()
            if position and position+1 < len(text) and text[position-1].isdigit() and text[position+1].isdigit():
                continue
            prefix = text[:position+1]
            if re.search(r'\b(?:figs?|eqs?|refs?|dr|mr|mrs|ms|prof|vs|ca|approx|al|e\.g|i\.e|m\.p|r\.t)\.$', prefix, re.I) or re.search(r'\b[A-Z]\.$', prefix):
                continue
        if match.group()[0] in '.!?' and end < len(text) and not text[end].isspace():
            continue
        ends.append(end)
    spans, start = [], 0
    for end in ends+[len(text)]:
        while start < end and text[start].isspace():start += 1
        stop = end
        while stop > start and text[stop-1].isspace():stop -= 1
        if stop > start:spans.append((start,stop))
        start = end
    return spans


def source_segments(text, limit=650):
    # One source sentence per translation unit; never merge sentences by character count.
    result = []
    for start,end in sentence_spans(text):
        result.extend(textwrap.wrap(text[start:end], width=limit, break_long_words=False, break_on_hyphens=False))
    return result


def aligned_sources(paper_id, page_number, block):
    segments=[{'id':block['id']+'_s'+str(i+1),'text':text} for i,text in enumerate(source_segments(block['text']))]
    try:
        with PDF_LOCK, pymupdf.open(source_path(paper_id)) as doc:
            page=doc[page_number-1]
            parent=locate_legacy_blocks(page,[block])[0]['rects']
            geometry=locate_legacy_blocks(page,segments,within=parent) if parent else [{'rects':[]} for _ in segments]
        for segment,position in zip(segments,geometry):segment['rects']=position['rects']
    except (OSError,RuntimeError,ValueError):
        for segment in segments:segment['rects']=[]
    return segments
