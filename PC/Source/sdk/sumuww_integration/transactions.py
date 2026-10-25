"""Key-free transaction construction, digest inspection and signature attachment.

This is a SUMUWW JSON format, not PSBT. Previous transaction bytes bind input
amounts and scripts to their transaction IDs. Only the node can establish their
current unspent status. Request IDs identify bytes, not a trusted recipient.
"""
from dataclasses import replace
import hashlib
import json
import re

from sumuww.address import decode_address, encode_address
from sumuww.primitives import MAX_MONEY, checked_amount_sum, format_amount, hash_to_display
from sumuww.profiles import get_network
from sumuww.transaction import Transaction, TxInput, TxOutput, bip143_sighash_all
from sumuww.wallet import verify_p2wpkh

FORMAT = 'sumuww-external-signing-v1'
MAX_PACKAGE_BYTES = 16_000_000
MAX_INPUTS = 1000
BODY_FIELDS = {'format', 'network', 'genesis_hash', 'unsigned_tx', 'previous_transactions'}


def units(value, *, positive=False):
    if type(value) is not int or not (1 if positive else 0) <= value <= MAX_MONEY:
        raise ValueError('Amount must be an integer in smallest units within the money range')
    return value


def _hex(value, maximum=4_000_000):
    if (not isinstance(value, str) or len(value) > maximum * 2 or len(value) % 2
            or not re.fullmatch('[0-9a-f]*', value)):
        raise ValueError('Expected bounded lowercase hexadecimal bytes')
    return bytes.fromhex(value)


def _p2wpkh(script):
    if len(script) != 22 or script[:2] != b'\x00\x14':
        raise ValueError('The P2WPKH reference format supports native P2WPKH only')
    return script


def address_script(address, network):
    return _p2wpkh(decode_address(address, network=get_network(network)))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def _identifier(body):
    return hashlib.sha256(b'SUMUWW signing request v1\x00' + _canonical(body)).hexdigest()


def estimated_vsize(transaction):
    """Conservative upper bound for 73-byte signature + 33-byte public key."""
    sized = replace(transaction, inputs=tuple(replace(i, witness=(bytes(73), bytes(33)))
                                             for i in transaction.inputs))
    return (sized.weight() + 3) // 4


def create_package(network, previous_outputs, payments, change_address, *,
                   fee_units=None, fee_rate=None):
    """Use the supplied outputs in order; no key, database or network access.

    previous_outputs: [(previous_transaction_hex, output_index), ...]
    payments: [{'address': address, 'amount_units': integer}, ...]
    fee_rate: integer smallest units per virtual byte, mutually exclusive with fee.
    """
    profile = get_network(network)
    if (fee_units is None) == (fee_rate is None):
        raise ValueError('Specify exactly one total fee or fee rate')
    if fee_units is not None:
        units(fee_units)
    else:
        units(fee_rate, positive=True)
    if not isinstance(payments, list):
        raise ValueError('Invalid payment options')
    if not payments or len(payments) > 1000:
        raise ValueError('Supply between 1 and 1000 payment outputs')
    change = address_script(change_address, profile)
    targets = []
    for item in payments:
        if not isinstance(item, dict) or set(item) != {'address', 'amount_units'}:
            raise ValueError('Payment requires address and amount_units')
        targets.append(TxOutput(units(item['amount_units'], positive=True),
                                address_script(item['address'], profile)))
    payment_total = checked_amount_sum(o.value for o in targets)
    if not 1 <= len(previous_outputs) <= MAX_INPUTS:
        raise ValueError('Supply between 1 and 1000 explicitly selected previous outputs')
    inputs, previous, seen = [], {}, set()
    total = 0
    selected_fee = None
    for raw, index in previous_outputs:
        transaction = Transaction.deserialize(_hex(raw))
        if type(index) is not int or not 0 <= index < len(transaction.outputs):
            raise ValueError('Previous output index is invalid')
        outpoint = (transaction.txid(), index)
        if outpoint in seen:
            raise ValueError('Duplicate previous output')
        seen.add(outpoint)
        _p2wpkh(transaction.outputs[index].script_pubkey)
        total = checked_amount_sum((total, transaction.outputs[index].value))
        inputs.append(TxInput(*outpoint))
        # Witnesses are unnecessary for a previous transaction's txid commitment.
        previous[hash_to_display(transaction.txid())] = transaction.serialize(False).hex()
        probe = Transaction(2, tuple(inputs), tuple(targets + [TxOutput(0, change)]))
        selected_fee = fee_units if fee_units is not None else units(fee_rate * estimated_vsize(probe))
    remainder = total - payment_total - selected_fee
    if remainder < 0:
        raise ValueError('Insufficient available funds after the fee')
    outputs = targets + ([TxOutput(remainder, change)] if remainder else [])
    unsigned = Transaction(2, tuple(inputs), tuple(outputs))
    body = {'format': FORMAT, 'network': profile.name,
            'genesis_hash': hash_to_display(profile.genesis.block_hash()),
            'unsigned_tx': unsigned.serialize().hex(), 'previous_transactions': previous}
    package = dict(body, request_id=_identifier(body), signatures=[])
    inspect_package(package, profile)
    return package


