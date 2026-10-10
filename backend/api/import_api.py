import os
import re
import logging
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
    if length <= 0 or length > 51 * 1024 * 1024:
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
        if filename in (".", "..") or len(filename) > 255 or re.search(r'[<>:"|?*\x00-\x1f]', filename):
            return {"error": "invalid filename"}
        payload = part.get_payload(decode=True)
        if not payload or b"%PDF-" not in payload[:1024]:
            return {"error": "invalid pdf"}
        if len(payload)>50*1024*1024:
            return {"error":"PDF 文件大小需小于 50 MB"}
        upload_dir = get_data_path("upload")
        os.makedirs(upload_dir, exist_ok=True)
        folder = tempfile.mkdtemp(prefix="import_", dir=upload_dir)
        # Keep the temporary Windows path short, even for long article titles.
        path = os.path.join(folder, "document.pdf")
        try:
            with open(path, "wb") as file:file.write(payload)
        except OSError:
            cleanup_import_file(path);raise
        return {"file_path": path, "file_name": filename}
    return None

def cleanup_import_file(
        file_path
):
    from utils.json_io import sharing_retry
    try:
        if os.path.exists(file_path):sharing_retry(lambda:os.remove(file_path))
        if os.path.isdir(os.path.dirname(file_path)):sharing_retry(lambda:os.rmdir(os.path.dirname(file_path)))
    except OSError:
        # Antivirus/indexer locks must never turn a committed import into failure.
        logging.warning('Temporary PDF cleanup deferred: %s',file_path,exc_info=True)

def handle_import(handler):
    if not require_token(handler):
        return
    try:result=save_uploaded_file(handler)
    except OSError:
        logging.exception('PDF upload could not be saved')
        return error(handler,'文件暂时无法保存，请重试并检查磁盘空间或文件占用。',503)
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
            saved_file, file_name=result.get('file_name')
        )
    except OSError:
        logging.exception('PDF import storage operation failed')
        return error(handler,'文件暂时无法读取或保存，请重试并检查磁盘空间或文件占用。',503)
    except Exception as exc:
        logging.exception('PDF import parsing failed')
        message='此 PDF 已加密，请先解锁后导入。' if 'password' in str(exc).lower() or 'encrypted' in str(exc).lower() else 'PDF 无法解析，请确认文件完整且能在 PDF 阅读器中打开。'
        return error(handler,message,400)
    finally:cleanup_import_file(saved_file)
    success(
        handler,
        item
    )
