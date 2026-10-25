"""Public-script transaction history cache for the currently selected wallet."""

from .primitives import hash_to_display
from .rewards import read_reward
from hashlib import sha256
import json


class WalletHistory:
    def __init__(self, script):
        self.script = script
        self.tip = None
        self.outputs = {}
        self.entries = []
        self._replacement_token = None
        self._replacements = []

    def _apply(self, transaction, height, outputs):
        received = sum(output.value for output in transaction.outputs
                       if output.script_pubkey == self.script)
        spent = sum(outputs.pop((item.prev_txid, item.prev_index), 0)
                    for item in transaction.inputs)
        txid = transaction.txid()
        for index, output in enumerate(transaction.outputs):
            if output.script_pubkey == self.script:
                outputs[(txid, index)] = output.value
        if received or spent:
            return {'txid': hash_to_display(txid), 'height': height,
                    'coinbase': transaction.is_coinbase(), 'net_amount': received - spent,
                    'status': 'pending' if height is None else 'confirmed'}
        return None

    def _refresh(self, chain):
        """Refresh the selected script's entire active-chain public history.

        The caller owns a chain read snapshot. A changed branch that no longer
        contains our cached tip is rebuilt; confirmations are never cached.
        """
        tip = chain.tip_hash
        if tip != self.tip:
            pending_blocks = []
            row = chain._row(tip)
            while row[0] != self.tip and row[2] > 0:
                pending_blocks.append((row[2], chain.get_block(row[0])))
                row = chain._row(row[1])
            if row[0] != self.tip:
                self.outputs = {}
                self.entries = []
            for height, block in reversed(pending_blocks):
                for transaction in block.transactions:
                    entry = self._apply(transaction, height, self.outputs)
                    if entry:
                        if transaction.is_coinbase():
                            entry['mining_reward'] = read_reward(chain.connection, block, height)
                        self.entries.append(entry)
            self.tip = tip
        height = chain._row(tip)[2]
        outputs = self.outputs.copy()
        pending = []
        for transaction in chain.mempool_transactions():
            entry = self._apply(transaction, None, outputs)
            if entry:
                pending.append(entry)
        token = (*chain._path_cache_token(), tip)
        if self._replacement_token != token:
            key = sha256(self.script).hexdigest()
            records = []
            for old, new, reason, raw in chain.connection.execute("""SELECT r.old_txid,r.new_txid,r.reason,e.effects
                FROM mempool_replacements r JOIN mempool_replacement_effects e ON r.old_txid=e.old_txid
                ORDER BY r.seen,r.rowid"""):
                amounts = json.loads(raw)
                if key in amounts:
                    records.append({'txid': hash_to_display(old), 'height': None, 'coinbase': False,
                                    'net_amount': amounts[key], 'status': 'replaced', 'confirmations': 0,
                                    'replaced_by': hash_to_display(new), 'replacement_reason': reason})
            self._replacements = records
            self._replacement_token = token
        # Active-chain and current-pool facts override old local replacement records.
        active_ids = {entry['txid'] for entry in self.entries} | {entry['txid'] for entry in pending}
        removed = [entry for entry in self._replacements if entry['txid'] not in active_ids]
        return height, tip, removed + pending

    def _rows(self, pending, height, positions):
        result = []
        pending_count = len(pending)
        for position in positions:
            if position < pending_count:
                result.append(dict(pending[-1 - position], confirmations=0))
            else:
                entry = self.entries[-1 - (position - pending_count)]
                result.append(dict(entry, confirmations=height - entry['height'] + 1))
        return result

    def recent(self, chain, limit=10):
        """Return the existing recent-list view without pruning full history."""
        with chain.read_snapshot():
            height, _, pending = self._refresh(chain)
            return self._rows(pending, height, range(len(pending) + len(self.entries))[:limit])

    def page(self, chain, offset=0, limit=50):
        """Read a bounded page: pending, locally replaced, then confirmed newest first."""
        if type(offset) is not int or offset < 0:
            raise ValueError('History offset must be a non-negative integer')
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('History limit must be an integer from 1 to 200')
        with chain.read_snapshot():
            height, tip, pending = self._refresh(chain)
            total = len(pending) + len(self.entries)
            positions = range(offset, min(offset + limit, total))
            return {'transactions': self._rows(pending, height, positions),
                    'total': total, 'offset': offset, 'limit': limit,
                    'height': height, 'tip': hash_to_display(tip)}
