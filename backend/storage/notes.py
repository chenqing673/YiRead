"""Durable local reading notes, with optimistic versioning for multiple tabs."""
import os
import re
from core.config import get_data_path
from storage.paper_reader import get_paper
from utils.json_io import read_json,write_json_atomic


class NotesConflict(ValueError):pass


def notes_path(paper_id):
    return os.path.join(get_data_path('library'),paper_id,'notes.json')


def get_notes(paper_id):
    if not get_paper(paper_id):raise LookupError('文献不存在')
    return read_json(notes_path(paper_id)) or {'notes':{},'version':0}


def save_note(paper_id,data):
    stored=get_notes(paper_id)
    operation=data.get('operation_id')
    digest=None
    if operation is not None:
        import hashlib,json
        if not isinstance(operation,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',operation):raise ValueError('保存操作编号无效')
        digest=hashlib.sha256(json.dumps({'note_id':data.get('note_id'),'note':data.get('note')},sort_keys=True).encode()).hexdigest()
        previous=stored.get('operations',{}).get(operation)
        if previous:
            if previous!=digest:raise NotesConflict('同一保存操作的内容已变化，请重新保存')
            return stored
    version=data.get('version')
    if not isinstance(version,int) or isinstance(version,bool):raise ValueError('缺少笔记版本')
    if version!=stored['version']:raise NotesConflict('笔记已在其他页面更新，请重新载入后保存')
    note_id=data.get('note_id')
    if not isinstance(note_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',note_id):raise ValueError('笔记编号无效')
    note=data.get('note')
    if note is None:
        stored['notes'].pop(note_id,None)
    else:
        if not isinstance(note,dict):raise ValueError('笔记格式错误')
        text=note.get('text','');bookmark=note.get('bookmark',False)
        if not isinstance(text,str) or len(text)>15000 or not isinstance(bookmark,bool):raise ValueError('笔记限 15000 字符，书签必须为布尔值')
        paper=get_paper(paper_id)
        parent=note.get('parent',note_id)
        original=next(((page['page'],block) for page in paper.get('pages',[]) for block in page.get('blocks',[]) if block['id']==parent),None)
        if not original:raise ValueError('笔记对应的原文段落不存在')
        clean={'text':text,'bookmark':bookmark,'parent':parent,'page':original[0]}
        if 'anchor' in note:
            anchor=note['anchor']
            if not isinstance(anchor,dict) or any(not isinstance(anchor.get(k,''),str) or len(anchor.get(k,''))>limit for k,limit in [('quote',350),('prefix',24),('suffix',24)]):raise ValueError('文字批注锚点格式错误')
            if not anchor.get('quote','').strip():raise ValueError('请选择要批注的文字')
            clean['anchor']={k:anchor.get(k,'') for k in ('quote','prefix','suffix')}
        for name,limit in [('quote',350),('source',1500)]:
            value=note.get(name,'')
            if not isinstance(value,str):raise ValueError('笔记引用格式错误')
            clean[name]=value[:limit]
        if text.strip() or bookmark:stored['notes'][note_id]=clean
        else:stored['notes'].pop(note_id,None)
        if len(stored['notes'])>1000:raise ValueError('每篇文献最多保存 1000 条笔记')
    stored['version']+=1
    if operation:
        stored.setdefault('operations',{})[operation]=digest
        stored['operations']=dict(list(stored['operations'].items())[-50:])
    write_json_atomic(notes_path(paper_id),stored)
    return stored
