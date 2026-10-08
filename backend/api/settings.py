from api.base import success, error, read_body
from core.security import require_token
from core.translator import public_settings, save_settings, settings, translate


def handle_settings(handler):
    if not require_token(handler):
        return
    try:
        if handler.command == "GET":
            return success(handler, public_settings())
        success(handler, save_settings(read_body(handler)))
    except (ValueError, TypeError) as exc:
        error(handler, str(exc), 400)


def handle_test(handler):
    if not require_token(handler):
        return
    try:
        config = settings()
        result = translate("Hello, welcome to YiRead.", config, config.get("target_lang", "zh"))
        success(handler, {"translation": result})
    except ValueError as exc:
        error(handler, str(exc), 400)
