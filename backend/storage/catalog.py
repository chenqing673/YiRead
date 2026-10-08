"""Local editable metadata and content hashes, never external lookups."""
import hashlib
import os
import re
import threading
import pymupdf
from core.config import get_data_path
from storage.item import get_item
from storage.pdf_view import PDF_LOCK
from utils.json_io import write_json_atomic

CATALOG_LOCK=threading.RLock()


def fingerprint(path):
    digest=hashlib.sha256()
    with open(path,'rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def extract_metadata(path):
    with PDF_LOCK,pymupdf.open(path) as doc:
        metadata=doc.metadata or {}
        text=doc[0].get_text() if len(doc) else ''
    result={}
    title=(metadata.get('title') or '').strip()
    if title and len(title)>8 and not title.lower().endswith('.pdf'):result['title']=title
    author=(metadata.get('author') or '').strip()
    if author and len(author)<1000:result['authors']=[v.strip() for v in re.split(r';|\band\b',author) if v.strip()]
    journal=re.search(r'\b(?:Chinese Chemical Letters|Journal of [A-Za-z &-]{3,60}|Organic Letters|Organic Process Research [& ]+Development)\b',text[:1500])
    if journal:result['journal']=journal.group().strip()
    doi=re.search(r'10\.\d{4,9}/[^\s<>"\]]+',text,re.I)
    if doi:result['doi']=doi.group().rstrip('.,;)')
    # Only infer year from document dates or first-page publication/copyright context.
    year=re.search(r'(?:©|copyright|published|\(\s*)[^\n]{0,30}?\b((?:19|20)\d{2})\b',text,re.I)
    if year:result['year']=int(year.group(1))
    return result


def update_item(paper_id,data):
    with CATALOG_LOCK:
        item=get_item(paper_id)
        if not item:raise LookupError('文献不存在')
        for name in ('title','doi','journal'):
            if name in data:
                if not isinstance(data[name],str) or len(data[name])>500:raise ValueError('元数据文本过长或格式错误')
                item[name]=data[name].strip()
        if not item.get('title'):raise ValueError('标题不能为空')
        if 'year' in data:
            year=data['year']
            if year in ('',None):item['year']=None
            elif isinstance(year,(str,int)) and str(year).isdigit() and 1800<=int(year)<=2100:item['year']=int(year)
            else:raise ValueError('年份应为 1800–2100')
        for name in ('authors','tags'):
            if name in data:
                value=data[name]
                if not isinstance(value,list) or len(value)>50 or any(not isinstance(v,str) or len(v)>150 for v in value):raise ValueError('作者或标签格式错误')
                item[name]=list(dict.fromkeys(v.strip() for v in value if v.strip()))
        for name in ('favorite','is_read'):
            if name in data:
                if not isinstance(data[name],bool):raise ValueError('状态格式错误')
                item[name]=data[name]
        write_json_atomic(os.path.join(get_data_path('library'),paper_id,'item.json'),item)
        return item
