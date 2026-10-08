"""Bounded batches with stable IDs, checkpoints and selective failure recovery."""
import copy,hashlib,json,os,threading
from concurrent.futures import ThreadPoolExecutor,as_completed
from core.config import get_data_path
from core.translator import settings,translate,translate_batch,ProviderError,TranslationCancelled
from storage.jobs import get_job,get_jobs_path
from storage.translation_store import get_translation,save_translation
from utils.json_io import read_json,write_json_atomic
from core.alignment import aligned_sources

EXECUTOR=ThreadPoolExecutor(max_workers=1)
JOB_LOCK=threading.RLock()
ACTIVE=set()

def submit_translation(job_id):
    with JOB_LOCK:
        if job_id in ACTIVE:return
        ACTIVE.add(job_id)
    def execute():
        try:run_translation_job(job_id)
        finally:
            with JOB_LOCK:ACTIVE.discard(job_id)
    EXECUTOR.submit(execute)

def run_translation_job(job_id):
    path=os.path.join(get_jobs_path(),job_id+'.json');job=get_job(job_id)
    if not job or job.get('cancel_requested') or job['status'] not in ('pending','running'):return job
    config=settings();pid=job['paper_id'];halt=threading.Event();lock=threading.RLock()
    def cancelled():return halt.is_set() or bool((get_job(job_id) or {}).get('cancel_requested'))
    def persist():
        with JOB_LOCK,lock:
            if (get_job(job_id) or {}).get('cancel_requested'):job['cancel_requested']=True
            write_json_atomic(path,job)
    def meter(usage):
        with lock:
            for key,value in usage.items():job['usage'][key]=job['usage'].get(key,0)+value
    def retry_message(message):
        with lock:job['message']=message
        persist()
    callbacks={'on_usage':meter,'cancel':cancelled,'on_retry':retry_message}
    job.update(status='running',error=None,failed={},usage={},completed=0,total=0,message='准备翻译');persist()
    try:
        paper=read_json(os.path.join(get_data_path('library'),pid,'paper.json'))
        if not paper:raise ProviderError('文献不存在',fatal=True)
        originals=[(p['page'],b) for p in paper['pages'] for b in p['blocks'] if b.get('text','').strip()]
        selected=[(page,b) for page,b in originals if (not job.get('block_id') or b['id']==job['block_id']) and (not job.get('pages') or page in job['pages']) and (not job.get('retry_blocks') or b['id'] in job['retry_blocks'])]
        if not selected:raise ProviderError('所选范围没有可提取的文字，扫描件需先进行 OCR',fatal=True)
        existing=get_translation(pid) or {};same_language=existing.get('target_lang')==job['target_lang']
        translated=copy.deepcopy(existing.get('blocks',[])) if same_language else []
        cached={b['id']:b for b in translated} if not job.get('force') and existing.get('engine')=='openai-compatible' else {}
        aligned=job.get('aligned') if job.get('aligned') is not None else config.get('aligned',False)
        plans={};pending=[]
        for page,block in selected:
            prior=next((b for b in translated if b['id']==block['id']),{});value=cached.get(block['id'])
            if value and value.get('translation') and (not aligned or value.get('segments')) and not job.get('block_id') and not job.get('retry_blocks'):continue
            if job.get('segment_id'):
                segment=next(s for s in prior['segments'] if s['id']==job['segment_id']);units=[{'id':segment['id'],'text':segment['text']}]
            elif aligned:units=aligned_sources(pid,page,block)
            else:units=[{'id':block['id']+'_part'+str(i//5000+1),'text':block['text'][i:i+5000]} for i in range(0,len(block['text']),5000)]
            plans[block['id']]={'page':page,'units':units,'prior':prior};pending.extend(units)
        signature=hashlib.sha256(json.dumps({'source':originals,'aligned':aligned,'language':job['target_lang'],'model':config.get('model'),'endpoint':config.get('base_url'),'glossary':config.get('glossary')},sort_keys=True).encode()).hexdigest()
        results=job.get('unit_results',{}) if not job.get('force') and signature==job.get('plan_signature') else {}
        allowed={u['id'] for u in pending};results={k:v for k,v in results.items() if k in allowed and isinstance(v,str) and v.strip()}
        job.update(unit_results=results,plan_signature=signature,total=len(pending),completed=len(results));saved=set()
        def commit_ready():
            nonlocal translated
            with JOB_LOCK:
                for bid,plan in plans.items():
                    if bid in saved or not all(u['id'] in results for u in plan['units']):continue
                    prior=plan['prior']
                    if job.get('segment_id'):
                        output=copy.deepcopy(prior);segment=next(s for s in output['segments'] if s['id']==job['segment_id'])
                        segment['history']=(segment.get('history',[])+[segment['translation']])[-20:];segment.update(translation=results[segment['id']],edited=False)
                        output['translation']='\n\n'.join(s['translation'] for s in output['segments'])
                    elif aligned:
                        segments=[dict(u,translation=results[u['id']]) for u in plan['units']]
                        output={'id':bid,'segments':segments,'translation':'\n\n'.join(s['translation'] for s in segments),'alignment_version':2}
                    else:output={'id':bid,'translation':'\n\n'.join(results[u['id']] for u in plan['units'])}
                    if not job.get('segment_id') and prior.get('translation'):output['history']=(prior.get('history',[])+[prior['translation']])[-20:]
                    translated=[b for b in translated if b['id']!=bid]+[output];order={b['id']:i for i,(_,b) in enumerate(originals)}
                    translated.sort(key=lambda b:order.get(b['id'],len(order)))
                    metadata={k:v for k,v in existing.items() if k not in ('paper_id','blocks','target_lang','engine')}
                    save_translation(pid,translated,target_lang=job['target_lang'],engine='openai-compatible',**metadata);saved.add(bid)
        commit_ready();batches=[];batch=[];length=0
        for unit in pending:
            if unit['id'] in results:continue
            if batch and (not config.get('batch',True) or len(batch)>=8 or length+len(unit['text'])>6000):batches.append(batch);batch=[];length=0
            batch.append(unit);length+=len(unit['text'])
        if batch:batches.append(batch)
        def request_batch(group):
            found={};errors={};fatal=False
            if cancelled():return found,errors,fatal
            try:
                if len(group)>1:
                    try:found=translate_batch(group,config,job['target_lang'],**callbacks)
                    except ProviderError as exc:
                        if exc.fatal or '编号或格式' not in str(exc):raise
                for unit in group:
                    if unit['id'] in found:continue
                    if cancelled():break
                    try:found[unit['id']]=translate(unit['text'],config,job['target_lang'],**callbacks)
                    except ValueError as exc:
                        errors[unit['id']]=str(exc)
                        if isinstance(exc,ProviderError) and exc.fatal:fatal=True;halt.set();break
            except TranslationCancelled:pass
            except ValueError as exc:
                errors.update({u['id']:str(exc) for u in group if u['id'] not in found});fatal=isinstance(exc,ProviderError) and exc.fatal
                if fatal:halt.set()
            return found,errors,fatal
        failures={};workers=max(1,min(2,config.get('concurrency',1)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            iterator=iter(batches);active={}
            def dispatch():
                while len(active)<workers and not cancelled():
                    group=next(iterator,None)
                    if group is None:break
                    active[pool.submit(request_batch,group)]=group
            dispatch()
            while active:
                future=next(as_completed(active));active.pop(future);found,errors,fatal=future.result()
                with lock:results.update(found);failures.update(errors)
                commit_ready()
                with lock:job.update(completed=len(results),progress=int(len(results)/max(1,len(pending))*100),message='已保存 '+str(len(results))+' / '+str(len(pending))+' 个翻译单元')
                persist();dispatch()
        for bid,plan in plans.items():
            missing=[u['id'] for u in plan['units'] if u['id'] not in results]
            if missing:job['failed'][bid]={'page':plan['page'],'message':next((failures[x] for x in missing if x in failures),'尚未翻译，可继续任务')}
        if (get_job(job_id) or {}).get('cancel_requested'):job.update(status='paused',error=None,message='已暂停，已保存结果可继续阅读')
        elif job['failed']:job.update(status='failed',error=next(iter(job['failed'].values()))['message'])
        else:job.update(status='completed',progress=100,error=None,message='所选范围翻译完成')
    except Exception as exc:job.update(status='failed',error=str(exc))
    persist();return job

def recover_jobs():
    for name in os.listdir(get_jobs_path()):
        if name.endswith('.json'):
            path=os.path.join(get_jobs_path(),name);job=read_json(path)
            if job and job.get('status') in ('pending','running'):
                job.update(status='paused',error=None,message='服务已重启，点击继续可恢复已保存的结果');write_json_atomic(path,job)
