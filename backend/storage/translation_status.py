from storage.jobs import get_translation_job_by_paper
from storage.translation_store import get_translation
from storage.paper_reader import get_paper


def get_translation_status(paper_id):
    job=get_translation_job_by_paper(paper_id);result=get_translation(paper_id) or {}
    simulated=not result.get('engine') and any(str(b.get('translation','')).startswith('[译文]') for b in result.get('blocks',[]))
    if simulated and (not job or job.get('status')=='completed'):
        return {'job_id':None,'status':'not_started','progress':0,'error':'旧版模拟译文，请重新翻译'}
    paper=get_paper(paper_id) or {'pages':[]}
    expected={b['id'] for p in paper['pages'] for b in p['blocks'] if b.get('text','').strip()}
    actual={b['id'] for b in result.get('blocks',[]) if b.get('translation')}
    if job and result.get('target_lang')!=job.get('target_lang'):actual=set()
    coverage=int(len(expected&actual)/max(1,len(expected))*100)
    status=job.get('status') if job else 'completed' if expected and expected<=actual else 'partial' if actual else 'not_started'
    if status=='completed' and not (expected and expected<=actual):status='partial'
    data={'job_id':job.get('job_id') if job else None,'status':status,'progress':job.get('progress',0) if job and status in ('pending','running','failed','paused') else coverage,'document_progress':coverage,'error':job.get('error') if job else None}
    if job:
        for key in ('target_lang','pages','failed','completed','total','usage','message','cancel_requested'):data[key]=job.get(key)
    return data
