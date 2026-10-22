"""Prefer standalone Windows binaries; otherwise use the offline Python bootstrap."""

import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
WHEELS = {
    'coincurve-21.0.0-cp312-cp312-win_amd64.whl': '5dd7b66b83b143f3ad3861a68fc0279167a0bae44fe3931547400b7a200e90b1',
    'cryptography-50.0.1-cp311-abi3-win_amd64.whl': 'aed8db4f6d71c51efb89530e12d9464e7bf2923d46c3205dc794a2a93f8c0648',
    'cffi-2.1.0-cp312-cp312-win_amd64.whl': 'c97f080ea627e2863524c5af3836e2270b5f5dfff1f104392b959f8df0c5d384',
    'pycparser-3.0-py3-none-any.whl': 'b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992',
}
METADATA = ('coincurve-21.0.0', 'cryptography-50.0.1', 'cffi-2.1.0', 'pycparser-3.0')


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ('app', 'node', 'rpc', 'demo', 'peer', 'network-demo', 'basic-demo', 'retarget-demo', 'tests'):
        print('Usage: start.cmd [--directory data/node-a] | run.cmd app <arguments> | run.cmd node <arguments> | rpc --token-file FILE METHOD | peer <arguments> | demo/network-demo/basic-demo/retarget-demo --directory <fresh-directory> | tests', file=sys.stderr)
        return 2
    mode = args.pop(0)
    executable = 'SUMUWW.exe' if mode == 'app' else 'SUMUWW-node.exe' if mode in ('node', 'peer', 'rpc') else None
    if executable is not None:
        for directory in (ROOT, ROOT / 'bin' / 'SUMUWW'):
            binary = directory / executable
            if binary.is_file():
                command = [str(binary)] + ([mode] if mode in ('peer', 'rpc') else []) + args
                return subprocess.run(command, check=False).returncode
    if os.name != 'nt' or sys.version_info[:2] != (3, 12) or struct.calcsize('P') != 8:
        print('Use Windows AMD64 / CPython 3.12. Set SUMUWW_PYTHON to its executable, or use a venv with requirements.txt on another platform.', file=sys.stderr)
        return 2
    for name, expected in WHEELS.items():
        wheel = ROOT / 'vendor' / name
        if not wheel.is_file() or hashlib.sha256(wheel.read_bytes()).hexdigest() != expected:
            print('Dependency wheel missing or hash mismatch: ' + name, file=sys.stderr)
            return 2
    dependencies = ROOT / '.deps'
    os.chdir(ROOT)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    if not all((dependencies / (name + '.dist-info/METADATA')).is_file() for name in METADATA):
        install = subprocess.run([sys.executable, '-B', '-m', 'pip', 'install', '--disable-pip-version-check', '--no-index', '--find-links', str(ROOT / 'vendor'), '--require-hashes', '--no-compile', '--target', str(dependencies), '-r', str(ROOT / 'requirements-win-cp312.lock')], check=False)
        if install.returncode:
            return install.returncode
    sys.path[:0] = [str(dependencies), str(ROOT)]
    if mode == 'app':
        from sumuww.app import main as run_app
        return run_app(args) or 0
    if mode == 'tests':
        env = dict(os.environ)
        env['PYTHONPATH'] = os.pathsep.join([str(dependencies), str(ROOT), env.get('PYTHONPATH', '')])
        return subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v', *args], env=env, check=False).returncode
    if mode == 'demo':
        from sumuww.demo import main as run_demo
        return run_demo(args) or 0
    if mode == 'peer':
        from sumuww.peerd import main as run_peer
        return run_peer(args)
    if mode == 'rpc':
        from sumuww.rpc_client import main as run_rpc
        return run_rpc(args)
    if mode == 'network-demo':
        from sumuww.network_demo import main as run_network_demo
        return run_network_demo(args)
    if mode == 'basic-demo':
        from sumuww.basic_demo import main as run_basic_demo
        return run_basic_demo(args)
    if mode == 'retarget-demo':
        from sumuww.retarget_demo import main as run_retarget_demo
        return run_retarget_demo(args)
    from sumuww.__main__ import main as run_node
    return run_node(args)


if __name__ == '__main__':
    raise SystemExit(main())
