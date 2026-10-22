"""Run two independent daemon processes with separate DBs over loopback TCP."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from . import __version__
from .__main__ import test_key
from .chain import Chain
from .peerd import atomic_json
from .profiles import get_network


def child_environment():
    environment = dict(os.environ)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment['PYTHONPATH'] = os.pathsep.join(str(Path(item).resolve()) for item in sys.path if item and Path(item).is_dir())
    return environment


class Daemon:
    def __init__(self, directory, name, database, peers=(), *, network='regtest'):
        self.network = get_network(network).name
        self.name = name
        self.ready = directory / f'{name}.status.json'
        self.stop_file = directory / f'{name}.stop'
        self.log_path = directory / f'{name}.log.txt'
        self.log = self.log_path.open('w', encoding='utf-8')
        command = [sys.executable, '-B', '-m', 'sumuww.peerd', '--network', self.network, '--database', str(database), '--ready-file', str(self.ready), '--stop-file', str(self.stop_file), '--poll-interval', '0.1', '--timeout', '5']
        for host, port in peers:
            command += ['--peer', f'{host}:{port}']
        self.process = subprocess.Popen(command, env=child_environment(), stdout=self.log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

    def status(self):
        if self.process.poll() is not None:
            self.log.flush()
            raise RuntimeError(f'{self.name} exited: ' + self.log_path.read_text(encoding='utf-8')[-3000:])
        try:
            value = json.loads(self.ready.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        return value if value.get('pid') == self.process.pid and value.get('running') else None

    def stop(self):
        try:
            if self.process.poll() is None:
                self.stop_file.write_text('stop\n', encoding='utf-8')
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.terminate()
                    self.process.wait(timeout=5)
            if self.process.returncode != 0:
                raise RuntimeError(f'{self.name} failed to stop cleanly, exit {self.process.returncode}')
        finally:
            self.log.close()


def wait_for(description, predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise RuntimeError(f'Timed out waiting for {description}')


def node_command(database, *arguments, network='regtest'):
    name = get_network(network).name
    result = subprocess.run([sys.executable, '-B', '-m', 'dora', '--network', name, '--database', str(database), *arguments], env=child_environment(), capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return json.loads(result.stdout)


def matched(a, b, height, mempool=0):
    left, right = a.status(), b.status()
    if not left or not right or left['height'] != height or right['height'] != height or left['mempool'] != mempool or right['mempool'] != mempool:
        return None
    keys = ('height', 'tip', 'chainwork', 'utxos', 'utxo_commitment', 'mempool')
    return (left, right) if all(left[key] == right[key] for key in keys) else None


def snapshot(status):
    fields = ('profile', 'height', 'tip', 'chainwork', 'utxos', 'utxo_commitment', 'mempool', 'public_network_ready', 'peers', 'stats')
    return {key: status[key] for key in fields if key in status}


def run(directory):
    directory = Path(directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Network demo needs a new or empty directory; existing files are preserved')
    directory.mkdir(parents=True, exist_ok=True)
    db_a, db_b = directory / 'node-a.sqlite', directory / 'node-b.sqlite'
    with Chain(db_a) as seed:
        seed.mine(test_key(1).script_pubkey, 100)
    processes = []
    try:
        b = Daemon(directory, 'node-b', db_b)
        processes.append(b)
        b_ready = wait_for('node B readiness', b.status)
        a = Daemon(directory, 'node-a', db_a, ((b_ready['listen']['host'], b_ready['listen']['port']),))
        processes.append(a)
        initial = wait_for('100-block synchronization', lambda: matched(a, b, 100))
        recipient = test_key(2)
        payment = node_command(db_a, 'send-test', '--from-key-id', '1', '--to-pubkey', recipient.pubkey.hex(), '--amount', '3', '--fee', '0.001')
        relayed = wait_for('signed transaction relay to B', lambda: matched(a, b, 100, 1))
        node_command(db_b, 'mine-test', '--key-id', '3', '--count', '1')
        confirmed = wait_for('B mined block relay back to A', lambda: matched(a, b, 101))
        balances = [node_command(db, 'balance-test', '--key-id', '2')['total_smw'] for db in (db_a, db_b)]
        assert balances == ['3.00000000', '3.00000000']
        # Disconnect A, create different valid branches, then reconnect the DB.
        a.stop()
        node_command(db_a, 'mine-test', '--key-id', '1', '--count', '1')
        isolated_a = node_command(db_a, 'verify')
        node_command(db_b, 'mine-test', '--key-id', '3', '--count', '2')
        isolated_b = wait_for('B isolated height 103', lambda: (status if (status := b.status()) and status['height'] == 103 else None))
        assert isolated_a['height'] == 102 and isolated_a['tip'] != isolated_b['tip']
        restarted_a = Daemon(directory, 'node-a-restarted', db_a, ((b_ready['listen']['host'], b_ready['listen']['port']),))
        processes.append(restarted_a)
        recovered = wait_for('restart and greater-work branch convergence', lambda: matched(restarted_a, b, 103))
        verified = [node_command(db, 'verify') for db in (db_a, db_b)]
        assert all(item['active_chain_replayed'] for item in verified)
        assert verified[0]['utxo_commitment'] == verified[1]['utxo_commitment']
        result = {'application_version': __version__, 'scope': 'two independent processes on one Windows host; local regtest', 'transport': 'IPv4 loopback TCP', 'databases_separate': True, 'public_network_ready': False, 'initial_sync': {'height': 100, 'tips_and_utxos_match': True, 'node_a': snapshot(initial[0]), 'node_b': snapshot(initial[1])}, 'payment': {'txid': payment['txid'], 'amount_smw': '3.00000000', 'fee_smw': '0.00100000', 'mempool_relayed': relayed[1]['mempool'] == 1, 'confirmed_by_b_at_height': 101, 'bob_balance_on_both_nodes_smw': balances, 'node_a': snapshot(confirmed[0]), 'node_b': snapshot(confirmed[1])}, 'partition': {'node_a_height': 102, 'node_b_height': 103, 'different_branches_created': True}, 'reconnection': {'greater_work_branch_selected': True, 'tips_and_utxos_match': True, 'node_a': snapshot(recovered[0]), 'node_b': snapshot(recovered[1]), 'both_databases_replayed': True}, 'daemon_exit_codes': []}
    finally:
        errors = []
        for process in reversed(processes):
            if process.process.poll() is None:
                try:
                    process.stop()
                except Exception as error:
                    errors.append(str(error))
            elif not process.log.closed:
                process.log.close()
        if errors:
            raise RuntimeError('; '.join(errors))
    result['daemon_exit_codes'] = [process.process.returncode for process in processes]
    assert result['daemon_exit_codes'] == [0, 0, 0]
    atomic_json(directory / 'network_demo_result.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='SUMUWW two-process TCP demonstration with public test keys')
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args.directory), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({'error': type(exc).__name__, 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
