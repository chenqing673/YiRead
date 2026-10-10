"""Exercise the actual release in a clean, Unicode path without a Python PATH."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen
import zipfile
import fitz

archive = Path(__file__).resolve().parents[1] / 'dist' / 'YiRead-Windows-x64.zip'


def fetch(path, data=None, headers=None):
    with urlopen(Request('http://127.0.0.1:8765' + path, data=data, headers=headers or {}), timeout=10) as response:
        return response.read()


def main():
    # Never let this standalone release test send writes to an existing service.
    try:
        fetch('/api/library')
    except OSError:
        pass
    else:
        raise RuntimeError('Port 8765 is already serving YiRead; stop it before testing the portable release.')
    with tempfile.TemporaryDirectory(prefix='YiRead-中文 空格-') as temp:
        with zipfile.ZipFile(archive) as release:
            assert not any('/data/' in name.replace('\\', '/') for name in release.namelist())
            release.extractall(temp)
        app = Path(temp) / 'YiRead'
        env = os.environ.copy()
        windows_dir = next((value for key, value in env.items() if key.lower() == 'systemroot'), r'C:\Windows')
        env['PATH'] = str(Path(windows_dir) / 'System32')
        with open(Path(temp) / 'output.log', 'wb') as output:
            process = subprocess.Popen([str(app / 'YiRead.exe')], cwd=temp, env=env,
                                       stdout=output, stderr=output, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                for attempt in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Packaged process exited before startup')
                    try:
                        fetch('/api/library')
                        break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('Startup timeout')
                assert b'YiRead' in fetch('/')
                token = json.loads(fetch('/api/token'))['data']['token']
                pdf = fitz.open()
                page = pdf.new_page()
                page.insert_text((72, 72), 'Portable PDF import and rendering test.')
                payload = pdf.tobytes()
                pdf.close()
                boundary = 'YiReadPortableSmoke'
                body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="sample.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
                        + payload + f'\r\n--{boundary}--\r\n'.encode())
                item = json.loads(fetch('/api/import', body, {'Content-Type': 'multipart/form-data; boundary=' + boundary, 'X-Token': token}))
                assert item['status'] == 'ok', item
                paper_id = item['data']['id']
                assert fetch('/api/pdf-page/' + paper_id + '/1').startswith(b'\x89PNG')
                assert (app / 'data' / 'library' / paper_id / 'source.pdf').exists()
                print('PASS: packaged startup, homepage, token, PDF import/render and portable data; no Python PATH')
            finally:
                process.terminate()
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
