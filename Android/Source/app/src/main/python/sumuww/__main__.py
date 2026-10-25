"""Local SUMUWW node and encrypted legacy/seed wallet command line."""

import argparse
import getpass
import json
import os
import sqlite3
from pathlib import Path
import sys
import warnings

from . import __version__
from .profiles import get_network, NETWORK_NAMES
from .address import decode_address
from .keystore import (create_wallet, load_wallet, backup_wallet, restore_wallet,
                       create_hd_wallet, recover_hd_wallet, export_mnemonic, MAX_PASSWORD_BYTES)

from .block import Block, genesis_block
from .chain import Chain
from .errors import StorageError, UnsupportedFeature, ValidationError
from .primitives import format_amount, hash_to_display, parse_amount
from .transaction import Transaction, TxInput, TxOutput
from .wallet import RegtestKey, p2wpkh_script, sign_p2wpkh
from .fees import estimate_payment_fee
from .wallet_paths import reserved_node_paths, same_path, is_managed_privacy_path


def test_key(key_id):
    if key_id not in (1, 2, 3):
        raise ValueError('Only public local-test key IDs 1, 2 and 3 are available')
    return RegtestKey.from_int(key_id)


def create_test_payment(chain, key_id, recipient_pubkey, amount, fee):
    """Select mature confirmed outputs and sign using a publicly known fixture."""
    return create_payment(chain, test_key(key_id), p2wpkh_script(recipient_pubkey), amount, fee)


def create_payment(chain, key, recipient, amount, fee):
    """Select from one committed snapshot; submission revalidates atomically."""
    if type(amount) is not int or amount <= 0:
        raise ValueError('Payment amount must be positive')
    if type(fee) is not int or fee < 0:
        raise ValueError('Fee must be nonnegative')
    selected = []
    total = 0
    with chain.read_snapshot():
        pending = {item.outpoint() for tx in chain.mempool_transactions() for item in tx.inputs}
        next_height = chain.info()['height'] + 1
        for outpoint, coin in chain.list_utxos(key.script_pubkey):
            if coin.coinbase and next_height - coin.height < 100:
                continue
            tx_input = TxInput(*outpoint)
            if tx_input.outpoint() in pending:
                continue
            selected.append((tx_input, coin.output))
            total += coin.output.value
            if total >= amount + fee:
                break
    if total < amount + fee:
        raise ValueError('Insufficient mature confirmed funds after pending spends')
    outputs = [TxOutput(amount, recipient)]
    if total > amount + fee:
        outputs.append(TxOutput(total - amount - fee, key.script_pubkey))
    tx = Transaction(2, tuple(item for item, _ in selected), tuple(outputs))
    for index, (_, output) in enumerate(selected):
        tx = sign_p2wpkh(tx, index, output, key)
    return tx


def _same_path(left, right):
    return same_path(left, right)


def _guard_paths(args):
    """Reject wallet/password/output collisions before opening any database."""
    files = [(name, getattr(args, name, None)) for name in
             ('wallet', 'backup', 'password_file', 'hex_file', 'phrase_file', 'phrase_output')]
    files = [(name, path) for name, path in files if path is not None]
    for index, (name, path) in enumerate(files):
        for other_name, other_path in files[index + 1:]:
            if _same_path(path, other_path):
                raise ValueError(f'{name} and {other_name} paths must be separate')
    # Wallet-only commands do not require --database. Still reserve the ordinary
    # node filenames in each referenced directory, without looking up or reading
    # a user's active data directory. An explicit database also reserves its
    # custom-named sidecars and policy files.
    databases = ([args.database] if args.database is not None else
                 [Path(path).absolute().parent / 'node.sqlite' for _, path in files])
    reserved = [item for database in databases for item in reserved_node_paths(database)]
    for _, path in files:
        if (any(is_managed_privacy_path(path, database) for database in databases)
                or any(_same_path(path, item) for item in reserved)):
            raise ValueError('Input, wallet and backup paths must be separate from the database and its sidecars')


