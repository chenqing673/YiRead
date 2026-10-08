import datetime
import os
import shutil

from storage.library import get_library_path
from storage.id_generator import generate_paper_id
from storage.paper import create_paper_json
from utils.json_io import write_json_atomic
from storage.catalog import CATALOG_LOCK, fingerprint, extract_metadata
from storage.library import list_library

def _import_pdf(
    source_file
):
    library_path = get_library_path()
    digest=fingerprint(source_file)
    for existing in list_library():
        original=os.path.join(library_path,existing['id'],'source.pdf')
        existing_hash=existing.get('sha256')
        if not existing_hash and os.path.isfile(original):existing_hash=fingerprint(original)
        if existing_hash==digest:return {**existing,'duplicate':True}
    metadata=extract_metadata(source_file)
    paper_id = generate_paper_id()
    paper_dir = os.path.join(
        library_path,
        paper_id
    )
    os.makedirs(
        paper_dir,
        exist_ok=True
    )
    target_pdf = os.path.join(
        paper_dir,
        "source.pdf"
    )
    shutil.copy2(
        source_file,
        target_pdf
    )
    pdf_filename_without_ext = os.path.splitext(
        os.path.basename(
            source_file
        )
    )[0]
    item = {
        "id": paper_id,
        "title": pdf_filename_without_ext,
        "file_name": os.path.basename(
            source_file
        ),
        "file_size": os.path.getsize(
            source_file
        ),
        "authors": [],
        "year": None,
        "source": "local",
        "status": "imported",
        "created_at": datetime.datetime.now().isoformat()
    }
    item.update(sha256=digest,tags=[],favorite=False,is_read=False)
    item.update(metadata)
    write_json_atomic(
        os.path.join(
            paper_dir,
            "item.json"
        ),
        item
    )
    try:
        create_paper_json(paper_dir)
    except Exception:
        shutil.rmtree(paper_dir)
        raise
    return item


def import_pdf(source_file):
    with CATALOG_LOCK:return _import_pdf(source_file)
