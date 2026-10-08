from api.base import success,error,read_body
from core.security import require_token
from core.translation_worker import JOB_LOCK
from storage.trash import list_trash,restore_paper


def handle_trash(handler):
    if not require_token(handler):return
    try:
        with JOB_LOCK:
            result=restore_paper(read_body(handler).get('entry')) if handler.command=='POST' else {'items':list_trash()}
            success(handler,result)
    except LookupError as exc:error(handler,str(exc),404)
    except (ValueError,TypeError) as exc:error(handler,str(exc),400)