def _password(args, *, creating=False):
    if args.password_file is not None:
        with args.password_file.open('rb') as stream:
            raw = stream.read(MAX_PASSWORD_BYTES + 3)
        if raw.endswith(b'\r\n'):
            raw = raw[:-2]
        elif raw.endswith(b'\n'):
            raw = raw[:-1]
        if not raw or len(raw) > MAX_PASSWORD_BYTES or b'\n' in raw or b'\r' in raw:
            raise ValueError('Password file must contain one UTF-8 line of 1 to 1024 bytes')
        try:
            return raw.decode('utf-8')
        except UnicodeError:
            raise ValueError('Password file must contain UTF-8 text') from None
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            password = getpass.getpass('Wallet password: ')
            if creating and getpass.getpass('Confirm wallet password: ') != password:
                raise ValueError('Wallet passwords do not match')
        except getpass.GetPassWarning:
            raise ValueError('Hidden password input is unavailable; use a secure terminal or --password-file') from None
    return password


def _hex_input(path):
    # Wire/object maximum is 4 MB; permit only the outer line ending beyond hex.
    with path.open('rb') as stream:
        raw = stream.read(8_000_003)
    if len(raw) > 8_000_002:
        raise ValueError('Hex input exceeds the supported object size')
    try:
        data = bytes.fromhex(raw.decode('utf-8-sig').strip())
    except (UnicodeError, ValueError):
        raise ValueError('Hex input must contain UTF-8 hexadecimal bytes') from None
    if len(data) > 4_000_000:
        raise ValueError('Hex input exceeds the supported object size')
    return data


def _public_wallet(key):
    result = {'address': key.address, 'pubkey': key.pubkey.hex(), 'script_pubkey': key.script_pubkey.hex(),
              'network': key.network.name, 'encrypted': True, 'single_key': not key.is_hd,
              'hd': key.is_hd, 'wallet_version': key.wallet_version}
    if key.is_hd:
        result['derivation_path'] = key.derivation_path
    return result


def _phrase_input(path):
    if path is None:
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            try:
                return getpass.getpass('24 English recovery words: ')
            except getpass.GetPassWarning:
                raise ValueError('Hidden recovery input is unavailable; use --phrase-file') from None
    with path.open('rb') as stream:
        raw = stream.read(1025)
    if not 1 <= len(raw) <= 1024:
        raise ValueError('Recovery phrase input is too large or empty')
    try:
        return raw.decode('utf-8-sig').strip()
    except UnicodeError:
        raise ValueError('Recovery phrase file must contain UTF-8 text') from None


