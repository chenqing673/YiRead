import datetime
import os
import shutil

from storage.library import get_library_path
from storage.id_generator import generate_paper_id
from storage.paper import create_paper_json
from utils.json_io import write_json_atomic
from storage.catalog import CATALOG_LOCK, fingerprint, extract_metadata
from storage.library import list_library
from utils.json_io import sharing_retry
import tempfile
from pathlib import Path

def _import_pdf(
    source_file, file_name=None
):
    library_path = get_library_path()
    os.makedirs(library_path,exist_ok=True)
    digest=sharing_retry(lambda:fingerprint(source_file))
    for existing in list_library():
        original=os.path.join(library_path,existing['id'],'source.pdf')
        existing_hash=existing.get('sha256')
        if not existing_hash and os.path.isfile(original):existing_hash=sharing_retry(lambda:fingerprint(original))
        if existing_hash==digest and os.path.isfile(original) and os.path.isfile(os.path.join(library_path,existing['id'],'paper.json')):
            return {**existing,'duplicate':True}
    metadata=sharing_retry(lambda:extract_metadata(source_file))
    paper_id = generate_paper_id()
    paper_dir = os.path.join(
        library_path,
        paper_id
    )
    # Publish only after both parsing and metadata writes succeed. The library
    # cannot expose a half-imported item to another tab or a duplicate upload.
    staging_root=Path(library_path)/'.imports';staging_root.mkdir(parents=True,exist_ok=True)
    display_name=file_name or os.path.basename(source_file)
    pdf_filename_without_ext = os.path.splitext(
        os.path.basename(
            display_name
        )
    )[0]
    item = {
        "id": paper_id,
        "title": pdf_filename_without_ext,
        "file_name": display_name,
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
    staging=Path(tempfile.mkdtemp(prefix='parse_',dir=staging_root))
    target_pdf=str(staging/'source.pdf')
    try:
        sharing_retry(lambda:shutil.copy2(source_file,target_pdf))
        sharing_retry(lambda:create_paper_json(str(staging)))
        # create_paper_json used the temporary directory name; retain the final ID.
        from utils.json_io import read_json
        parsed=read_json(str(staging/'paper.json'));parsed['id']=paper_id
        write_json_atomic(str(staging/'paper.json'),parsed)
        write_json_atomic(str(staging/'item.json'),item)
        sharing_retry(lambda:os.replace(str(staging),paper_dir))
    finally:
        # Only this newly-created staging directory is eligible for cleanup.
        if staging.exists() and staging.resolve().parent==staging_root.resolve() and staging.name.startswith('parse_'):
            try:sharing_retry(lambda:shutil.rmtree(staging))
            except OSError:
                import logging
                logging.warning('Import staging cleanup deferred: %s',staging,exc_info=True)
    return item


def import_pdf(source_file,file_name=None):
    with CATALOG_LOCK:return _import_pdf(source_file,file_name=file_name)
