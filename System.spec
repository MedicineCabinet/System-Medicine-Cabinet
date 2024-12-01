# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['System.py'],
    pathex=[],
    binaries=[],
    datas=[('users', 'users'), ('sounds', 'sounds'), ('qr_codes', 'qr_codes'), ('qrcodes', 'qrcodes'), ('images', 'images'), ('door_status', 'door_status')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
