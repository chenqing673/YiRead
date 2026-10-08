"""Local-only YiRead web server."""
from api.trash import handle_trash
from api.translation_control import handle_translation_cancel
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
import re
import shutil
import threading
import webbrowser
from urllib.parse import urlparse, unquote
from api.base import error
from api.config import handle_config
from api.library import handle_library
from api.token import handle_token
from api.import_api import handle_import
from api.translation import handle_create_translation
from api.worker import handle_run_translation
from api.translation_result import handle_translation_result
from api.translation_status import handle_translation_status
from api.paper import handle_paper
from api.pdf_view import handle_pdf_layout, handle_pdf_page
from api.item import handle_item
from api.delete import handle_delete
from api.settings import handle_settings, handle_test
from api.research import handle_research
from api.notes import handle_notes
from core.security import require_token
from core.init_data import init_data
from core.config import get_data_path
from core.translation_worker import recover_jobs, JOB_LOCK
from storage.jobs import get_translation_job_by_paper
from core.runtime import RESOURCE_DIR

HOST = "127.0.0.1"
PORT = 8765
BASE_DIR = str(RESOURCE_DIR)
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


class YiReadHandler(SimpleHTTPRequestHandler):
    def allowed_request(self):
        try:
            hostname = urlparse("http://" + self.headers.get("Host", "")).hostname
        except ValueError:
            hostname = None
        if hostname not in ("127.0.0.1", "localhost", "::1"):
            error(self, "invalid host", 403)
            return False
        origin=self.headers.get('Origin')
        if origin:
            parsed=urlparse(origin)
            if parsed.netloc!=self.headers.get('Host') and origin not in ('https://chatgpt.com','https://chat.openai.com'):
                error(self,'invalid origin',403)
                return False
        return True

    def end_headers(self):
        # 允许 Codex 等跨域/私有网络访问本地页面与 API
        origin=self.headers.get('Origin')
        if origin in ('https://chatgpt.com','https://chat.openai.com'):
            self.send_header('Access-Control-Allow-Origin',origin)
            self.send_header('Vary','Origin')
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        super().end_headers()

    def do_OPTIONS(self):
        if not self.allowed_request():return
        self.send_response(204)
        self.end_headers()

    def list_directory(self, path):
        error(self, "not found", 404)
        return None

    def do_GET(self):
        if not self.allowed_request():
            return
        route = unquote(urlparse(self.path).path)
        if route.startswith("/api/pdf-page/"):
            match = re.fullmatch(r"/api/pdf-page/([A-Za-z0-9_-]+)/([1-9][0-9]{0,5})", route)
            if not match:
                return error(self,"invalid page",400)
            return handle_pdf_page(self,match[1],int(match[2]))
        endpoints = {"/api/config": handle_config, "/api/library": handle_library,
                     "/api/trash":handle_trash, "/api/token": handle_token, "/api/settings": handle_settings}
        if route in endpoints:
            return endpoints[route](self)
        resources = {"/api/translation/status/": handle_translation_status,
                     "/api/translation/": handle_translation_result,
                     "/api/paper/": handle_paper, "/api/item/": handle_item,
                     "/api/source/": self.serve_source, "/api/pdf-layout/": handle_pdf_layout,
                     "/api/notes/":handle_notes}
        for prefix, handle in resources.items():
            if route.startswith(prefix):
                paper_id = route[len(prefix):]
                if not re.fullmatch(r"[A-Za-z0-9_-]+", paper_id):
                    return error(self, "invalid id", 400)
                return handle(self, paper_id)
        if route.startswith("/api/"):
            return error(self, "api not found", 404)
        if route == "/":
            self.path = "/index.html"
        return super().do_GET()

    def serve_source(self, handler, paper_id):
        path = os.path.join(get_data_path("library"), paper_id, "source.pdf")
        if not os.path.isfile(path):
            return error(self, "source not found", 404)
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(os.path.getsize(path)))
        self.end_headers()
        with open(path, "rb") as pdf:
            shutil.copyfileobj(pdf, self.wfile)

    def do_POST(self):
        if not self.allowed_request():
            return
        route = unquote(urlparse(self.path).path)
        endpoints = {"/api/import": handle_import, "/api/translation": handle_create_translation,
                     "/api/trash/restore":handle_trash, "/api/notes":handle_notes, "/api/translation/cancel":handle_translation_cancel,
                     "/api/worker": handle_run_translation, "/api/settings": handle_settings,
                     "/api/settings/test": handle_test}
        research={'/api/metadata':'metadata','/api/metadata/extract':'metadata-extract','/api/translation/edit':'edit','/api/translation/restore':'restore'}
        if route in research:return handle_research(self,research[route])
        if route in endpoints:
            return endpoints[route](self)
        if route.startswith("/api/delete/"):
            if not require_token(self):
                return
            paper_id = route[len("/api/delete/"):]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", paper_id):
                return error(self, "invalid id", 400)
            with JOB_LOCK:
                job = get_translation_job_by_paper(paper_id)
                if job and job.get("status") in ("pending", "running"):
                    return error(self, "翻译任务执行中，请完成后再删除", 409)
                return handle_delete(self, paper_id)
        error(self, "api not found", 404)

    def translate_path(self, path):
        relative = unquote(urlparse(path).path).lstrip("/")
        full_path = os.path.abspath(os.path.join(FRONTEND_DIR, relative))
        try:
            if os.path.commonpath([full_path, FRONTEND_DIR]) != FRONTEND_DIR:
                return FRONTEND_DIR
        except ValueError:
            return FRONTEND_DIR
        return full_path


def start_server(open_browser=False):
    init_data()
    recover_jobs()
    from storage.trash import recover_trash
    recover_trash()
    server = ThreadingHTTPServer((HOST, PORT), YiReadHandler)
    print(f"YiRead server running: http://{HOST}:{PORT}", flush=True)
    if open_browser:
        threading.Thread(
            target=webbrowser.open, args=(f"http://{HOST}:{PORT}/",), daemon=True
        ).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("YiRead stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start the YiRead web server.")
    parser.add_argument("--open-browser", action="store_true", help="Open the homepage in the default browser")
    start_server(open_browser=parser.parse_args().open_browser)
