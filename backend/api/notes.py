from api.base import read_body,success,error
from core.security import require_token
from core.translation_worker import JOB_LOCK
from storage.notes import get_notes,save_note,NotesConflict


def handle_notes(handler,paper_id=None):
    if not require_token(handler):return
    try:
        with JOB_LOCK:
            if paper_id:return success(handler,get_notes(paper_id))
            data=read_body(handler)
            if not data.get('paper_id'):raise ValueError('缺少文献编号')
            success(handler,save_note(data['paper_id'],data))
    except LookupError as exc:error(handler,str(exc),404)
    except NotesConflict as exc:error(handler,str(exc),409)
    except (ValueError,TypeError) as exc:error(handler,str(exc),400)
