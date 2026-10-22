"""Build Windows binaries from this source distribution.

Use a project-local Windows CPython 3.12 virtual environment with the pinned
runtime dependencies, build dependencies and vendored Tk rendering repair.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

WORK = Path(__file__).resolve().parent
WORKSPACE = WORK.parent
DEFAULT_SOURCE = WORKSPACE
BUILD_ENV = Path(sys.prefix)


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(part)
    return value.hexdigest()


def source_hashes(source):
    names = sorted((source / 'dora').rglob('*.py'))
    names += sorted((source / 'sumuww').rglob('*.py'))
    names += [source / name for name in ('sumuww_gui_entry.py', 'sumuww_node_entry.py', 'sumuww_manager_entry.py', 'run.py', 'run.cmd',
                                       'start.cmd', 'start-public.cmd', 'join-network.cmd',
                                       'requirements-win-cp312.lock', 'LICENSE', 'assets/sumuww_symbol.png')]
    names += sorted(path for path in (source / 'assets').rglob('*') if path.is_file())
    names += sorted(path for path in (source / 'vendor' / 'tk-font-quality').rglob('*') if path.is_file())
    return {path.relative_to(source).as_posix(): sha256(path) for path in names}


def copy_distribution_files(source, bundle):
    for name in ('run.cmd', 'start.cmd', 'start-public.cmd', 'join-network.cmd', 'allow-public-connections.cmd'):
        shutil.copy2(source / name, bundle / name)
    for name in ('BEACON_RECOVERY.md', 'HTLC_9100.md', 'HTLC_9100.html', 'CONNECTION_PROOFS_9000.md', 'CONNECTION_PROOFS_9000.html', 'UPGRADE_9000.txt', 'VERSION.txt', 'README.md', 'SOURCE_REVISION.md', 'WHITEPAPER.md', 'SUMUWW_PROTOCOL_SPEC.md', 'BOUNDARY_V4.md', 'BOUNDARY_V4.html', 'DOCUMENT_LAYOUT.json',
                 'Protocol.html', 'RPC_API.html', 'User_Guide.html', 'Whitepaper.html',
                 'RELEASE_NOTES.txt', 'DOCUMENT_SHA256SUMS.txt',
                 'requirements-win-cp312.lock', 'requirements.txt', 'LICENSE', 'LICENSE.md', 'LICENSE.txt'):
        if (source / name).is_file():
            shutil.copy2(source / name, bundle / name)
    packaging = bundle / 'packaging'
    packaging.mkdir(exist_ok=True)
    shutil.copy2(source / 'packaging' / 'BUILD_WINDOWS.md', packaging / 'BUILD_WINDOWS.md')
    if (source / 'docs').is_dir():
        shutil.copytree(source / 'docs', bundle / 'docs', dirs_exist_ok=True)
    for name in ('assets', 'vectors', 'programs', 'Whitepaper-English'):
        if (source / name).is_dir():
            shutil.copytree(source / name, bundle / name, dirs_exist_ok=True)
    runtime_manifest = bundle / '_internal' / 'assets' / 'bootstrap-nodes.json'
    assert runtime_manifest.is_file() and sha256(runtime_manifest) == sha256(source / 'assets' / 'bootstrap-nodes.json'), 'Frozen default bootstrap data missing'
    bip39_source = source / 'assets' / 'bip39'
    assert bip39_source.is_dir(), 'Frozen BIP39 wordlist directory missing'
    bip39_files = sorted(path for path in bip39_source.rglob('*') if path.is_file())
    assert bip39_files, 'Frozen BIP39 wordlist directory is empty'
    for wordlist in bip39_files:
        runtime_wordlist = bundle / '_internal' / 'assets' / 'bip39' / wordlist.relative_to(bip39_source)
        assert runtime_wordlist.is_file() and sha256(runtime_wordlist) == sha256(wordlist), 'Frozen BIP39 data missing or changed'
    tools = bundle / 'tools'
    tools.mkdir(exist_ok=True)
    shutil.copy2(source / 'tools' / 'allow-public-connections.ps1', tools / 'allow-public-connections.ps1')
    vendor = bundle / 'vendor'
    vendor.mkdir(exist_ok=True)
    shutil.copytree(source / 'vendor' / 'licenses', vendor / 'licenses', dirs_exist_ok=True)
    shutil.copy2(source / 'vendor' / 'THIRD_PARTY_NOTICES.md', vendor / 'THIRD_PARTY_NOTICES.md')
    shutil.copy2(source / 'vendor' / 'DEPENDENCY_PROVENANCE.json', vendor / 'DEPENDENCY_PROVENANCE.json')
    shutil.copytree(source / 'vendor' / 'tk-font-quality', vendor / 'tk-font-quality',
                    dirs_exist_ok=True, ignore=shutil.ignore_patterns('*.dll'))
    assert sha256(bundle / '_internal' / 'tk86t.dll') == sha256(source / 'vendor' / 'tk-font-quality' / 'tk86t.dll'), 'Patched Tk runtime missing from frozen build'
    licenses = bundle / 'licenses'
    shutil.copytree(source / 'vendor' / 'licenses', licenses / 'dependencies', dirs_exist_ok=True)
    notices = (source / 'vendor' / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
    notices = notices.replace('(licenses/', '(dependencies/').replace('(DEPENDENCY_PROVENANCE.json)', '(../vendor/DEPENDENCY_PROVENANCE.json)').replace('(tk-font-quality/', '(../vendor/tk-font-quality/')
    (licenses / 'THIRD_PARTY_NOTICES.md').write_text(notices, encoding='utf-8')
    shutil.copy2(Path(sys.base_prefix) / 'LICENSE.txt', licenses / 'LICENSE-Python.txt')
    tkinter_license = Path(sys.base_prefix) / 'tcl' / 'tk8.6' / 'license.terms'
    if tkinter_license.is_file():
        shutil.copy2(tkinter_license, licenses / 'LICENSE-Tk.txt')
    # This includes the bootloader exception permitting distribution of the
    # generated executable under the application's own license.
    distribution = importlib.metadata.distribution('pyinstaller')
    for item in distribution.files or ():
        if str(item).replace('\\', '/').endswith('/licenses/COPYING.txt'):
            shutil.copy2(distribution.locate_file(item), licenses / 'COPYING-PyInstaller.txt')
            break
    else:
        raise RuntimeError('PyInstaller bootloader license could not be located')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--build', action='store_true', help='Build only after the source owner confirms freeze')
    options = parser.parse_args(argv)
    source = options.source.resolve()
    if os.name != 'nt' or sys.version_info[:2] != (3, 12):
        parser.error('Use the dedicated Windows CPython 3.12 build environment')
    if sys.prefix == sys.base_prefix:
        parser.error('Use a project-local virtual environment; no global installs')
    for name in ('pyinstaller', 'coincurve', 'cryptography', 'cffi', 'pycparser'):
        importlib.metadata.version(name)
    if not options.build:
        print('Build environment ready; waiting for source freeze before --build')
        return 0
    before = source_hashes(source)
    environment = dict(os.environ, SUMUWW_BUILD_SOURCE=str(source), PYTHONDONTWRITEBYTECODE='1', SOURCE_DATE_EPOCH='0')
    environment.pop('PYTHONPATH', None)
    command = [sys.executable, '-B', '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--distpath', str(source / 'bin'), '--workpath', str(source / 'build/windows/pyinstaller'),
               str(WORK / 'build_windows.spec')]
    log = source / 'build/windows/build_windows.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w', encoding='utf-8') as output:
        completed = subprocess.run(command, cwd=source, env=environment, stdout=output,
                                   stderr=subprocess.STDOUT, check=False)
    if completed.returncode:
        raise RuntimeError(f'PyInstaller failed with exit {completed.returncode}; see {log}')
    after = source_hashes(source)
    if before != after:
        raise RuntimeError('Source changed during build; binaries cannot be marked final')
    bundle = source / 'bin' / 'SUMUWW'
    copy_distribution_files(source, bundle)
    binaries = {name: {'sha256': sha256(bundle / name), 'bytes': (bundle / name).stat().st_size}
                for name in ('SUMUWW.exe', 'SUMUWW-node.exe', 'SUMUWW-node-manager.exe')}
    result = {
        'application': 'SUMUWW', 'version': __import__('re').search(r'__version__ = "([^"]+)"', (source / 'sumuww/__init__.py').read_text()).group(1),
        'built_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_directory': str(source), 'bundle_directory': str(bundle),
        'build_environment': str(Path(sys.prefix)), 'python': sys.version,
        'builder_versions': {name: importlib.metadata.version(name) for name in
                             ('pyinstaller', 'pyinstaller-hooks-contrib', 'coincurve', 'cryptography', 'cffi', 'pycparser')},
        'build_exit': completed.returncode, 'source_unchanged_during_build': True,
        'source_sha256': before, 'binaries': binaries,
        'python_bundled': (bundle / '_internal' / 'python312.dll').is_file(),
        'bundle_bytes': sum(path.stat().st_size for path in bundle.rglob('*') if path.is_file()),
        'smoke_tests': None, 'requires_system_python': None,
        'signing': 'Unsigned; no publisher certificate was provided',
    }
    (log.parent / 'build_result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'build_exit': 0, 'bundle': str(bundle), 'bytes': result['bundle_bytes'],
                      'python_bundled': result['python_bundled']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
