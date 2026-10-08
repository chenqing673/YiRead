import json


def json_response(
        handler,
        data,
        status_code=200):
    body = json.dumps(
        data,
        ensure_ascii=False
    ).encode("utf-8")
    handler.send_response(
        status_code
    )
    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )
    handler.send_header(
        "Content-Length",
        str(len(body))
    )
    handler.end_headers()
    handler.wfile.write(body)


def success(
        handler,
        data):
    json_response(
        handler,
        {
            "status": "ok",
            "data": data
        }
    )


def error(
        handler,
        message,
        status_code=404):
    json_response(
        handler,
        {
            "status": "error",
            "message": message
        },
        status_code
    )


def read_body(handler):
    try:
        length = int(handler.headers.get("Content-Length", 0))
        if length <= 0 or length > 65536:
            raise ValueError("invalid request body")
        data = json.loads(handler.rfile.read(length).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        for key in ("paper_id", "job_id"):
            if key in data:
                import re
                if not isinstance(data[key], str) or not re.fullmatch(r"[A-Za-z0-9_-]+", data[key]):
                    raise ValueError("invalid " + key)
        return data
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("invalid JSON") from None
