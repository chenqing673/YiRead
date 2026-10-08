from api.base import success,error,read_body
from core.security import require_token
from core.translation_worker import JOB_LOCK
from storage.catalog import update_item
from storage.jobs import get_translation_job_by_paper
from storage.translation_store import get_translation,save_translation


def handle_research(handler,operation):
    if not require_token(handler):return
    try:
        data=read_body(handler);paper_id=data.get('paper_id')
        if not paper_id:raise ValueError('缺少文献编号')
        with JOB_LOCK:
            if operation=='metadata':return success(handler,update_item(paper_id,data))
            if operation=='metadata-extract':
                from storage.catalog import extract_metadata
                from storage.pdf_view import source_path
                import os
                if not os.path.isfile(source_path(paper_id)):raise LookupError('原始 PDF 不存在')
                return success(handler,update_item(paper_id,extract_metadata(source_path(paper_id))))
            job=get_translation_job_by_paper(paper_id)
            if job and job['status'] in ('running','pending'):return error(handler,'翻译正在进行，请完成后再修订',409)
            result=get_translation(paper_id)
            if not result:raise LookupError('译文不存在')
            block=next((b for b in result['blocks'] if b['id']==data.get('block_id')),None)
            if not block:raise LookupError('译文段落不存在')
            target=block
            if data.get('segment_id'):
                target=next((s for s in block.get('segments',[]) if s['id']==data['segment_id']),None)
                if not target:raise LookupError('对齐段落不存在')
            elif block.get('segments') and operation!='restore':raise ValueError('请选择一个对齐小段进行修订')
            if operation=='edit' and 'base_translation' in data and data['base_translation']!=target['translation']:return error(handler,'译文已在其他页面更新，草稿仍保留，请重新载入核对后保存',409)
            if operation=='restore':
                if not target.get('history'):raise ValueError('没有可恢复的上一版')
                value=target['history'].pop()
                if target is block:block.pop('segments',None);block.pop('alignment_version',None)
            else:
                value=data.get('translation')
                if not isinstance(value,str) or not value.strip() or len(value)>30000:raise ValueError('译文不能为空且限 30000 字符')
                target['history']=(target.get('history',[])+[target['translation']])[-20:]
            target['translation']=value;target['edited']=True
            if block.get('segments'):block['translation']='\n\n'.join(s['translation'] for s in block['segments'])
            save_translation(paper_id,result['blocks'],**{k:v for k,v in result.items() if k not in ('paper_id','blocks')})
            success(handler,{'saved':True})
    except LookupError as exc:error(handler,str(exc),404)
    except (ValueError,TypeError) as exc:error(handler,str(exc),400)
