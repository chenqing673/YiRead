"""User-initiated GitHub Release updates for the portable Windows build."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import threading
from urllib.request import Request, urlopen
import zipfile

from core.runtime import APP_DIR, RESOURCE_DIR, FROZEN
from core.version import VERSION, REPOSITORY

ASSET_NAME = 'YiRead-Windows-x64.zip'
LIMIT = 512 * 1024 * 1024
LOCK = threading.RLock()
STATE = {'status': 'idle', 'progress': 0}
LATEST = None


def version_tuple(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value)
    if not match:
        raise ValueError('仅支持正式版本号 v主版本.次版本.修订号')
    return tuple(map(int, match.groups()))


def release_info(release):
    if release.get('draft') or release.get('prerelease'):
        raise ValueError('该版本不是正式发布版本')
    tag = release['tag_name']
    available = version_tuple(tag) > version_tuple(VERSION)
    prefix = f'https://github.com/{REPOSITORY}/releases/'
    page = release.get('html_url', '')
    if not page.startswith(prefix + 'tag/'):
        raise ValueError('发布页面地址不匹配')
    asset = next((x for x in release.get('assets', []) if x['name'] == ASSET_NAME), None)
    if asset:
        url = asset.get('browser_download_url', '')
        if not url.startswith(prefix + 'download/'):
            raise ValueError('下载地址不匹配')
    digest = asset.get('digest', '') if asset else ''
    verified = bool(re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest or ''))
    return {'current_version': VERSION, 'latest_version': tag, 'available': available,
            'notes': str(release.get('body') or '')[:20000], 'release_url': page,
            'download_url': asset['browser_download_url'] if asset else '',
            'size': asset.get('size', 0) if asset else 0, 'digest': digest,
            'can_install': bool(FROZEN and available and verified and asset and 0 < asset.get('size', 0) <= LIMIT)}


def check_update():
    global LATEST
    req = Request(f'https://api.github.com/repos/{REPOSITORY}/releases/latest',
                  headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'YiRead/' + VERSION,
                           'X-GitHub-Api-Version': '2022-11-28'})
    with urlopen(req, timeout=20) as response:
        release = json.loads(response.read(1024 * 1024))
    info = release_info(release)
    with LOCK:
        LATEST = info
    return info


def extract_release(archive, destination):
    """Reject traversal, symlinks, user data, and unexpected executable payloads."""
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        if sum(x.file_size for x in entries) > LIMIT * 3:
            raise ValueError('安装包解压大小超出限制')
        seen = set()
        for entry in entries:
            name = entry.filename.replace('\\', '/')
            path = PurePosixPath(name)
            parts = path.parts
            if not parts or parts[0] != 'YiRead' or '..' in parts or any(':' in p for p in parts):
                raise ValueError('安装包路径不合法')
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('安装包不允许符号链接')
            if len(parts) < 2:
                continue
            top = parts[1]
            if top not in ('YiRead.exe', '_internal', '使用说明.txt', '用户使用说明书.html'):
                raise ValueError('安装包包含非程序文件或用户数据')
            key = name.lower().rstrip('/')
            if key in seen:
                raise ValueError('安装包包含重复路径')
            seen.add(key)
            if any(p.rstrip(' .') != p or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?', p) for p in parts):
                raise ValueError('安装包包含不合法 Windows 路径')
        source.extractall(destination)
    root = destination / 'YiRead'
    if not (root / 'YiRead.exe').is_file() or not list((root / '_internal').glob('python3*.dll')):
        raise ValueError('缺少完整 Windows 运行文件')
    return root


def update_state(**values):
    with LOCK:
        STATE.update(values)


def status():
    with LOCK:
        return {**STATE, 'current_version': VERSION}


def install_update(server):
    with LOCK:
        if STATE['status'] in ('downloading', 'installing'):
            raise ValueError('更新已在进行中')
        if not LATEST or not LATEST['can_install']:
            raise ValueError('请先检查更新；自动安装需要免安装版及带 SHA256 校验值的正式安装包')
        info = LATEST.copy()
        STATE.update(status='downloading', progress=0, message='正在下载并校验新版')
    threading.Thread(target=_download, args=(info, server), daemon=True).start()
    return status()


def _download(info, server):
    stage = Path(tempfile.mkdtemp(prefix='YiRead-update-'))
    try:
        archive = stage / 'release.zip'
        digest = hashlib.sha256()
        count = 0
        with urlopen(Request(info['download_url'], headers={'User-Agent': 'YiRead/' + VERSION}), timeout=60) as response, archive.open('wb') as output:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                count += len(chunk)
                if count > LIMIT or count > info['size']:
                    raise ValueError('下载大小超出预期')
                output.write(chunk)
                digest.update(chunk)
                update_state(progress=int(count * 100 / info['size']))
        if count != info['size'] or digest.hexdigest().lower() != info['digest'].split(':')[1].lower():
            raise ValueError('安装包大小或 SHA256 校验失败，原程序未修改')
        package = extract_release(archive, stage)
        from core.translation_worker import JOB_LOCK, ACTIVE
        with JOB_LOCK:
            if ACTIVE:
                raise ValueError('翻译仍在运行，请暂停并等待完成后重新更新')
            update_state(status='installing', message='正在退出并替换程序；随后自动重新打开')
        script = stage / 'apply-update.ps1'
        shutil.copyfile(RESOURCE_DIR / 'apply-update.ps1', script)
        manifest = stage / 'update.json'
        manifest.write_text(json.dumps({'target': str(APP_DIR), 'source': str(package), 'pid': os.getpid()}, ensure_ascii=False), encoding='utf-8')
        powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        subprocess.Popen([str(powershell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-Manifest', str(manifest)],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        server.shutdown()
    except Exception as exc:
        update_state(status='failed', message='更新失败：' + str(exc))
        shutil.rmtree(stage, ignore_errors=True)
