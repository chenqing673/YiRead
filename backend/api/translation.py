from api.base import success, error, read_body
from core.security import require_token
from core.translator import settings
from core.translation_worker import JOB_LOCK, submit_translation
from storage.jobs import create_translation_job
from storage.paper_reader import get_paper


def handle_create_translation(handler):
    if not require_token(handler):
        return
    try:
        data = read_body(handler)
        paper_id = data.get("paper_id")
        if not paper_id:
            return error(handler, "missing paper_id", 400)
        paper=get_paper(paper_id)
        if not paper:
            return error(handler, "paper not found", 404)
        with JOB_LOCK:
            block_id=data.get('block_id');segment_id=data.get('segment_id')
            if block_id and not any(b['id']==block_id for p in paper['pages'] for b in p['blocks']):raise ValueError('原文段落不存在')
            from storage.translation_store import get_translation
            existing=get_translation(paper_id) or {}
            if segment_id and not any(s['id']==segment_id for b in existing.get('blocks',[]) if b['id']==block_id for s in b.get('segments',[])):raise ValueError('对齐段落不存在')
            pages=data.get('pages')
            if pages is not None and (not isinstance(pages,list) or not pages or len(pages)>len(paper['pages']) or any(type(n) is not int or n not in {p['page'] for p in paper['pages']} for n in pages)):
                raise ValueError('请选择有效的翻译页码')
            retry_failed=data.get('retry_failed',False)
            if 'force' in data and not isinstance(data['force'],bool):raise ValueError('重译设置格式错误')
            if not isinstance(retry_failed,bool):raise ValueError('重试设置格式错误')
            if retry_failed:
                from storage.jobs import get_translation_job_by_paper
                prior=get_translation_job_by_paper(paper_id)
                if not prior or not prior.get('failed'):raise ValueError('没有失败部分可重试')
                if data.get('force') or pages or block_id:raise ValueError('失败重试不能同时指定重译或页码')
            aligned=data.get('aligned',prior.get('aligned',False) if retry_failed else settings().get('aligned',False))
            if not isinstance(aligned,bool):raise ValueError('对齐设置格式错误')
            language=existing.get('target_lang',settings().get('target_lang','zh')) if block_id else settings().get('target_lang','zh')
            job = create_translation_job(paper_id, target_lang=language, force=bool(data.get("force")),block_id=block_id,segment_id=segment_id,aligned=aligned,pages=sorted(set(pages)) if pages else None,retry_failed=retry_failed)
            if job["status"] == "pending":
                submit_translation(job["job_id"])
        success(handler, {k:v for k,v in job.items() if k not in ('unit_results','plan_signature')})
    except (ValueError, TypeError) as exc:
        error(handler, str(exc), 400)
