# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
curve_data, curve_binaries, curve_imports = collect_all('coincurve')

a = Analysis(
    ['server.py'],
    pathex=['vendor'],
    binaries=curve_binaries,
    datas=[('dist', 'dist'), ('docs', 'docs')] + curve_data,
    hiddenimports=['sumuww.dgw', '_cffi_backend'] + curve_imports,
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
    name='SUMUWW-Explorer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
