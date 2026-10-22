"""Local wallet fee suggestions; never a consensus minimum or speed promise.

Observe positive fees in the latest 20 active blocks and the local mempool.
The upper quartile is a simple suggestion, not Bitcoin Core's fee estimator.
All money/rate arithmetic is exact. Initial defaults and the automatic cap
are wallet policy; manually signed transactions keep their own chosen fees.
"""

from fractions import Fraction
from weakref import WeakKeyDictionary

from .primitives import MAX_MONEY, checked_amount_sum, coinbase_is_mature, require_int
from .transaction import Transaction, TxInput, TxOutput

INITIAL_FEE_UNITS = 100_000       # 0.001 SMW total, when observations are absent.
MAX_AUTO_FEE_UNITS = 1_000_000    # 0.01 SMW total, automatic wallet suggestions only.
HISTORY_BLOCKS = 20
MAX_HISTORY_SAMPLES = 1000
_history_cache = WeakKeyDictionary()


def virtual_size(transaction):
    return (transaction.weight() + 3) // 4


def _positive_rate(transaction, values):
    try:
        incoming = checked_amount_sum(values[(item.prev_txid, item.prev_index)] for item in transaction.inputs)
        outgoing = checked_amount_sum(output.value for output in transaction.outputs)
    except (KeyError, TypeError, ValueError):
        return None
    fee = incoming - outgoing
    return Fraction(fee, virtual_size(transaction)) if fee > 0 else None


def _confirmed_rates(chain):
    tip = chain.tip_hash
    cached = _history_cache.get(chain)
    if cached is not None and cached[0] == tip:
        return cached[1]
    path = chain._path(tip)
    recent = [tx for _, block in path[-HISTORY_BLOCKS:]
              for tx in block.transactions[1:]][-MAX_HISTORY_SAMPLES:]
    needed = {item.prev_txid for tx in recent for item in tx.inputs}
    values = {}
    # Keep only previous outputs needed by the bounded recent sample. Previous
    # outputs may be spent now, so current UTXOs alone cannot recover their fees.
    for _, block in path:
        for tx in block.transactions:
            if tx.txid() in needed:
                values.update({(tx.txid(), index): output.value
                               for index, output in enumerate(tx.outputs)})
    rates = tuple(rate for tx in recent if (rate := _positive_rate(tx, values)) is not None)
    _history_cache[chain] = (tip, rates)
    return rates


def _pending_rates(chain):
    values = {outpoint: coin.output.value for outpoint, coin in chain._load_utxos().items()}
    rates = []
    # Pool admission stores parents before children. This includes package
    # outputs without treating pending wallet receipts as spendable funds.
    for tx in chain.mempool_transactions():
        rate = _positive_rate(tx, values)
        if rate is not None:
            rates.append(rate)
        values.update({(tx.txid(), index): output.value for index, output in enumerate(tx.outputs)})
    return tuple(rates)


def _suggestion(chain):
    history = _confirmed_rates(chain)
    pending = _pending_rates(chain)
    rates = sorted(history + pending)
    if not rates:
        return None, 'initial_default', 0
    # Nearest-rank 75th percentile, at least one smallest unit per virtual byte.
    rate = max(Fraction(1), rates[(3 * len(rates) + 3) // 4 - 1])
    return rate, 'local_mempool' if pending else 'local_history', len(rates)


def estimate_payment_fee(chain, wallet_script, recipient_script, amount_units):
    """Suggest the total fee using a conservative supported-payment size.

    The caller should keep an outer read snapshot around estimation and signing
    when preparing an exact payment quote. This function also works standalone.
    Signatures are bounded at 73 bytes and the change output is always budgeted,
    so shorter DER signatures or exact-change payments never exceed the size.
    """
    require_int(amount_units, 1, MAX_MONEY)
    if not isinstance(wallet_script, bytes) or not isinstance(recipient_script, bytes):
        raise TypeError('Payment scripts must be bytes')
    with chain.read_snapshot():
        rate, source, samples = _suggestion(chain)
        pending = {item.outpoint() for tx in chain.mempool_transactions() for item in tx.inputs}
        spend_height = chain.info()['height'] + 1
        coins = [(outpoint, coin) for outpoint, coin in chain.list_utxos(wallet_script)
                 if (not coin.coinbase or coinbase_is_mature(coin.height, spend_height))
                 and TxInput(*outpoint).outpoint() not in pending]
        selected = []
        total = 0
        fee = INITIAL_FEE_UNITS if rate is None else 1
        index = 0
        capped = False
        while True:
            required = checked_amount_sum((amount_units, fee))
            while total < required and index < len(coins):
                outpoint, coin = coins[index]
                selected.append(TxInput(*outpoint, witness=(bytes(73), bytes(33))))
                total = checked_amount_sum((total, coin.output.value))
                index += 1
            if total < required:
                raise ValueError('Insufficient mature confirmed funds after pending spends')
            payment = Transaction(2, tuple(selected), (TxOutput(amount_units, recipient_script), TxOutput(0, wallet_script)))
            size = virtual_size(payment)
            suggested = INITIAL_FEE_UNITS if rate is None else (rate.numerator * size + rate.denominator - 1) // rate.denominator
            capped = suggested > MAX_AUTO_FEE_UNITS
            suggested = min(MAX_AUTO_FEE_UNITS, max(1, suggested))
            if suggested <= fee:
                return {'fee_units': fee, 'estimated_vsize': size, 'source': source,
                        'capped': capped, 'sample_count': samples,
                        'auto_fee_cap_units': MAX_AUTO_FEE_UNITS}
            fee = suggested
