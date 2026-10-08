from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / 'backend' / 'portable.py')],
    pathex=[str(root / 'backend')],
    binaries=[],
    datas=[(str(root / 'frontend'), 'frontend')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='YiRead',
          debug=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='YiRead')
