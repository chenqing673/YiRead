"""Recoverable deletion with a manifest covering separate document/translation/job files."""
import datetime
import os
import re
import shutil
import uuid
from pathlib import Path
from core.config import get_data_path
from utils.json_io import read_json,write_json_atomic


def trash_root():
    root=Path(get_data_path('trash'));root.mkdir(parents=True,exist_ok=True);return root


def destinations(pid,record):
    kind=record['kind']
    if kind=='library':return Path(get_data_path('library'))/pid
    if kind=='translation':return Path(get_data_path('translation'))/(pid+'.json')
    if kind=='job' and re.fullmatch(r'[A-Za-z0-9_-]+\.json',record['name']):return Path(get_data_path('jobs'))/record['name']
    raise ValueError('回收记录无效')


def entry_data(entry):
    if not isinstance(entry,str) or not re.fullmatch(r'[a-f0-9]{32}',entry):raise ValueError('回收记录编号无效')
    folder=trash_root()/entry;data=read_json(str(folder/'manifest.json'))
    if not isinstance(data,dict) or not isinstance(data.get('paper_id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]+',data['paper_id']):raise LookupError('回收记录不存在')
    if not isinstance(data.get('files'),list) or not data['files']:raise ValueError('回收记录无效')
    for record in data.get('files',[]):
        if not isinstance(record,dict):raise ValueError('回收记录无效')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',record.get('slot','')) or record['slot'] in ('.','..'):raise ValueError('回收记录无效')
        destinations(data['paper_id'],record)
    return folder,data


def list_trash():
    result=[]
    for folder in trash_root().iterdir():
        if not folder.is_dir() or not re.fullmatch(r'[a-f0-9]{32}',folder.name):continue
        try:
            _,data=entry_data(folder.name)
            result.append({'entry':folder.name,'paper_id':data['paper_id'],'title':data['title'],'deleted_at':data['deleted_at'],'state':data['state']})
        except (ValueError,LookupError,KeyError,TypeError):
            continue  # Preserve damaged entries; they must not prevent the library from opening.
    return sorted(result,key=lambda d:d['deleted_at'],reverse=True)


def recycle_paper(pid):
    if not isinstance(pid,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',pid):raise ValueError('文献编号无效')
    library=Path(get_data_path('library'))/pid
    if not library.is_dir():raise LookupError('文献不存在')
    item=read_json(str(library/'item.json')) or {}
    records=[{'kind':'library','slot':'library'}]
    translation=Path(get_data_path('translation'))/(pid+'.json')
    if translation.exists():records.append({'kind':'translation','slot':'translation.json'})
    jobs=Path(get_data_path('jobs'))
    for path in jobs.glob('*.json'):
        if re.fullmatch(r'[A-Za-z0-9_-]+\.json',path.name) and (read_json(str(path)) or {}).get('paper_id')==pid:
            records.append({'kind':'job','name':path.name,'slot':'job-'+path.name})
    entry=uuid.uuid4().hex;folder=trash_root()/entry;folder.mkdir()
    data={'paper_id':pid,'title':item.get('title') or pid,'deleted_at':datetime.datetime.now().isoformat(),'state':'moving','files':records}
    write_json_atomic(str(folder/'manifest.json'),data);moved=[]
    try:
        for record in records:
            shutil.move(str(destinations(pid,record)),str(folder/record['slot']));moved.append(record)
        data['state']='ready';write_json_atomic(str(folder/'manifest.json'),data)
    except Exception:
        for record in reversed(moved):shutil.move(str(folder/record['slot']),str(destinations(pid,record)))
        shutil.rmtree(folder);raise
    return {'paper_id':pid,'entry':entry,'deleted':[r['kind'] for r in records],'recoverable':True}


def restore_paper(entry):
    folder,data=entry_data(entry);pid=data['paper_id']
    if data['state']!='ready':raise ValueError('回收记录正在处理，暂不能恢复')
    for record in data['files']:
        if destinations(pid,record).exists():raise ValueError('文献库已有相同编号或关联文件，未覆盖任何资料')
        if not (folder/record['slot']).exists():raise ValueError('回收记录的文件不完整')
    data['state']='restoring';write_json_atomic(str(folder/'manifest.json'),data);moved=[]
    try:
        for record in data['files']:
            target=destinations(pid,record);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(str(folder/record['slot']),str(target));moved.append(record)
    except Exception:
        for record in reversed(moved):shutil.move(str(destinations(pid,record)),str(folder/record['slot']))
        data['state']='ready';write_json_atomic(str(folder/'manifest.json'),data);raise
    shutil.rmtree(folder)
    return {'paper_id':pid,'restored':True}


def recover_trash():
    for item in list_trash():
        if item['state'] not in ('moving','restoring'):continue
        folder,data=entry_data(item['entry']);pid=data['paper_id']
        for record in data['files']:
            target=destinations(pid,record);held=folder/record['slot']
            if data['state']=='moving' and target.exists() and not held.exists():shutil.move(str(target),str(held))
            elif data['state']=='restoring' and held.exists() and not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(held),str(target))
        if data['state']=='moving' and all((folder/r['slot']).exists() for r in data['files']):
            data['state']='ready';write_json_atomic(str(folder/'manifest.json'),data)
        elif data['state']=='restoring' and all(destinations(pid,r).exists() and not (folder/r['slot']).exists() for r in data['files']):shutil.rmtree(folder)
