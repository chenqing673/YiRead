from api.base import success
from core.security import get_token

def handle_token(handler):
    success(
        handler,
        {
            "token": get_token()
        }
    )
