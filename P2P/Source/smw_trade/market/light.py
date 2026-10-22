"""Bitcoin SPV settlement using replaceable Electrum servers and local keys.

Header PoW/difficulty and transaction inclusion are verified locally. History
completeness/unspentness still require honest available servers; this is not a
full Bitcoin validator. All supplied amounts/scripts are parsed from raw txs.
"""
import hashlib
from pathlib import Path
from sumuww.transaction import Transaction
from .utxo import UtxoAdapter, BTC_GENESIS, txid
from .light_headers import GENESIS, sha256d
from .light_network import LightNetwork, DEFAULT_SERVERS


class BitcoinLightAdapter(UtxoAdapter):
    def __init__(self, config, directory, network='mainnet', progress=None):
        self.coin = 'BTC'
        self.config = config
        self.network = network
        self.confirmations = int(config.get('confirmations', 6 if network == 'mainnet' else 1))
        if self.confirmations < 1 or (network == 'mainnet' and self.confirmations < 6):
            raise ValueError('Insufficient confirmation policy.')
        self.fee = int(config.get('fee_units', 2000))
        if not 294 <= self.fee <= 1_000_000:
            raise ValueError('Invalid fee budget.')
        self.seconds = int(config.get('block_seconds', 600))
        if self.seconds < 1 or (network == 'mainnet' and self.seconds != 600):
            raise ValueError('Public timing profile is fixed at 600 seconds.')
        self.client = LightNetwork(Path(directory) / 'bitcoin-headers.bin', config.get('servers', DEFAULT_SERVERS), network, progress)
        self.heights = {}
        self.raw_cache = {}
        self.proofs = {}

    def close(self):
        self.client.close()

    def info(self):
        height = self.client.sync()
        genesis = sha256d(GENESIS[self.network])[::-1].hex()
        if self.network == 'mainnet' and genesis != BTC_GENESIS:
            raise ValueError('Wrong Bitcoin genesis.')
        return {'identity': 'BTC:' + genesis, 'height': height, 'clock': height,
                'kind': 'height', 'seconds': self.seconds, 'active': True, 'fee': self.fee,
                'confirmations': self.confirmations, 'verification': 'spv',
                'verified_servers': len(self.client.active), 'header_bytes': len(self.client.chain.data)}

    @staticmethod
    def script_hash(script):
        return hashlib.sha256(script).digest()[::-1].hex()

    def _history(self, script):
        def normalize(rows):
            if not isinstance(rows, list) or len(rows) > 20_000:
                raise ValueError('Bitcoin script history exceeds the supported limit.')
            result = []
            seen = set()
            for row in rows:
                digest, height = row['tx_hash'], row['height']
                if not isinstance(digest, str) or len(digest) != 64 or len(bytes.fromhex(digest)) != 32 or digest in seen:
                    raise ValueError('Invalid or repeated Bitcoin history transaction.')
                if type(height) is not int or not -1 <= height <= self.client.chain.height:
                    raise ValueError('Invalid Bitcoin history height.')
                seen.add(digest)
                result.append((digest, height))
            return sorted(result)
        rows = self.client.consistent('blockchain.scripthash.get_history', self.script_hash(script), normalize=normalize)
        # Replace old inclusion heights, including after reorganization or eviction.
        for digest, height in rows:
            self.heights[digest] = height
        return rows

    def _unspent(self, script):
        def normalize(rows):
            if not isinstance(rows, list) or len(rows) > 20_000:
                raise ValueError('Bitcoin output list exceeds the supported limit.')
            result, seen = [], set()
            for row in rows:
                digest, index, height, value = (row[k] for k in ('tx_hash', 'tx_pos', 'height', 'value'))
                if not isinstance(digest, str) or len(digest) != 64 or len(bytes.fromhex(digest)) != 32:
                    raise ValueError('Invalid Bitcoin output transaction ID.')
                if any(type(n) is not int for n in (index, height, value)) or not 0 <= index < 2**32 or not 0 <= height <= self.client.chain.height or not 0 <= value <= 21_000_000 * 10**8:
                    raise ValueError('Invalid Bitcoin output value, position or height.')
                if (digest, index) in seen:
                    raise ValueError('Repeated Bitcoin output.')
                seen.add((digest, index))
                result.append((digest, index, height, value))
            return sorted(result)
        return self.client.consistent('blockchain.scripthash.listunspent', self.script_hash(script), normalize=normalize)

    def _raw(self, digest):
        if not isinstance(digest, str) or len(digest) != 64 or len(bytes.fromhex(digest)) != 32:
            raise ValueError('Invalid Bitcoin transaction ID.')
        if digest not in self.raw_cache:
            def normalize(raw):
                if not isinstance(raw, str) or not 20 <= len(raw) <= 8_000_000:
                    raise ValueError('Invalid Bitcoin transaction length.')
                tx = Transaction.deserialize(bytes.fromhex(raw))
                if len(tx.serialize(include_witness=False)) == 64:
                    raise ValueError('Ambiguous 64-byte Bitcoin Merkle leaf refused.')
                if txid(tx) != digest:
                    raise ValueError('Bitcoin transaction hash mismatch.')
                return tx.serialize().hex()
            raw = self.client.consistent('blockchain.transaction.get', digest, False, normalize=normalize)
            if len(self.raw_cache) >= 4096:
                self.raw_cache.clear()
            self.raw_cache[digest] = Transaction.deserialize(bytes.fromhex(raw))
        return self.raw_cache[digest]

    def transaction(self, digest):
        self.client.sync()
        tx = self._raw(digest)
        height = self.heights.get(digest, 0)
        if height <= 0:
            return tx, 0
        block = self.client.chain.digest(height)
        if self.proofs.get(digest) != (height, block):
            results, errors = self.client.parallel(self.client.active, lambda p: p.call('blockchain.transaction.get_merkle', digest, height))
            verified = 0
            for peer, proof in results:
                try:
                    self.client.chain.verify_merkle(digest, height, proof)
                    verified += 1
                except (ValueError, KeyError, TypeError):
                    # A supplied invalid proof is a conflict, not confirmation.
                    raise ValueError('A Bitcoin server supplied an invalid inclusion proof.') from None
            if verified < 2:
                raise ValueError('Two Bitcoin inclusion proofs are required.')
            if len(self.proofs) >= 4096:
                self.proofs.clear()
            self.proofs[digest] = (height, block)
        return tx, self.client.chain.height - height + 1

    def _checked_output(self, digest, index, height, value, script):
        self.heights[digest] = height
        tx, count = self.transaction(digest)
        if index >= len(tx.outputs):
            raise ValueError('Bitcoin server reported a nonexistent output.')
        out = tx.outputs[index]
        if out.value != value or out.script_pubkey != script:
            raise ValueError('Bitcoin server changed the output amount or script.')
        coinbase = len(tx.inputs) == 1 and tx.inputs[0].prev_txid == bytes(32) and tx.inputs[0].prev_index == 0xffffffff
        return {'value': out.value, 'script': script.hex(), 'confirmations': count, 'coinbase': coinbase}

    def coins(self, key):
        result = []
        for digest, index, height, value in self._unspent(key.script_pubkey):
            out = self._checked_output(digest, index, height, value, key.script_pubkey)
            if out['confirmations'] >= self.confirmations and (not out['coinbase'] or out['confirmations'] >= 101):
                result.append({'txid': digest, 'index': index, **out})
        return result

    def output(self, digest, index):
        tx = self._raw(digest)
        if type(index) is not int or not 0 <= index < len(tx.outputs):
            raise ValueError('Invalid Bitcoin output index.')
        script = tx.outputs[index].script_pubkey
        for tx_hash, position, height, value in self._unspent(script):
            if (tx_hash, position) == (digest, index):
                return self._checked_output(digest, index, height, value, script)
        return None

    def find_reference(self, spec):
        script = self.contract(spec).script_pubkey
        matches = []
        for digest, height in self._history(script):
            if height > 0 and height < spec['scan_start']:
                continue
            tx, count = self.transaction(digest)
            for index, out in enumerate(tx.outputs):
                if out.script_pubkey == script and out.value == spec['amount'] + spec['fee']:
                    matches.append((height if height > 0 else 2**32, digest, index))
        if matches:
            _, digest, index = min(matches)
            return {'txid': digest, 'index': index}
        return None

    def _funding(self, spec, reference):
        rows = dict(self._history(self.contract(spec).script_pubkey))
        if reference['txid'] not in rows:
            raise ValueError('Funding is absent from the consistent Bitcoin script history.')
        return super()._funding(spec, reference)

    def _spend(self, spec, reference):
        matches = []
        for digest, height in self._history(self.contract(spec).script_pubkey):
            tx, count = self.transaction(digest)
            if any(i.prev_txid[::-1].hex() == reference['txid'] and i.prev_index == reference['index'] for i in tx.inputs):
                matches.append((height if height > 0 else 2**32, digest))
        return min(matches)[1] if matches else None

    def broadcast(self, operation):
        self.client.sync(force=True)
        tx = Transaction.deserialize(bytes.fromhex(operation['raw']))
        if txid(tx) != operation['txid']:
            raise ValueError('Changed signed Bitcoin transaction.')
        return self.client.broadcast(operation['raw'], operation['txid'])
