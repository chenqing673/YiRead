import os
import uuid
import datetime
from core.config import get_data_path
from utils.json_io import write_json_atomic
from utils.json_io import read_json


def get_jobs_path():
    path = get_data_path(
        "jobs"
    )
    os.makedirs(
        path,
        exist_ok=True
    )
    return path


def get_translation_job_by_paper(
    paper_id
):
    import os
    jobs_path = get_jobs_path()
    matches = []
    for filename in os.listdir(jobs_path):
        if filename.endswith(".json"):
            job = read_json(os.path.join(jobs_path, filename))
            if job and job.get("paper_id") == paper_id:
                matches.append(job)
    return max(matches, key=lambda j: j.get("created_at", ""), default=None)



def create_translation_job(
    paper_id,
    source_lang="en",
    target_lang="zh",
    force=False,
    block_id=None,
    segment_id=None,
    aligned=None,
    pages=None,
    retry_failed=False
):
    existing = get_translation_job_by_paper(paper_id)
    if existing and existing["status"] in ("pending", "running"):
        return existing
    if existing and existing.get('type')!='translation_block' and existing["status"] == "completed" and existing.get("target_lang") == target_lang and not force and not block_id and not pages and not retry_failed and not existing.get('pages') and bool(existing.get('aligned'))==bool(aligned):
        from storage.translation_store import get_translation
        result = get_translation(paper_id)
        if result and result.get("engine") == "openai-compatible":
            return existing
    job_id = (
        datetime.datetime.now()
        .strftime("%Y%m%d")
        + "_"
        + uuid.uuid4().hex[:8]
    )
    job = {
        "job_id": job_id,
        "paper_id": paper_id,
        "type": "translation",
        "force": force,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "status": "pending",
        "progress": 0,
        "error": None,
        "created_at":
        datetime.datetime.now()
        .isoformat()
    }
    job.update(block_id=block_id,segment_id=segment_id,aligned=aligned,pages=pages,failed={},completed=0,total=0,usage={})
    if retry_failed and existing:
        job['retry_blocks']=list(existing.get('failed',{}))
    if existing and not force and existing.get('target_lang')==target_lang:
        job['unit_results']=existing.get('unit_results',{})
        job['plan_signature']=existing.get('plan_signature')
    if block_id:job['type']='translation_block'
    job_file = os.path.join(
        get_jobs_path(),
        job_id + ".json"
    )
    write_json_atomic(
        job_file,
        job
    )
    return job


def get_job(job_id):
    path = os.path.join(
        get_jobs_path(),
        job_id + ".json"
    )
    return read_json(
        path
    )
