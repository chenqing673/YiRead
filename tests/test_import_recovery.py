"""Import failures stay retryable without publishing incomplete library entries."""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from core import config
from api import import_api
from storage import importer
from storage.library import list_library
from storage.pdf_parser import parse_pdf
from utils.json_io import write_json_atomic


class ImportRecovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.config=patch.object(config,'CONFIG_FILE',str(self.root/'config.json'));self.config.start()
        write_json_atomic(config.CONFIG_FILE,{'data_dir':self.temp.name})
        self.pdf=self.root/'input.pdf'
        with pymupdf.open() as doc:
            page=doc.new_page();page.insert_text((50,100),'Research paragraph with readable science.');doc.save(self.pdf)
    def tearDown(self):
        self.config.stop();self.temp.cleanup()
    def test_parse_failure_never_publishes_partial_item_and_next_import_works(self):
        with patch.object(importer,'create_paper_json',side_effect=ValueError('fixture error')):
            with self.assertRaises(ValueError):importer.import_pdf(self.pdf)
        self.assertEqual(list_library(),[])
        self.assertEqual(list((self.root/'library'/'.imports').iterdir()),[])
        item=importer.import_pdf(self.pdf,file_name='original article.pdf')
        self.assertEqual(item['file_name'],'original article.pdf')
        self.assertTrue((self.root/'library'/item['id']/'source.pdf').is_file())
        self.assertTrue(importer.import_pdf(self.pdf)['duplicate'])
    def test_short_upload_path_preserves_long_original_name(self):
        filename='a'*210+'.pdf';boundary='import-test'
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/pdf\r\n\r\n'.encode()+self.pdf.read_bytes()+f'\r\n--{boundary}--\r\n'.encode())
        class Handler:pass
        handler=Handler();handler.headers={'Content-Type':'multipart/form-data; boundary='+boundary,'Content-Length':str(len(body))};handler.rfile=io.BytesIO(body)
        uploaded=import_api.save_uploaded_file(handler)
        self.assertEqual(uploaded['file_name'],filename)
        self.assertEqual(Path(uploaded['file_path']).name,'document.pdf')
        self.assertEqual(Path(uploaded['file_path']).read_bytes(),self.pdf.read_bytes())
    def test_cleanup_lock_does_not_mask_committed_http_success(self):
        uploaded={'file_path':str(self.pdf),'file_name':'research.pdf'}
        with patch.object(import_api,'require_token',return_value=True),patch.object(import_api,'save_uploaded_file',return_value=uploaded),patch('api.import_api.os.remove',side_effect=PermissionError('file lock')),patch('utils.json_io.time.sleep'),patch.object(import_api,'success') as success,patch.object(import_api,'error') as error,self.assertLogs(level='WARNING'):
            import_api.handle_import(object())
        success.assert_called_once();error.assert_not_called();self.assertEqual(len(list_library()),1)
    def test_transient_windows_read_lock_is_retried(self):
        fingerprint=importer.fingerprint;attempts=[]
        def intermittent(path):
            attempts.append(path)
            if len(attempts)==1:raise PermissionError('indexer')
            return fingerprint(path)
        with patch.object(importer,'fingerprint',side_effect=intermittent),patch('utils.json_io.time.sleep'):
            item=importer.import_pdf(self.pdf)
        self.assertEqual(len(attempts),2);self.assertTrue(item['id'])
    def test_optional_graphics_failure_keeps_valid_pdf_text(self):
        with patch('pymupdf.Page.get_drawings',side_effect=RuntimeError('odd drawing')),self.assertLogs(level='WARNING'):
            parsed=parse_pdf(self.pdf)
        self.assertIn('Research paragraph',parsed['pages'][0]['blocks'][0]['text'])


if __name__=='__main__':unittest.main()
