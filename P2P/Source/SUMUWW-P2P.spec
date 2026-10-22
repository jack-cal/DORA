# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('tools/bitcoin-31.1', 'tools/bitcoin-31.1'), ('tools/runtime-manifest.json', 'tools'), ('smw_trade/locales', 'smw_trade/locales'), ('assets/fonts', 'assets/fonts'), ('vendor/assets/bip39', 'assets/bip39'), ('vendor/assets/bootstrap-nodes.json', 'assets/bootstrap-nodes.json')]
binaries = []
hiddenimports = []
hiddenimports += collect_submodules('py_ecc')
hiddenimports += collect_submodules('nacl')
tmp_ret = collect_all('coincurve')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['run.py'],
    pathex=['vendor'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='SUMUWW-P2P',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    icon='vendor/assets/sumuww.ico',
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SUMUWW-P2P',
)
