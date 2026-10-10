from urllib.parse import parse_qs, urlparse
from api.base import success, error
from storage.translation_layout import get_translation_layout, render_translation_background


def handle_translation_layout(handler, paper_id, page_number):
    try:
        success(handler, get_translation_layout(paper_id, page_number))
    except FileNotFoundError:
        error(handler, '原始 PDF 不存在，仍可使用连续阅读', 404)
    except (ValueError, RuntimeError):
        error(handler, '页面无法排版，请使用连续阅读', 422)


def handle_translation_background(handler, paper_id, page_number):
    version = parse_qs(urlparse(handler.path).query).get('v', [''])[0]
    try:
        content = render_translation_background(paper_id, page_number, version)
        handler.send_response(200)
        handler.send_header('Content-Type', 'image/png')
        handler.send_header('Content-Length', str(len(content)))
        handler.send_header('Cache-Control', 'private, max-age=3600')
        handler.end_headers()
        handler.wfile.write(content)
    except FileNotFoundError:
        error(handler, '原始 PDF 不存在', 404)
    except ValueError:
        error(handler, '译文已更新，请重新载入排版', 409)
    except RuntimeError:
        error(handler, '页面无法显示，请使用连续阅读', 422)
