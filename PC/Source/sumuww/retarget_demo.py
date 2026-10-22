"""Actual profile retargets, two-process relay and encrypted wallet recovery.

The laboratory uses interval16/timespan16 to exercise the same calculation
quickly. Controlled old timestamps in the initial mined history are explicit
test inputs. No public-network difficulty or launch conditions are selected.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from . import __version__
from .basic_demo import DEMO_PASSWORD
from .block import Block, mine_header
from .chain import Chain
from .errors import ValidationError
from .network_demo import Daemon, wait_for, matched, node_command
from .peerd import atomic_json
from .primitives import Header, hash_to_display, valid_target
from .profiles import RETARGET_LAB


def run(directory):
    directory = Path(directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Retarget demo needs a new or empty directory; existing files are preserved')
    directory.mkdir(parents=True, exist_ok=True)
    network = RETARGET_LAB
    password_file = directory / 'PUBLIC-DEMO-PASSWORD.txt'
    password_file.write_text(DEMO_PASSWORD + '\n', encoding='utf-8')
    db_a, db_b = directory / 'node-a.sqlite', directory / 'node-b.sqlite'
    alice_wallet, bob_wallet = directory / 'alice.wallet.json', directory / 'bob.wallet.json'
    backup, restored = directory / 'bob.backup.json', directory / 'bob.restored.json'

    def command(database, *arguments):
        return node_command(database, *arguments, network=network.name)

    def wallet(database, operation, path, *extra):
        return command(database, operation, '--wallet', str(path), '--password-file', str(password_file), *extra)

    alice = wallet(db_a, 'wallet-create', alice_wallet)
    bob = wallet(db_b, 'wallet-create', bob_wallet)
    assert alice['address'].startswith('dtl1') and bob['address'].startswith('dtl1')
    boundaries = []
    clock = {'now': network.genesis.header.timestamp + 1}
    with Chain(db_a, network=network, clock=lambda: clock['now']) as chain:
        # Mine real blocks through six adjustment boundaries with known times.
        headers = {0: network.genesis.header}
        wrong_bits_rejected = False
        for height in range(1, 101):
            clock['now'] = network.genesis.header.timestamp + height
            from .address import decode_address
            block = chain.make_block(decode_address(alice['address'], network=network))
            if height == 16:
                before = chain.info()
                header = block.header
                wrong = Header(header.version, header.previous_hash, header.merkle_root,
                               header.timestamp, network.initial_bits, 0)
                wrong = Block(mine_header(wrong, pow_limit=network.pow_limit), block.transactions)
                try:
                    chain.accept_block(wrong)
                except ValidationError:
                    wrong_bits_rejected = True
                assert wrong_bits_rejected
                after = chain.info()
                assert all(before[key] == after[key] for key in ('height', 'tip', 'chainwork', 'utxo_commitment'))
            assert chain.accept_block(block)
            headers[height] = block.header
            if height % network.retarget_interval == 0:
                parent = headers[height - 1]
                first = headers[height - network.retarget_interval]
                old_target = valid_target(parent.bits, network.pow_limit)
                new_target = valid_target(block.header.bits, network.pow_limit)
                boundaries.append({'height': height, 'first_ancestor_height': height - network.retarget_interval, 'elapsed_seconds': parent.timestamp - first.timestamp, 'previous_bits': f'0x{parent.bits:08x}', 'accepted_bits': f'0x{block.header.bits:08x}', 'target_changed': new_target != old_target, 'block': hash_to_display(block.block_hash())})
        assert len(boundaries) == 6 and all(item['target_changed'] for item in boundaries)

    processes = []
    try:
        b = Daemon(directory, 'node-b', db_b, network=network.name)
        processes.append(b)
        ready = wait_for('laboratory node B readiness', b.status)
        a = Daemon(directory, 'node-a', db_a, ((ready['listen']['host'], ready['listen']['port']),), network=network.name)
        processes.append(a)
        wait_for('100 blocks including six real retargets', lambda: matched(a, b, 100))
        payment = wallet(db_a, 'wallet-send', alice_wallet, '--to-address', bob['address'], '--amount', '3', '--fee', '0.001')
        wait_for('laboratory payment relay', lambda: matched(a, b, 100, 1))
        command(db_b, 'mine', '--address', alice['address'])
        wait_for('laboratory payment confirmation', lambda: matched(a, b, 101))
        assert command(db_b, 'balance', '--address', bob['address'])['total_smw'] == '3.00000000'
        wallet(db_b, 'wallet-backup', bob_wallet, '--backup', str(backup))
        recovered = wallet(db_b, 'wallet-restore', restored, '--backup', str(backup))
        assert recovered['address'] == bob['address']
        recovery_payment = wallet(db_b, 'wallet-send', restored, '--to-address', alice['address'], '--amount', '1', '--fee', '0.001')
        wait_for('restored laboratory key transaction relay', lambda: matched(a, b, 101, 1))
        command(db_a, 'mine', '--address', alice['address'])
        wait_for('restored laboratory key transaction confirmation', lambda: matched(a, b, 102))
        a.stop()
        restarted = Daemon(directory, 'node-a-restarted', db_a, ((ready['listen']['host'], ready['listen']['port']),), network=network.name)
        processes.append(restarted)
        wait_for('restarted node after retargets', lambda: matched(restarted, b, 102))
        verified = [command(db, 'verify') for db in (db_a, db_b)]
        assert all(item['active_chain_replayed'] for item in verified)
        assert verified[0]['tip'] == verified[1]['tip'] and verified[0]['utxo_commitment'] == verified[1]['utxo_commitment']
        balances = [command(db, 'balance', '--address', bob['address'])['total_smw'] for db in (db_a, db_b)]
        assert balances == ['1.99900000'] * 2
        result = {'application_version': __version__, 'network': network.name, 'scope': 'two independent processes on one Windows host; accelerated laboratory, not public-network launch', 'public_network_ready': False, 'profile': network.profile_id, 'genesis': hash_to_display(network.genesis.block_hash()), 'retarget_interval': network.retarget_interval, 'target_timespan': network.target_timespan, 'initial_timestamps': 'controlled genesis time + block height; mined blocks with verified PoW', 'retarget_boundaries': boundaries, 'wrong_bits_with_valid_pow_rejected': wrong_bits_rejected, 'wallets': {'random_encrypted_keys': True, 'public_demo_password': True, 'alice_address': alice['address'], 'bob_address': bob['address']}, 'payment': {'txid': payment['txid'], 'relayed_and_confirmed': True}, 'recovery': {'same_address': True, 'restored_key_spend_txid': recovery_payment['txid'], 'relayed_and_confirmed': True, 'bob_balance_both_nodes_smw': balances}, 'restart': {'tips_and_utxos_match': True, 'both_databases_replayed': True, 'height': verified[0]['height']}, 'final_chain': verified[0]}
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
    assert result['daemon_exit_codes'] == [0, 0, 0]
    atomic_json(directory / 'retarget_demo_result.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Actual block retarget, wallet recovery and two-process laboratory demonstration')
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
