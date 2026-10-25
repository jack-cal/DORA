"""Local transaction admission policy; never used to validate a block.

Rates are integer SMW base units per 1,000 virtual bytes. Public defaults are
one base unit per virtual byte. The isolated regtest default permits zero fees.
All replacement checks complete before the caller changes the pool.
"""
from dataclasses import dataclass
from hashlib import sha256
import json

MAX_REPLACEMENT_EFFECT_BYTES = 4_000_000

from .errors import InvalidTransaction


class MempoolPolicyError(InvalidTransaction):
    """A local policy refusal, not evidence of an invalid block."""


def vsize(transaction):
    return (transaction.weight() + 3) // 4


@dataclass(frozen=True)
class MempoolPolicy:
    minimum_rate: int = 1000
    incremental_rate: int = 1000
    max_replacements: int = 100

    def __post_init__(self):
        if (type(self.minimum_rate) is not int or not 0 <= self.minimum_rate <= 100_000_000
                or type(self.incremental_rate) is not int or not 1 <= self.incremental_rate <= 100_000_000
                or type(self.max_replacements) is not int or not 1 <= self.max_replacements <= 100):
            raise ValueError('Invalid local mempool policy')

    def required_fee(self, size):
        return (self.minimum_rate * size + 999) // 1000

    def check_fee(self, transaction, fee):
        if fee < self.required_fee(vsize(transaction)):
            raise MempoolPolicyError('Fee is below the local relay minimum')

    def info(self):
        return {'minimum_fee_units_per_kvb': self.minimum_rate,
                'incremental_fee_units_per_kvb': self.incremental_rate,
                'full_rbf': True, 'max_replacements': self.max_replacements,
                'consensus_fee_minimum_units': 0}


def replacement(chain, transaction, entries):
    """Return a validated replacement overlay and the removed transactions.

The write lock and capacity check belong to Chain. Removal includes every
descendant, whose fee must also be paid. New unconfirmed inputs are disallowed
unless that exact outpoint was already used by a direct conflict.
"""
    inputs = {item.outpoint() for item in transaction.inputs}
    direct = {tx.txid() for tx in entries if inputs.intersection(i.outpoint() for i in tx.inputs)}
    if not direct:
        return None
    removed = set(direct)
    while True:
        following = {tx.txid() for tx in entries if any(i.prev_txid in removed for i in tx.inputs)}
        if following.issubset(removed):
            break
        removed.update(following)
    if len(removed) > chain.mempool_policy.max_replacements:
        raise MempoolPolicyError('Replacement removes too many pending transactions')
    pool_ids = {tx.txid() for tx in entries}
    old_inputs = {i.outpoint() for tx in entries if tx.txid() in direct for i in tx.inputs}
    if any(i.prev_txid in pool_ids and i.outpoint() not in old_inputs for i in transaction.inputs):
        raise MempoolPolicyError('Replacement adds an unconfirmed input')

    original, path = chain._state_for(chain.tip_hash)
    # Validate every original against the same snapshot to recover its exact
    # fee. This also detects stale or externally corrupted local pool entries.
    old_state = original.copy()
    fees = {}
    effects = {}
    for tx in entries:
        if tx.txid() in removed:
            # Public-script net amounts only; no keys, wallet files or signatures.
            amounts = {}
            for output in tx.outputs:
                key = sha256(output.script_pubkey).hexdigest()
                amounts[key] = amounts.get(key, 0) + output.value
            for item in tx.inputs:
                coin = old_state.get((item.prev_txid, item.prev_index))
                if coin is None: raise InvalidTransaction('Missing or already spent input')
                output = coin.output
                key = sha256(output.script_pubkey).hexdigest()
                amounts[key] = amounts.get(key, 0) - output.value
            effects[tx.txid()] = json.dumps(amounts, separators=(',', ':')).encode()
        fees[tx.txid()] = chain._apply_transaction(tx, old_state, len(path), path)
    state = original.copy()
    kept = [tx for tx in entries if tx.txid() not in removed]
    for tx in kept:
        chain._apply_transaction(tx, state, len(path), path)
    fee = chain._apply_transaction(transaction, state, len(path), path)
    chain.mempool_policy.check_fee(transaction, fee)
    size = vsize(transaction)
    old_fee = sum(fees[digest] for digest in removed)
    increment = (chain.mempool_policy.incremental_rate * size + 999) // 1000
    if fee < old_fee + increment:
        raise MempoolPolicyError('Replacement fee does not pay for removed transactions and relay cost')
    if any(fee * vsize(tx) <= fees[tx.txid()] * size for tx in entries if tx.txid() in direct):
        raise MempoolPolicyError('Replacement fee rate must exceed each direct conflict')
    return state, path, kept, removed, fee, effects
