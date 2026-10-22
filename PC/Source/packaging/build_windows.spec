# Build three executable entry points into one shared Windows onedir bundle.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

SOURCE = Path(os.environ['SUMUWW_BUILD_SOURCE']).resolve()
extra_data = [(str(SOURCE / 'assets' / 'sumuww_symbol.png'), 'assets'),
              (str(SOURCE / 'assets' / 'brand'), 'assets/brand'),
              (str(SOURCE / 'assets' / 'sumuww_ui_logo.png'), 'assets'),
              (str(SOURCE / 'assets' / 'sumuww_window_icon.png'), 'assets'),
              (str(SOURCE / 'assets' / 'sumuww.ico'), 'assets'),
              (str(SOURCE / 'assets' / 'bootstrap-nodes.json'), 'assets'),
              (str(SOURCE / 'assets' / 'locales'), 'assets/locales'),
              (str(SOURCE / 'assets' / 'fonts'), 'assets/fonts'),
              (str(SOURCE / 'assets' / 'privacy'), 'assets/privacy'),
              (str(SOURCE / 'assets' / 'bip39'), 'assets/bip39')]
extra_binaries = []
extra_hidden = ['_cffi_backend', 'sqlite3', 'tkinter']
for package in ('coincurve', 'cryptography','py_ecc','nacl','eth_utils','eth_typing','eth_hash','cytoolz'):
    package_data, package_binaries, package_hidden = collect_all(package)
    extra_data += package_data
    extra_binaries += package_binaries
    extra_hidden += package_hidden
for package in ('cffi', 'pycparser'):
    extra_data += copy_metadata(package)

# Keep the application's original fonts and styles; use the audited Tk build
# that explicitly selects ClearType Windows font rendering.
font_runtime = SOURCE / 'vendor' / 'tk-font-quality' / 'tk86t.dll'
assert font_runtime.is_file(), 'Audited Windows Tk font runtime is missing'
extra_binaries.append((str(font_runtime), '.'))

gui = Analysis(
    [str(SOURCE / 'sumuww_gui_entry.py')], pathex=[str(SOURCE)],
    binaries=extra_binaries, datas=extra_data, hiddenimports=extra_hidden,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['pytest', 'unittest', 'tests'], noarchive=False,
)
node = Analysis(
    [str(SOURCE / 'sumuww_node_entry.py')], pathex=[str(SOURCE)],
    binaries=extra_binaries, datas=extra_data, hiddenimports=extra_hidden,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['pytest', 'unittest', 'tests'], noarchive=False,
)
manager = Analysis(
    [str(SOURCE / 'sumuww_manager_entry.py')], pathex=[str(SOURCE)],
    binaries=extra_binaries, datas=extra_data, hiddenimports=extra_hidden,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['pytest', 'unittest', 'tests'], noarchive=False,
)
for analysis in (gui, node, manager):
    analysis.binaries = [entry for entry in analysis.binaries
                         if Path(entry[0]).name.lower() != 'tk86t.dll']
    analysis.binaries.append(('tk86t.dll', str(font_runtime), 'BINARY'))
    analysis.datas = [entry for entry in analysis.datas
                      if not entry[0].replace('\\', '/').startswith('_tk_data/')]
    tk_library = SOURCE / 'vendor' / 'tk-font-quality' / 'tk8.6'
    for file in sorted(tk_library.rglob('*')):
        if file.is_file():
            analysis.datas.append(('_tk_data/' + file.relative_to(tk_library).as_posix(),
                                   str(file), 'DATA'))
gui_exe = EXE(
    PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name='SUMUWW',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False, icon=str(SOURCE / 'assets/sumuww.ico'), version=str(SOURCE / 'assets/version-info.txt'), manifest=str(SOURCE / 'packaging/windows-gui.manifest'),
)
node_exe = EXE(
    PYZ(node.pure), node.scripts, [], exclude_binaries=True, name='SUMUWW-node',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=True, icon=str(SOURCE / 'assets/sumuww.ico'), version=str(SOURCE / 'assets/version-info.txt'),
)
manager_exe = EXE(
    PYZ(manager.pure), manager.scripts, [], exclude_binaries=True, name='SUMUWW-node-manager',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False, icon=str(SOURCE / 'assets/sumuww.ico'), version=str(SOURCE / 'assets/version-info.txt'), manifest=str(SOURCE / 'packaging/windows-gui.manifest'),
)
bundle = COLLECT(
    gui_exe, node_exe, manager_exe, gui.binaries, node.binaries, manager.binaries,
    gui.datas, node.datas, manager.datas,
    strip=False, upx=False, name='SUMUWW',
)
