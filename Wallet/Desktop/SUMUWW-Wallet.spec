from pathlib import Path
from PyInstaller.utils.hooks import collect_all
ROOT = Path(SPECPATH)
CORE = ROOT.parents[1] / 'PC/Source'
datas = [(str(ROOT / 'locales'), 'locales'), (str(CORE / 'assets'), 'assets')]
binaries = []
hiddenimports = []
for package in ('coincurve', 'cryptography', 'py_ecc', 'nacl', 'eth_utils', 'eth_typing', 'eth_hash', 'cytoolz'):
    data, binary, hidden = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += hidden
a = Analysis([str(ROOT / 'run.py')], pathex=[str(CORE), str(ROOT)],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=['pytest', 'tests'], noarchive=False)
# Match the existing full-node font rendering and icon.
font_runtime = CORE / 'vendor/tk-font-quality'
a.binaries = [item for item in a.binaries if Path(item[0]).name.lower() != 'tk86t.dll']
a.binaries.append(('tk86t.dll', str(font_runtime / 'tk86t.dll'), 'BINARY'))
a.datas = [item for item in a.datas if not item[0].replace('\\', '/').startswith('_tk_data/')]
for path in (font_runtime / 'tk8.6').rglob('*'):
    if path.is_file():
        a.datas.append(('_tk_data/' + path.relative_to(font_runtime / 'tk8.6').as_posix(), str(path), 'DATA'))
exe = EXE(PYZ(a.pure), a.scripts, [], exclude_binaries=True, name='SUMUWW-Wallet',
          console=False, upx=False, icon=str(CORE / 'assets/sumuww.ico'),
          version=str(ROOT / 'version-info.txt'), manifest=str(CORE / 'packaging/windows-gui.manifest'))
coll = COLLECT(exe, a.binaries, a.datas, name='SUMUWW-Wallet', upx=False)
