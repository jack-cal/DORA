"""Run the actual frozen executables with temporary data and no Python on PATH."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import contextlib
import shutil
import uuid

WORK = Path(__file__).resolve().parent.parent / 'build/windows'
WORK.mkdir(parents=True, exist_ok=True)


@contextlib.contextmanager
def smoke_directory(prefix):
    # Inherit the workspace ACL so the frozen child can open the test database.
    root = WORK / (prefix + uuid.uuid4().hex)
    root.mkdir()
    try:
        yield str(root)
    finally:
        shutil.rmtree(root)


def wait_until(predicate, timeout=20):
    end = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() >= end:
            raise RuntimeError('Packaged application smoke deadline exceeded')
        time.sleep(.1)


def launcher_smoke(bundle):
    """Exercise the portable batch entry without vendor wheels or Python PATH."""
    with smoke_directory('launcher-smoke-') as temporary:
        root = Path(temporary).resolve()
        environment = dict(os.environ)
        system = Path(environment['SYSTEMROOT'])
        environment['PATH'] = os.pathsep.join((str(system / 'System32'), str(system)))
        for name in ('PYTHONPATH', 'PYTHONHOME', 'SUMUWW_PYTHON', 'VIRTUAL_ENV'):
            environment.pop(name, None)
        # Pass the native cmd.exe command line. list2cmdline quoting is for
        # ordinary Windows programs and escapes quotes differently from /c.
        command = ('"' + str(system / 'System32/cmd.exe') + '" /d /s /c ""'
                   + str(bundle / 'run.cmd') + '" node --network regtest --database "'
                   + str(root / 'a path with spaces.sqlite') + '" info"')
        completed = subprocess.run(command, cwd=root, env=environment,
                                   capture_output=True, text=True, encoding='utf-8',
                                   timeout=15, check=False)
        assert completed.returncode == 0
        assert json.loads(completed.stdout)['height'] == 0
        assert not list((bundle / 'vendor').glob('*.whl'))
    return 'portable_cmd_binary_preference_no_vendor_wheels_and_quoted_path'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=WORK.parents[1] / 'bin/SUMUWW')
    parser.add_argument('--launcher-only', action='store_true', help='Append only the focused batch launcher check')
    parser.add_argument('--node-only', action='store_true', help='Verify frozen node and launcher; inspect GUI separately')
    options = parser.parse_args(argv)
    bundle = options.bundle.resolve()
    node_exe, gui_exe = bundle / 'SUMUWW-node.exe', bundle / 'SUMUWW.exe'
    result_path = WORK / 'build_result.json'
    build = json.loads(result_path.read_text(encoding='utf-8'))
    if options.launcher_only:
        if not build.get('smoke_tests') or build['smoke_tests']['exit'] != 0:
            raise RuntimeError('Run the actual executable smoke before the focused launcher check')
        check = launcher_smoke(bundle)
        if check not in build['smoke_tests']['checks']:
            build['smoke_tests']['checks'].append(check)
        build['bundle_bytes'] = sum(path.stat().st_size for path in bundle.rglob('*') if path.is_file())
        result_path.write_text(json.dumps(build, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(json.dumps({'exit': 0, 'check': check}, ensure_ascii=False))
        return 0
    checks = []
    children = []
    with smoke_directory('binary-smoke-') as temporary:
        root = Path(temporary)
        environment = dict(os.environ)
        system = Path(environment['SYSTEMROOT'])
        environment['PATH'] = os.pathsep.join((str(system / 'System32'), str(system)))
        environment['LOCALAPPDATA'] = str(root / 'user-state')
        environment['DORA_DATA_DIR'] = str(root / 'gui-node')
        for name in ('PYTHONPATH', 'PYTHONHOME', 'SUMUWW_PYTHON', 'TCL_LIBRARY', 'TK_LIBRARY', 'VIRTUAL_ENV'):
            environment.pop(name, None)
        environment['PYTHONDONTWRITEBYTECODE'] = '1'

        def run(*args, json_output=True):
            complete = subprocess.run([str(node_exe), *map(str, args)], cwd=root,
                                      env=environment, capture_output=True, text=True,
                                      encoding='utf-8', timeout=40, check=False)
            if complete.returncode:
                raise RuntimeError(f'Packaged CLI command failed: {args[0]}, exit={complete.returncode}')
            return json.loads(complete.stdout) if json_output else complete.stdout

        def status(path):
            try:
                return json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                return None

        try:
            assert 'wallet-create' in run('--help', json_output=False)
            assert '--allow-internet' in run('peer', '--help', json_output=False)
            expected_version = build['version']
            assert expected_version in run('--version', json_output=False)
            checks.append('console_help_version_and_peer_help')
            # A separate public-profile database must not silently use the
            # standalone offline test miner. This does not solve SUMUWW PoW.
            sumuww_database = root / 'sumuww-offline.sqlite'
            denied = subprocess.run(
                [str(node_exe), 'node', '--network', 'dora', '--database', str(sumuww_database),
                 'mine-test', '--key-id', '1'], cwd=root, env=environment,
                capture_output=True, text=True, encoding='utf-8', timeout=15, check=False)
            assert denied.returncode == 2
            assert 'connected, synchronized node' in json.loads(denied.stderr)['message'], denied.stderr
            assert run('node', '--network', 'dora', '--database', sumuww_database, 'info')['height'] == 0
            checks.append('frozen_cli_public_profile_offline_mining_rejected_without_block')
            database = root / 'node.sqlite'
            prefix = ('node', '--network', 'regtest', '--database', database)
            assert run(*prefix, 'info')['height'] == 0
            password = root / 'password.txt'
            password.write_text('SUMUWW-frozen-smoke-2026\n', encoding='utf-8')
            alice, bob = root / 'alice.json', root / 'bob.json'
            alice_info = run(*prefix, 'wallet-create', '--wallet', alice, '--password-file', password)
            bob_info = run(*prefix, 'wallet-create', '--wallet', bob, '--password-file', password)
            assert alice_info['address'] != bob_info['address']
            mined = run(*prefix, 'mine', '--address', alice_info['address'], '--count', '100')
            assert mined['height'] == 100
            sent = run(*prefix, 'wallet-send', '--wallet', alice, '--password-file', password,
                       '--to-address', bob_info['address'], '--amount', '3', '--fee', '0.001')
            assert sent['status'] == 'local mempool' and len(sent['txid']) == 64
            checks.append('bundled_sqlite_coincurve_cryptography_wallet_mine_and_send')
            backup, restored = root / 'backup.json', root / 'restored.json'
            run(*prefix, 'wallet-backup', '--wallet', alice, '--backup', backup, '--password-file', password)
            restored_info = run(*prefix, 'wallet-restore', '--wallet', restored, '--backup', backup, '--password-file', password)
            assert restored_info['address'] == alice_info['address']
            checks.append('encrypted_backup_restore_preserves_address')

            source_ready, source_stop = root / 'source-ready.json', root / 'source-stop'
            target_ready, target_stop = root / 'target-ready.json', root / 'target-stop'
            common = ['peer', '--network', 'regtest', '--allow-internet', '--poll-interval', '.1', '--timeout', '2']
            source = subprocess.Popen([str(node_exe), *common, '--database', str(database),
                                       '--listen', '0.0.0.0:0', '--ready-file', str(source_ready),
                                       '--stop-file', str(source_stop)], cwd=root, env=environment,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            children.append(source)
            source_state = wait_until(lambda: status(source_ready))
            target = subprocess.Popen([str(node_exe), *common, '--database', str(root / 'target.sqlite'),
                                       '--listen', '127.0.0.1:0', '--peer', f"localhost:{source_state['listen']['port']}",
                                       '--ready-file', str(target_ready), '--stop-file', str(target_stop)],
                                      cwd=root, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            children.append(target)

            def relayed():
                state = status(target_ready)
                return state if state and state['height'] == 100 and state['mempool'] == 1 else None

            state = wait_until(relayed, 25)
            assert state['internet_connectivity_enabled'] and state['peers'] >= 1
            wait_until(lambda: (status(target_ready) or {}).get('mining_ready'))
            assert run(*prefix, 'mine', '--address', bob_info['address'], '--count', '1')['height'] == 101
            wait_until(lambda: (status(target_ready) or {}).get('height') == 101)
            source_stop.touch()
            target_stop.touch()
            assert source.wait(10) == target.wait(10) == 0
            assert run('node', '--network', 'regtest', '--database', root / 'target.sqlite', 'verify')['active_chain_replayed']
            checks.append('two_frozen_daemons_real_localhost_dns_block_tx_relay_confirmation_peer_sync_replay_and_close')

            if options.node_only:
                checks.append(launcher_smoke(bundle))
                build['smoke_tests'] = {'exit': 0, 'checks': checks,
                    'all_data_temporary': True,
                    'scope': 'Frozen node and batch launcher on this Windows PC; GUI not exercised by --node-only'}
                build['requires_system_python'] = False
                result_path.write_text(json.dumps(build, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
                print(json.dumps(build['smoke_tests'], ensure_ascii=False))
                return 0

            assert (bundle / '_internal' / 'assets' / 'sumuww_symbol.png').is_file()
            gui = subprocess.Popen([str(gui_exe), '--directory', str(root / 'gui-node'), '--network', 'regtest'],
                                   cwd=root, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            children.append(gui)
            powershell = system / 'System32/WindowsPowerShell/v1.0/powershell.exe'

            def gui_window():
                if gui.poll() is not None:
                    raise RuntimeError('Frozen GUI exited before presenting its window')
                command = (f'$guiProcess = Get-Process -Id {gui.pid}; $guiProcess.Refresh(); '
                           '[pscustomobject]@{handle=$guiProcess.MainWindowHandle.ToInt64(); '
                           'title=$guiProcess.MainWindowTitle} | ConvertTo-Json -Compress')
                complete = subprocess.run([str(powershell), '-NoProfile', '-Command', command],
                                          capture_output=True, text=True, timeout=10, check=True,
                                          creationflags=subprocess.CREATE_NO_WINDOW)
                window = json.loads(complete.stdout)
                return window if window['handle'] and 'SUMUWW' in window['title'] else None

            window = wait_until(gui_window)
            wait_until(lambda: (root / 'gui-node' / 'node.sqlite').is_file())
            close_command = f'$guiProcess = Get-Process -Id {gui.pid}; $guiProcess.CloseMainWindow()'
            closed = subprocess.run([str(powershell), '-NoProfile', '-Command', close_command],
                                    capture_output=True, text=True, timeout=10, check=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            assert 'True' in closed.stdout
            assert gui.wait(15) == 0
            assert run('node', '--network', 'regtest', '--database', root / 'gui-node' / 'node.sqlite', 'info')['height'] == 0
            checks.append('frozen_tk_gui_logo_asset_start_temporary_chain_and_graceful_window_close')
        finally:
            for process in children:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(5)
    checks.append(launcher_smoke(bundle))
    build['smoke_tests'] = {'exit': 0, 'checks': checks, 'all_data_temporary': True,
                            'child_path': environment['PATH'],
                            'python_related_environment_removed': True,
                            'scope': 'Actual frozen executables on this Windows PC; no external peers or separate clean PC test'}
    build['requires_system_python'] = False
    result_path.write_text(json.dumps(build, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'exit': 0, 'checks': checks, 'requires_system_python': False}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
