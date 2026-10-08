from api.base import success, error, read_body
from core.security import require_token
from core.translation_worker import submit_translation
from storage.jobs import get_job


def handle_run_translation(handler):
    if not require_token(handler):
        return
    try:
        data = read_body(handler)
        job_id = data.get("job_id")
        if not job_id:
            return error(handler, "missing job_id", 400)
        job = get_job(job_id)
        if not job:
            return error(handler, "job not found", 404)
        if job["status"] == "pending":
            submit_translation(job_id)
        success(handler, {k:v for k,v in job.items() if k not in ('unit_results','plan_signature')})
    except (ValueError, TypeError) as exc:
        error(handler, str(exc), 400)
