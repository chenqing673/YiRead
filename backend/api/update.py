from api.base import success, error
from core.security import require_token
from core import updater


def handle_update(handler, action):
    if not require_token(handler):
        return
    try:
        if action == 'check':
            data = updater.check_update()
        elif action == 'install':
            from core.translation_worker import JOB_LOCK, ACTIVE
            with JOB_LOCK:
                if ACTIVE:
                    raise ValueError('请先暂停翻译，并等待已发出的请求完成')
                data = updater.install_update(handler.server)
        else:
            data = updater.status()
        success(handler, data)
    except Exception as exc:
        error(handler, str(exc), 400)
