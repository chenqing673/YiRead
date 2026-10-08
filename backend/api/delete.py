from api.base import success,error
from storage.trash import recycle_paper

def handle_delete(
        handler,
        paper_id):
    try:success(handler,recycle_paper(paper_id))
    except LookupError as exc:error(handler,str(exc),404)
    except (ValueError,TypeError) as exc:error(handler,str(exc),400)
