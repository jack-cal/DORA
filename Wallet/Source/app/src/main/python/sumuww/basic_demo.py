"""Exercise random encrypted wallets, recovery and two-process transaction relay.

The fixed password is a PUBLIC DEMO fixture, never a recommended wallet password.
Demo keys are random and encrypted; this development chain carries no real funds.
"""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .chain import Chain
from .network_demo import Daemon, wait_for, matched, node_command, snapshot
from .peerd import atomic_json

DEMO_PASSWORD = 'SUMUWW-public-demo-password-only'


def run(directory):
    directory = Path(directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Basic demo needs a new or empty directory; existing files are preserved')
    directory.mkdir(parents=True, exist_ok=True)
    password_file = directory / 'PUBLIC-DEMO-PASSWORD.txt'
    password_file.write_text(DEMO_PASSWORD + '\n', encoding='utf-8')
    db_a, db_b = directory / 'node-a.sqlite', directory / 'node-b.sqlite'
    alice_wallet, bob_wallet = directory / 'alice.wallet.json', directory / 'bob.wallet.json'
    backup, restored = directory / 'bob.backup.json', directory / 'bob.restored.json'

    def wallet(database, command, path, *extra):
        return node_command(database, command, '--wallet', str(path), '--password-file', str(password_file), *extra)

    alice = wallet(db_a, 'wallet-create', alice_wallet)
    bob = wallet(db_b, 'wallet-create', bob_wallet)
    assert alice['address'] != bob['address']
    assert not db_a.exists() and not db_b.exists()
    node_command(db_a, 'mine', '--address', alice['address'], '--count', '100')
    processes = []
    try:
        b = Daemon(directory, 'node-b', db_b)
        processes.append(b)
        b_ready = wait_for('node B readiness', b.status)
        a = Daemon(directory, 'node-a', db_a, ((b_ready['listen']['host'], b_ready['listen']['port']),))
        processes.append(a)
        initial = wait_for('100-block synchronization', lambda: matched(a, b, 100))
        payment = wallet(db_a, 'wallet-send', alice_wallet, '--to-address', bob['address'], '--amount', '3', '--fee', '0.001')
        wait_for('wallet transaction relay', lambda: matched(a, b, 100, 1))
        node_command(db_b, 'mine', '--address', alice['address'])
        wait_for('payment confirmation', lambda: matched(a, b, 101))
        balances = [node_command(db, 'balance', '--address', bob['address'])['total_smw'] for db in (db_a, db_b)]
        assert balances == ['3.00000000'] * 2
        backed_up = wallet(db_b, 'wallet-backup', bob_wallet, '--backup', str(backup))
        recovered = wallet(db_b, 'wallet-restore', restored, '--backup', str(backup))
        assert backed_up['address'] == recovered['address'] == bob['address']
        assert backup.read_bytes() == bob_wallet.read_bytes() == restored.read_bytes()
        recovery_payment = wallet(db_b, 'wallet-send', restored, '--to-address', alice['address'], '--amount', '1', '--fee', '0.001')
        wait_for('restored-wallet transaction relay', lambda: matched(a, b, 101, 1))
        node_command(db_a, 'mine', '--address', alice['address'])
        final = wait_for('restored-wallet payment confirmation', lambda: matched(a, b, 102))
        final_balances = [wallet(db, 'wallet-balance', restored)['total_smw'] for db in (db_a, db_b)]
        assert final_balances == ['1.99900000'] * 2
        verified = [node_command(db, 'verify') for db in (db_a, db_b)]
        assert all(item['active_chain_replayed'] for item in verified)
        assert verified[0]['utxo_commitment'] == verified[1]['utxo_commitment']
        result = {'application_version': __version__, 'scope': 'local regtest; two independent processes on one Windows host', 'public_network_ready': False, 'transport': 'IPv4 loopback TCP', 'wallets': {'random_keys': True, 'encrypted_files': True, 'public_demo_password': True, 'alice_address': alice['address'], 'bob_address': bob['address'], 'different_addresses': True}, 'initial_sync': {'height': initial[0]['height'], 'tips_and_utxos_match': True}, 'payment': {'txid': payment['txid'], 'amount_smw': '3.00000000', 'fee_smw': '0.00100000', 'relayed_and_confirmed': True, 'bob_balance_both_nodes_smw': balances}, 'recovery': {'same_address': True, 'ciphertext_backup_equal': True, 'signed_spend_from_restored_wallet': recovery_payment['txid'], 'relayed_and_confirmed': True, 'bob_balance_both_nodes_smw': final_balances}, 'final': {'node_a': snapshot(final[0]), 'node_b': snapshot(final[1]), 'both_databases_replayed': True}}
    finally:
        failures = []
        for process in reversed(processes):
            try:
                process.stop()
            except Exception as error:
                failures.append(str(error))
        if failures:
            raise RuntimeError('; '.join(failures))
    result['daemon_exit_codes'] = [process.process.returncode for process in processes]
    assert result['daemon_exit_codes'] == [0, 0]
    atomic_json(directory / 'basic_demo_result.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Basic wallet, backup recovery and two-node demo with a PUBLIC demo password')
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args.directory), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(json.dumps({'error': type(error).__name__, 'message': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
