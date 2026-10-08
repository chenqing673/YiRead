from api.base import success, error
from storage.pdf_view import get_pdf_layout, render_pdf_page


def handle_pdf_layout(handler, paper_id):
    try:
        result = get_pdf_layout(paper_id)
        if result is None:
            return error(handler,"source not found",404)
        success(handler,result)
    except Exception:
        error(handler,"PDF 无法解析，请打开原始文件检查",422)


def handle_pdf_page(handler,paper_id,page_number):
    try:
        result=render_pdf_page(paper_id,page_number)
        if result is None:
            return error(handler,"source not found",404)
        handler.send_response(200)
        handler.send_header("Content-Type","image/png")
        handler.send_header("Content-Length",str(len(result)))
        handler.send_header("Cache-Control","private, max-age=3600")
        handler.end_headers()
        handler.wfile.write(result)
    except ValueError:
        error(handler,"page not found",404)
    except Exception:
        error(handler,"PDF 页面无法显示",422)
