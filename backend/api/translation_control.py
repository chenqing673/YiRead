from api.base import read_body,success,error
from core.security import require_token
from core.translation_worker import JOB_LOCK
from storage.jobs import get_job,get_jobs_path
from utils.json_io import write_json_atomic
import os


def handle_translation_cancel(handler):
    if not require_token(handler):return
    try:
        data=read_body(handler)
        with JOB_LOCK:
            job=get_job(data.get('job_id',''))
            if not job:raise LookupError('任务不存在')
            if job['status'] in ('pending','running'):
                job['cancel_requested']=True
                if job['status']=='pending':job['status']='paused'
                write_json_atomic(os.path.join(get_jobs_path(),job['job_id']+'.json'),job)
            success(handler,{'status':job['status'],'cancel_requested':bool(job.get('cancel_requested'))})
    except LookupError as exc:error(handler,str(exc),404)
    except (ValueError,TypeError) as exc:error(handler,str(exc),400)
