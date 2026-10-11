"""Isolated update validation and real PowerShell replacement/rollback tests."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from core import updater


class Updates(unittest.TestCase):
    def test_http_token_and_install_guard(self):
        import threading
        from http.server import ThreadingHTTPServer
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        from server import YiReadHandler
        from core.security import get_token
        server = ThreadingHTTPServer(('127.0.0.1', 0), YiReadHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        try:
            with self.assertRaises(HTTPError) as denied: urlopen(base + '/api/update/status')
            self.assertEqual(denied.exception.code, 403)
            with urlopen(Request(base + '/api/update/status', headers={'X-Token': get_token()})) as response:
                self.assertEqual(json.load(response)['data']['current_version'], '1.0.3')
            with patch.object(updater, 'LATEST', None), self.assertRaises(HTTPError) as rejected:
                urlopen(Request(base + '/api/update/install', data=b'{}', headers={'X-Token': get_token()}))
            self.assertEqual(rejected.exception.code, 400)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def release(self, version='v1.0.4'):
        prefix = 'https://github.com/' + updater.REPOSITORY + '/releases/'
        return {'tag_name': version, 'html_url': prefix + 'tag/' + version, 'assets': [
            {'name': updater.ASSET_NAME, 'size': 100, 'digest': 'sha256:' + 'a' * 64,
             'browser_download_url': prefix + 'download/' + version + '/' + updater.ASSET_NAME}]}

    def test_versions_and_release(self):
        self.assertGreater(updater.version_tuple('v1.0.10'), updater.version_tuple('1.0.9'))
        with patch.object(updater, 'FROZEN', True):
            self.assertTrue(updater.release_info(self.release())['can_install'])
            self.assertFalse(updater.release_info(self.release('v1.0.1'))['available'])
            data = self.release(); data['assets'][0]['digest'] = None
            self.assertFalse(updater.release_info(data)['can_install'])
            data = self.release(); data['assets'][0]['browser_download_url'] = 'https://evil.example/a.zip'
            with self.assertRaises(ValueError): updater.release_info(data)
        with self.assertRaises(ValueError): updater.version_tuple('v1.0.3-beta')

    def test_archive_paths_and_data(self):
        for extra in ['YiRead/../evil', '/YiRead/evil', 'YiRead/data/translator.json',
                      'YiRead/_internal/CON.txt', 'YiRead/_internal/file.']:
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with zipfile.ZipFile(root / 'test.zip', 'w') as archive:
                    archive.writestr(extra, 'bad')
                with self.assertRaises(ValueError): updater.extract_release(root / 'test.zip', root / 'out')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with zipfile.ZipFile(root / 'test.zip', 'w') as archive:
                archive.writestr('YiRead/YiRead.exe', 'exe')
                archive.writestr('YiRead/_internal/python311.dll', 'dll')
            self.assertTrue((updater.extract_release(root / 'test.zip', root / 'out') / 'YiRead.exe').exists())

    def test_checksum_failure_keeps_original(self):
        import io
        fake = io.BytesIO(b'wrong')
        info = {'download_url': 'https://github.com/test', 'size': 5, 'digest': 'sha256:' + '0' * 64}
        with patch.object(updater, 'urlopen', return_value=fake):
            updater._download(info, None)
        self.assertEqual(updater.status()['status'], 'failed')
        self.assertIn('SHA256', updater.status()['message'])

    def test_powershell_replace_and_rollback_preserve_data(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory(prefix='更新 空格-') as temp:
                root = Path(temp); target = root / 'app'; source = root / 'incoming'
                for directory in (target, source):
                    (directory / '_internal').mkdir(parents=True)
                (target / 'YiRead.exe').write_text('old')
                (target / '_internal' / 'old.dll').write_text('old')
                (source / 'YiRead.exe').write_text('new')
                (source / '_internal' / 'new.dll').write_text('new')
                (target / 'data').mkdir(); (target / 'data' / 'translator.json').write_text('secret')
                (target / 'custom.txt').write_text('keep')
                manifest = root / 'manifest.json'
                manifest.write_text(json.dumps({'target': str(target), 'source': str(source), 'pid': 2147483647}), encoding='utf-8')
                # Substitute process launch only; exercise actual filesystem and rollback code.
                script = (ROOT / 'packaging' / 'apply-update.ps1').read_text(encoding='utf-8-sig')
                script = script.replace('    Add-Type -AssemblyName PresentationFramework', '    # no UI during test').replace("    [System.Windows.MessageBox]::Show('更新失败，已恢复旧程序。' + $failure, 'YiRead') | Out-Null", '    # no UI during test')
                script = script.replace("    Start-Process -FilePath", "    throw 'simulated restart failure'\n    Start-Process -FilePath") if fail else script.replace('    Start-Process -FilePath', '    Test-Launch -FilePath')
                script = script.replace("$ErrorActionPreference = 'Stop'", "$ErrorActionPreference = 'Stop'\nfunction Test-Launch { param($FilePath,$WorkingDirectory,$WindowStyle) }")
                helper = root / 'test.ps1'; helper.write_text(script, encoding='utf-8-sig')
                result = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(helper), '-Manifest', str(manifest)], capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((target / 'YiRead.exe').read_text(), 'old' if fail else 'new')
                self.assertEqual((target / 'data' / 'translator.json').read_text(), 'secret')
                self.assertEqual((target / 'custom.txt').read_text(), 'keep')
                self.assertTrue((target / '_internal' / ('old.dll' if fail else 'new.dll')).exists())


if __name__ == '__main__': unittest.main()
