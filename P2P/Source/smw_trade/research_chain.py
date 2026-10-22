"""Regtest-only SUMUWW conditional-spend extension. Public profiles fail closed."""
from sumuww.chain import Chain, Coin, _sum
from sumuww.errors import InvalidTransaction, StorageError
from sumuww.primitives import coinbase_is_mature
from .htlc import verify_spend

class SwapChain(Chain):
    def __init__(self, database, *, network='regtest', **kwargs):
        if network != 'regtest':
            raise ValueError('HTLC research extension is restricted to regtest')
        super().__init__(database, network=network, **kwargs)
        self.connection.execute('CREATE TABLE IF NOT EXISTS exchange_research_policy (policy TEXT PRIMARY KEY)')
        self.connection.execute("INSERT OR IGNORE INTO exchange_research_policy VALUES ('exact-p2wsh-htlc-v1')")

    def _apply_transaction(self, transaction, state, height, path):
        # Preserve core input/fee/maturity/finality/relative-lock validation.
        # Only dispatch of spending authorization differs from the source snapshot.
        self._basic_transaction(transaction)
        if transaction.is_coinbase(): raise InvalidTransaction('Coinbase is not a normal transaction')
        self._check_finality(transaction, height, path)
        parent_mtp = self._mtp(path)
        coins = []
        for item in transaction.inputs:
            coin = state.get((item.prev_txid, item.prev_index))
            if coin is None: raise InvalidTransaction('Missing or already spent input')
            if coin.coinbase and not coinbase_is_mature(coin.height, height):
                raise InvalidTransaction('Immature coinbase input')
            if transaction.version >= 2 and not item.sequence & (1 << 31):
                relative = item.sequence & 0xFFFF
                if item.sequence & (1 << 22):
                    coin_mtp = self._mtp(path[:max(coin.height - 1, 0) + 1])
                    if parent_mtp < coin_mtp + (relative << 9): raise InvalidTransaction('Relative time lock not satisfied')
                elif height < coin.height + relative: raise InvalidTransaction('Relative height lock not satisfied')
            coins.append(coin)
        fee = _sum(c.output.value for c in coins) - _sum(o.value for o in transaction.outputs)
        if fee < 0: raise InvalidTransaction('Transaction creates value')
        for index, coin in enumerate(coins):
            if not verify_spend(transaction, index, coin.output): raise InvalidTransaction('Invalid spending authorization')
        txid = transaction.txid()
        if self._has_live_outputs(state, txid): raise InvalidTransaction('Live outputs would be overwritten')
        for item in transaction.inputs: del state[(item.prev_txid, item.prev_index)]
        for index, output in enumerate(transaction.outputs):
            if not (output.script_pubkey.startswith(b'\x6a') or len(output.script_pubkey) > 10_000):
                state[(txid, index)] = Coin(output, height, False)
        return fee
