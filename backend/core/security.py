import secrets
from api.base import error
TOKEN = None
def generate_token():
    global TOKEN
    TOKEN = secrets.token_hex(32)
    return TOKEN
def get_token():
    global TOKEN
    if TOKEN is None:
        return generate_token()
    return TOKEN
def verify_token(value):
    return value == get_token()
def require_token(handler):
    token = handler.headers.get(
        "X-Token"
    )
    if not verify_token(token):
        error(
            handler,
            "invalid token",
            403
        )
        return False
    return True