def _phrase_output(path, phrase):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(phrase + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def _balance(chain, script):
    with chain.read_snapshot():
        return {'total_smw': format_amount(chain.balance(script)), 'spendable_in_next_block_smw': format_amount(chain.balance(script, mature_only=True)), 'pending_spends_excluded_from_balance': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=f'SUMUWW v{__version__} local chain tools and encrypted wallet; networking uses the node command.')
    parser.add_argument('--database', type=Path, help='Explicit SQLite path')
    parser.add_argument('--network', choices=NETWORK_NAMES, default='regtest', help='Select sumuww explicitly for the independent coin')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('info')
    commands.add_parser('verify')
    commands.add_parser('genesis')
    keys = commands.add_parser('test-key')
    keys.add_argument('--key-id', type=int, choices=(1, 2, 3), required=True)
    mining = commands.add_parser('mine-test')
    mining.add_argument('--key-id', type=int, choices=(1, 2, 3), required=True)
    mining.add_argument('--count', type=int, default=1)
    balance = commands.add_parser('balance-test')
    balance.add_argument('--key-id', type=int, choices=(1, 2, 3), required=True)
    payment = commands.add_parser('send-test')
    payment.add_argument('--from-key-id', type=int, choices=(1, 2, 3), required=True)
    payment.add_argument('--to-pubkey', required=True)
    payment.add_argument('--amount', required=True)
    payment.add_argument('--fee', default='0.001')
    commands.add_parser('mempool')
    for name in ('wallet-create', 'wallet-address', 'wallet-balance', 'wallet-send', 'wallet-backup',
                 'wallet-restore', 'wallet-recover-seed', 'wallet-export-seed'):
        command = commands.add_parser(name)
        command.add_argument('--wallet', type=Path, required=True, help='Encrypted wallet path')
        command.add_argument('--password-file', type=Path, help='Optional automation input; otherwise password is prompted without echo')
        if name == 'wallet-create':
            command.add_argument('--hd', action='store_true', help='Create a 24-word seed wallet; export its words explicitly with wallet-export-seed')
        if name == 'wallet-recover-seed':
            command.add_argument('--phrase-file', type=Path, help='Private recovery input file; otherwise words are prompted without echo')
        if name == 'wallet-export-seed':
            command.add_argument('--phrase-output', type=Path, required=True,
                                 help='New private plaintext recovery-word file; never printed in JSON output')
        if name in ('wallet-backup', 'wallet-restore'):
            command.add_argument('--backup', type=Path, required=True, help='Backup output for backup; backup input for restore')
        if name == 'wallet-send':
            command.add_argument('--to-address', required=True)
            command.add_argument('--amount', required=True)
            command.add_argument('--fee', default='auto', help='Automatic suggestion, or legacy total SMW fee')
            command.add_argument('--fee-rate', help='Manual yugeon/vB rate (up to three decimals)')
            command.add_argument('--fee-mode', choices=('slow','normal','fast'), default='normal')
    mining_address = commands.add_parser('mine')
    mining_address.add_argument('--address', required=True)
    mining_address.add_argument('--count', type=int, default=1)
    balance_address = commands.add_parser('balance')
    balance_address.add_argument('--address', required=True)
    for name in ('submit-transaction', 'submit-block'):
        command = commands.add_parser(name)
        command.add_argument('--hex-file', type=Path, required=True, help='UTF-8 file containing only hexadecimal bytes')
    args = parser.parse_args(argv)
    try:
        network = get_network(args.network)
        _guard_paths(args)
        key = None
        script = None
        submitted_object = None
        if args.command == 'submit-transaction':
            submitted_object = Transaction.deserialize(_hex_input(args.hex_file))
        elif args.command == 'submit-block':
            submitted_object = Block.deserialize(_hex_input(args.hex_file))
        if args.command.startswith('wallet-'):
            password = _password(args, creating=args.command in ('wallet-create', 'wallet-recover-seed'))
            if args.command == 'wallet-create':
                key = (create_hd_wallet if args.hd else create_wallet)(args.wallet, password, network=network)
            elif args.command == 'wallet-recover-seed':
                phrase = _phrase_input(args.phrase_file)
                key = recover_hd_wallet(args.wallet, password, phrase, network=network)
                phrase = None
            elif args.command == 'wallet-export-seed':
                key = load_wallet(args.wallet, password, network=network)
                phrase = export_mnemonic(args.wallet, password, network=network,
                                         expected_script=key.script_pubkey)
                _phrase_output(args.phrase_output, phrase)
                phrase = None
            elif args.command == 'wallet-backup':
                key = backup_wallet(args.wallet, args.backup, password, network=network)
            elif args.command == 'wallet-restore':
                key = restore_wallet(args.backup, args.wallet, password, network=network)
            else:
                key = load_wallet(args.wallet, password, network=network)
            password = None
        if args.command in ('mine', 'balance'):
            script = decode_address(args.address, network=network)
        if args.command == 'wallet-send':
            script = decode_address(args.to_address, network=network)
            amount = parse_amount(args.amount)
            if args.fee_rate is not None and args.fee != 'auto':
                raise ValueError('Choose a fee rate or a total fee, not both')
            fee = None if args.fee == 'auto' else parse_amount(args.fee)
            if fee is not None and fee > 100_000_000:
                raise ValueError('Manual fee exceeds the wallet fee limit')
            if amount <= 0:
                raise ValueError('Payment amount must be positive')
        if args.command in ('wallet-create', 'wallet-address', 'wallet-backup', 'wallet-restore',
                            'wallet-recover-seed', 'wallet-export-seed'):
            result = _public_wallet(key)
            result['operation'] = args.command
            if args.command == 'wallet-export-seed':
                result['phrase_file'] = str(args.phrase_output)
        elif args.command == 'test-key':
            key = test_key(args.key_id)
            result = {'test_only': True, 'publicly_known_key_id': args.key_id, 'pubkey': key.pubkey.hex(), 'script_pubkey': key.script_pubkey.hex()}
        elif args.command == 'genesis':
            block = network.genesis
            result = {'scope': 'development only', 'network': network.name, 'profile': network.profile_id, 'hash': hash_to_display(block.block_hash()), 'header_hex': block.header.serialize().hex(), 'block_hex': block.serialize().hex(), 'genesis_utxo_included': False, 'no_retarget': network.no_retarget, 'retarget_interval': network.retarget_interval, 'target_timespan': network.target_timespan, 'address_hrp': network.address_hrp, 'message_magic': network.message_magic.hex()}
        else:
            if args.database is None:
                parser.error('--database is required for chain commands')
            with Chain(args.database, network=network) as chain:
                if args.command in ('info', 'verify'):
                    result = chain.info()
                    if args.command == 'verify':
                        result['active_chain_replayed'] = True
                elif args.command in ('mine-test', 'mine'):
                    if network.name == 'dora':
                        raise ValueError('SUMUWW mining requires a connected, synchronized node; use SUMUWW.exe. Offline mining is available only on regtest/retarget-lab in this CLI')
                    blocks = chain.mine(script if args.command == 'mine' else test_key(args.key_id).script_pubkey, args.count)
                    result = {'generated': len(blocks), **chain.info()}
                elif args.command in ('balance-test', 'balance', 'wallet-balance'):
                    if args.command == 'balance-test':
                        script = test_key(args.key_id).script_pubkey
                    elif args.command == 'wallet-balance':
                        script = key.script_pubkey
                    result = _balance(chain, script)
                elif args.command == 'wallet-send':
                    with chain.read_snapshot():
                        suggestion = estimate_payment_fee(chain, key.script_pubkey, script, amount, mode=args.fee_mode, rate=args.fee_rate) if fee is None else None
                        fee = suggestion['fee_units'] if suggestion else fee
                        tx = create_payment(chain, key, script, amount, fee)
                    result = {'txid': hash_to_display(chain.submit_transaction(tx, allow_replacement=False)), 'transaction_hex': tx.serialize().hex(), 'fee_smw': format_amount(fee), 'total_smw': format_amount(amount + fee), 'fee_mode': 'automatic' if suggestion else 'manual', 'fee_source': suggestion['source'] if suggestion else 'manual', 'status': 'local mempool', 'from_address': key.address, 'to_address': args.to_address}
                elif args.command == 'send-test':
                    tx = create_test_payment(chain, args.from_key_id, bytes.fromhex(args.to_pubkey), parse_amount(args.amount), parse_amount(args.fee))
                    result = {'txid': hash_to_display(chain.submit_transaction(tx)), 'transaction_hex': tx.serialize().hex(), 'fee_smw': args.fee, 'status': 'local mempool'}
                elif args.command == 'mempool':
                    result = {'transactions': [{'txid': hash_to_display(tx.txid()), 'hex': tx.serialize().hex()} for tx in chain.mempool_transactions()]}
                elif args.command == 'submit-transaction':
                    tx = submitted_object
                    result = {'txid': hash_to_display(chain.submit_transaction(tx)), 'status': 'local mempool'}
                else:
                    block = submitted_object
                    result = {'block': hash_to_display(block.block_hash()), 'activated': chain.accept_block(block), **chain.info()}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValidationError, UnsupportedFeature, StorageError, ValueError, OSError, EOFError, sqlite3.Error) as exc:
        print(json.dumps({'error': type(exc).__name__, 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
