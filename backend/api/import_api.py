import os
import re
from api.base import success, error
from core.config import get_data_path
from core.security import require_token
from storage.importer import import_pdf

def save_uploaded_file(handler):
    from email.parser import BytesParser
    from email.policy import default
    import tempfile
    content_type = handler.headers.get("Content-Type", "")
    if not content_type.startswith("multipart/form-data"):
        return {"error": "invalid multipart Content-Type"}
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        return {"error": "invalid Content-Length"}
    if length <= 0 or length > 50 * 1024 * 1024:
        return {"error": "PDF 文件大小需小于 50 MB"}
    message = BytesParser(policy=default).parsebytes(
        ("Content-Type: " + content_type + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + handler.rfile.read(length)
    )
    if not message.is_multipart():
        return {"error": "invalid multipart Content-Type"}
    for part in message.iter_parts():
        filename = part.get_filename()
        if not filename:
            continue
        filename = os.path.basename(filename.replace("\\", "/"))
        if filename in (".", "..") or len(filename) > 180 or re.search(r'[<>:"|?*\x00-\x1f]', filename):
            return {"error": "invalid filename"}
        payload = part.get_payload(decode=True)
        if not payload or not payload.startswith(b"%PDF-"):
            return {"error": "invalid pdf"}
        upload_dir = get_data_path("upload")
        os.makedirs(upload_dir, exist_ok=True)
        folder = tempfile.mkdtemp(prefix="import_", dir=upload_dir)
        path = os.path.join(folder, filename or "document.pdf")
        with open(path, "wb") as file:
            file.write(payload)
        return {"file_path": path}
    return None

def cleanup_import_file(
        file_path
):
    if os.path.exists(
        file_path
    ):
        os.remove(file_path)
        os.rmdir(os.path.dirname(file_path))

def handle_import(handler):
    if not require_token(handler):
        return
    result = save_uploaded_file(
        handler
    )
    if result is None:
        error(
            handler,
            "no file",
            400
        )
        return
    if "error" in result:
        error(
            handler,
            result["error"],
            400
        )
        return
    saved_file = result["file_path"]
    try:
        item = import_pdf(
            saved_file
        )
    except Exception:
        cleanup_import_file(
            saved_file
        )
        error(
            handler,
            "invalid pdf",
            400
        )
        return
    if os.path.exists(
        saved_file
    ):
        cleanup_import_file(saved_file)
    success(
        handler,
        item
    )