def _validate(package, network):
    profile = get_network(network)
    if not isinstance(package, dict) or set(package) != BODY_FIELDS | {'request_id', 'signatures'}:
        raise ValueError('Invalid signing package fields')
    if len(_canonical(package)) > MAX_PACKAGE_BYTES:
        raise ValueError('Signing package is too large')
    body = {key: package[key] for key in BODY_FIELDS}
    if (body['format'] != FORMAT or body['network'] != profile.name
            or body['genesis_hash'] != hash_to_display(profile.genesis.block_hash())):
        raise ValueError('Signing package format or network/genesis mismatch')
    if package['request_id'] != _identifier(body):
        raise ValueError('Signing request ID does not match its contents')
    tx = Transaction.deserialize(_hex(body['unsigned_tx']))
    if (tx.version != 2 or tx.lock_time != 0 or not 1 <= len(tx.inputs) <= MAX_INPUTS
            or not 1 <= len(tx.outputs) <= 1001 or tx.is_coinbase()
            or any(i.script_sig or i.witness or i.sequence != 0xFFFFFFFF for i in tx.inputs)):
        raise ValueError('Unsupported unsigned transaction structure')
    if len({i.outpoint() for i in tx.inputs}) != len(tx.inputs):
        raise ValueError('Duplicate transaction input')
    for output in tx.outputs:
        units(output.value, positive=True)
        _p2wpkh(output.script_pubkey)
    records = body['previous_transactions']
    if not isinstance(records, dict) or set(records) != {hash_to_display(i.prev_txid) for i in tx.inputs}:
        raise ValueError('Previous transactions must match all inputs exactly')
    decoded = {}
    for txid, raw in records.items():
        previous = Transaction.deserialize(_hex(raw))
        if hash_to_display(previous.txid()) != txid:
            raise ValueError('Previous transaction does not match its referenced transaction ID')
        decoded[txid] = previous
    coins = []
    for item in tx.inputs:
        previous = decoded[hash_to_display(item.prev_txid)]
        if item.prev_index >= len(previous.outputs):
            raise ValueError('Referenced previous output does not exist')
        coin = previous.outputs[item.prev_index]
        _p2wpkh(coin.script_pubkey)
        coins.append(coin)
    fee = checked_amount_sum(c.value for c in coins) - checked_amount_sum(o.value for o in tx.outputs)
    units(fee)
    signatures = package['signatures']
    if not isinstance(signatures, list) or len(signatures) > len(tx.inputs):
        raise ValueError('Invalid signature list')
    signed_inputs, signed = list(tx.inputs), set()
    for entry in signatures:
        if not isinstance(entry, dict) or set(entry) != {'input_index', 'public_key', 'signature_der'}:
            raise ValueError('Invalid signature entry')
        index = entry['input_index']
        if type(index) is not int or not 0 <= index < len(tx.inputs) or index in signed:
            raise ValueError('Invalid or duplicate signature input index')
        public = _hex(entry['public_key'], 33)
        if len(public) != 33 or public[0] not in (2, 3):
            raise ValueError('A compressed secp256k1 public key is required')
        witness = (_hex(entry['signature_der'], 72) + b'\x01', public)
        signed_inputs[index] = replace(tx.inputs[index], witness=witness)
        signed.add(index)
    completed = replace(tx, inputs=tuple(signed_inputs))
    for index in signed:
        if not verify_p2wpkh(completed, index, coins[index]):
            raise ValueError('External signature does not authorize this transaction')
    return profile, tx, coins, fee, completed, signed


def inspect_package(package, network):
    profile, tx, coins, fee, completed, signed = _validate(package, network)
    return {'format': FORMAT, 'network': profile.name, 'genesis_hash': package['genesis_hash'],
            'request_id': package['request_id'], 'txid': hash_to_display(tx.txid()),
            'fee_units': fee, 'fee_smw': format_amount(fee),
            'estimated_vsize': estimated_vsize(tx),
            'complete': len(signed) == len(tx.inputs),
            'inputs': [{'input_index': n, 'txid': hash_to_display(i.prev_txid), 'index': i.prev_index,
                        'address': encode_address(c.script_pubkey, network=profile), 'value_units': c.value,
                        'signed': n in signed,
                        'digest_hex': bip143_sighash_all(tx, n, c.script_pubkey, c.value).hex()}
                       for n, (i, c) in enumerate(zip(tx.inputs, coins))],
            'outputs': [{'index': n, 'address': encode_address(o.script_pubkey, network=profile),
                         'value_units': o.value, 'value_smw': format_amount(o.value)}
                        for n, o in enumerate(tx.outputs)]}


def attach_signatures(package, network, signatures):
    """Verify supplied signatures; authorization policy belongs to the caller."""
    inspect_package(package, network)
    if not isinstance(signatures, list) or not signatures:
        raise ValueError('At least one external signature is required')
    updated = dict(package, signatures=package['signatures'] + signatures)
    inspect_package(updated, network)
    return updated


def finalize_package(package, network):
    _, tx, _, _, completed, signed = _validate(package, network)
    if len(signed) != len(tx.inputs):
        raise ValueError('Every input must be signed before finalization')
    return completed

