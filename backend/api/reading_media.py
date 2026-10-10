from urllib.parse import parse_qs,urlparse
from api.base import success,error
from storage.reading_media import get_reading_media,render_reading_media


def handle_reading_media(handler,paper_id):
    try:success(handler,get_reading_media(paper_id))
    except FileNotFoundError:error(handler,'原始 PDF 不存在',404)
    except (ValueError,RuntimeError):error(handler,'原图表暂时无法载入',422)


def handle_reading_media_image(handler,paper_id,page_number,asset_id):
    version=parse_qs(urlparse(handler.path).query).get('v',[''])[0]
    try:
        content=render_reading_media(paper_id,page_number,asset_id,version)
        handler.send_response(200);handler.send_header('Content-Type','image/png');handler.send_header('Content-Length',str(len(content)));handler.send_header('Cache-Control','private, max-age=3600');handler.end_headers();handler.wfile.write(content)
    except FileNotFoundError:error(handler,'原始 PDF 不存在',404)
    except LookupError:error(handler,'原图表不存在',404)
    except ValueError:error(handler,'原图表已更新，请重新载入',409)
    except RuntimeError:error(handler,'原图表暂时无法显示',422)
