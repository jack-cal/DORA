"""Two independent parties, local keys, observed chain state, durable refunds.

Public-chain spending is deliberately unavailable until SUMUWW supports HTLC.
Every fund/claim/refund operation is a local user command, never a peer command.
"""
import hashlib
import json
import threading
from coincurve import PublicKey
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import sign_p2wpkh
from .orders import DOMAIN, authenticate, canonical, valid_hex
from .trades import TradeBook
from .htlc import Contract, sign_spend, verify_spend
from .settlement import display
from .swap_backend import backends

class PeerSwap:

    def __init__(self, store, vault, config):
        self.store, self.vault, self.nodes = (store, vault, backends(config))
        self.lock = threading.RLock()
        with store.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS peer_swaps (session TEXT PRIMARY KEY, state TEXT NOT NULL)')

    def _get(self, session):
        terms = TradeBook(self.store).terms(session)
        with self.store.connect() as conn:
            row = conn.execute('SELECT state FROM peer_swaps WHERE session=?', (session,)).fetchone()
        if not row:
            raise ValueError('Prepare swap keys on both sides first.')
        return (terms, json.loads(row[0]))

    def _save(self, session, state):
        with self.store.connect() as conn:
            conn.execute('INSERT INTO peer_swaps VALUES (?,?) ON CONFLICT(session) DO UPDATE SET state=excluded.state', (session, canonical(state).decode()))

    def _seller(self, terms):
        return terms['maker'] if terms['order_side'] == 'sell' else terms['taker']

    def _selling(self, terms):
        return self.store.identity.public == self._seller(terms)

    def _secret(self, session, keys):
        return hashlib.sha256(keys['smw'].sign_digest(hashlib.sha256(b'SUMUWW swap secret v1\x00' + bytes.fromhex(session)).digest())).digest()

    def prepare(self, session):
        with self.lock:
            terms = TradeBook(self.store).terms(session)
            with self.store.connect() as conn:
                if conn.execute('SELECT 1 FROM executions WHERE session=?', (session,)).fetchone():
                    raise ValueError('This reservation was already used for a disposable check.')
                if conn.execute('SELECT 1 FROM peer_swaps WHERE session=?', (session,)).fetchone():
                    return self.snapshot(session)
            keys = self.vault.keys()
            infos = {coin: node.info() for coin, node in self.nodes.items()}
            if terms['btc_sats'] < 294:
                raise ValueError('Bitcoin regtest dust policy: receive amount must be at least 294 sat')
            offer = {'genesis': {c: v['genesis'] for c, v in infos.items()}, 'pubkeys': {c: k.pubkey.hex() for c, k in keys.items()}, 'secret_hash': None, 'refund_heights': None}
            if self._selling(terms):
                offer['secret_hash'] = hashlib.sha256(self._secret(session, keys)).hexdigest()
                offer['refund_heights'] = {'smw': infos['smw']['height'] + 40, 'btc': infos['btc']['height'] + 15}
            digest = self._proof_digest(session, self.store.identity.public, offer)
            offer['proofs'] = {c: k.sign_digest(digest).hex() for c, k in keys.items()}
            self._save(session, {'offer': offer, 'remote': None, 'funding_raw': None, 'refund_raw': None, 'claim_raw': None, 'refund_sent': False})
            return self.snapshot(session)

    @staticmethod
    def _proof_digest(session, identity, offer):
        return hashlib.sha256(b'SUMUWW swap key proof v1\x00' + bytes.fromhex(session) + bytes.fromhex(identity) + canonical({k: v for k, v in offer.items() if k != 'proofs'})).digest()

    def snapshot(self, session):
        terms, state = self._get(session)

        def txid(raw):
            return display(Transaction.deserialize(bytes.fromhex(raw))) if raw else None
        return self.store.identity.sign({'domain': DOMAIN, 'kind': 'swap-state', 'maker': self.store.identity.public, 'session': session, 'terms_hash': hashlib.sha256(canonical(terms)).hexdigest(), 'offer': state['offer'], 'funding': txid(state['funding_raw']), 'claim': txid(state['claim_raw']), 'refund': txid(state['refund_raw']) if state['refund_sent'] else None})

    def receive(self, packet):
        with self.lock:
            b = authenticate(packet)
            if set(b) != {'domain', 'kind', 'maker', 'session', 'terms_hash', 'offer', 'funding', 'claim', 'refund'} or b['kind'] != 'swap-state':
                raise ValueError('Invalid swap envelope')
            terms, state = self._get(b['session'])
            other = terms['taker'] if terms['maker'] == self.store.identity.public else terms['maker']
            if b['maker'] != other or b['terms_hash'] != hashlib.sha256(canonical(terms)).hexdigest():
                raise ValueError('Wrong trade participant or terms')
            for field in ('funding', 'claim', 'refund'):
                if b[field] is not None and (not valid_hex(b[field], 32)):
                    raise ValueError('Invalid transaction reference')
            offer = b['offer']
            if set(offer) != {'genesis', 'pubkeys', 'secret_hash', 'refund_heights', 'proofs'}:
                raise ValueError('Invalid key offer')
            if offer['genesis'] != state['offer']['genesis']:
                raise ValueError('Different chain genesis')
            for field in ('pubkeys', 'proofs'):
                if set(offer[field]) != {'smw', 'btc'}:
                    raise ValueError('Invalid coin keys')
            digest = self._proof_digest(b['session'], other, offer)
            for coin in ('smw', 'btc'):
                pub = bytes.fromhex(offer['pubkeys'][coin])
                if len(pub) != 33 or PublicKey(pub).format() != pub or (not PublicKey(pub).verify(bytes.fromhex(offer['proofs'][coin]), digest, hasher=None)):
                    raise ValueError('Invalid proof of key possession')
                if pub.hex() == state['offer']['pubkeys'][coin]:
                    raise ValueError('Shared counterparty key refused')
            if other == self._seller(terms):
                if not valid_hex(offer['secret_hash'], 32) or set(offer['refund_heights']) != {'smw', 'btc'}:
                    raise ValueError('Invalid seller commitment')
                if not state['remote']:
                    for coin, maximum, minimum in (('smw', 40, 30), ('btc', 15, 10)):
                        deadline = offer['refund_heights'][coin]
                        if type(deadline) is not int or not minimum <= deadline - self.nodes[coin].info()['height'] <= maximum:
                            raise ValueError('Refund window expired or outside agreed regtest policy')
            elif offer['secret_hash'] is not None or offer['refund_heights'] is not None:
                raise ValueError('Buyer cannot choose the secret or refund policy')
            if state['remote']:
                old = state['remote']['body']
                if old['offer'] != offer:
                    raise ValueError('Cannot replace agreed keys/commitment')
                for field in ('funding', 'claim', 'refund'):
                    if old[field] is not None and b[field] != old[field]:
                        if b[field] is None:
                            b = {**b, field: old[field]}
                        else:
                            raise ValueError('Cannot replace published transaction reference')
            if state['remote'] and any((state['remote']['body'][f] and packet['body'][f] is None for f in ('funding', 'claim', 'refund'))):
                return self.snapshot(b['session'])
            state['remote'] = packet
            self._save(b['session'], state)
            return self.snapshot(b['session'])

    def _contracts(self, terms, state):
        if not state['remote']:
            raise ValueError('Receive the signed peer swap keys first.')
        local, remote = (state['offer'], state['remote']['body']['offer'])
        seller, buyer = (local, remote) if self._selling(terms) else (remote, local)
        return {'smw': Contract(bytes.fromhex(seller['secret_hash']), bytes.fromhex(buyer['pubkeys']['smw']), bytes.fromhex(seller['pubkeys']['smw']), seller['refund_heights']['smw']), 'btc': Contract(bytes.fromhex(seller['secret_hash']), bytes.fromhex(seller['pubkeys']['btc']), bytes.fromhex(buyer['pubkeys']['btc']), seller['refund_heights']['btc'])}

    def _funding(self, terms, state, coin, contracts):
        own = coin == ('smw' if self._selling(terms) else 'btc')
        raw = state['funding_raw'] if own else None
        txid = display(Transaction.deserialize(bytes.fromhex(raw))) if raw else state['remote']['body']['funding'] if not own else None
        if not txid:
            raise ValueError('Funding transaction not available')
        tx, confirmations = self.nodes[coin].transaction(txid)
        expected = terms['smw_atoms' if coin == 'smw' else 'btc_sats'] + 1000
        matches = [(i, o) for i, o in enumerate(tx.outputs) if o.script_pubkey == contracts[coin].script_pubkey and o.value == expected]
        if len(matches) != 1 or confirmations < 1:
            raise ValueError('Wrong or unconfirmed funding output')
        index, previous = matches[0]
        return (tx, index, previous)

    def _unspent(self, coin, funding, index, previous):
        current = self.nodes[coin].output(display(funding), index)
        if not current or current['confirmations'] < 1 or current['value'] != previous.value or (current['script'] != previous.script_pubkey.hex()):
            raise ValueError('Lock is unconfirmed, already spent or changed')

    def fund(self, session):
        with self.lock:
            terms, state = self._get(session)
            keys = self.vault.keys()
            contracts = self._contracts(terms, state)
            coin = 'smw' if self._selling(terms) else 'btc'
            node, contract, key = (self.nodes[coin], contracts[coin], keys[coin])
            for c, minimum in (('smw', 20), ('btc', 6)):
                if contracts[c].refund_height - self.nodes[c].info()['height'] < minimum:
                    raise ValueError('Refund window too short; no new funding allowed')
            if coin == 'btc':
                tx, index, previous = self._funding(terms, state, 'smw', contracts)
                self._unspent('smw', tx, index, previous)
            if not state['funding_raw']:
                with self.store.connect() as conn:
                    other = [json.loads(r[0]) for r in conn.execute('SELECT state FROM peer_swaps WHERE session<>?', (session,))]
                reserved = {(i.prev_txid, i.prev_index) for s in other if s['funding_raw'] for i in Transaction.deserialize(bytes.fromhex(s['funding_raw'])).inputs}
                value = terms['smw_atoms' if coin == 'smw' else 'btc_sats'] + 1000
                selected = []
                total = 0
                for output in node.coins(key.script_pubkey):
                    point = (bytes.fromhex(output['txid'])[::-1], output['vout'])
                    if point in reserved:
                        continue
                    if output['script'] != key.script_pubkey.hex():
                        raise ValueError('Input ownership mismatch')
                    selected.append((point, TxOutput(output['value'], key.script_pubkey)))
                    total += output['value']
                    if total >= value + 1000:
                        break
                if total < value + 1000:
                    raise ValueError('Insufficient confirmed local funds including fees')
                outputs = [TxOutput(value, contract.script_pubkey)]
                if total > value + 1000:
                    outputs.append(TxOutput(total - value - 1000, key.script_pubkey))
                funding = Transaction(2, tuple((TxInput(*point) for point, _ in selected)), tuple(outputs), 0)
                for i, (_, previous) in enumerate(selected):
                    funding = sign_p2wpkh(funding, i, previous, key)
                refund = Transaction(2, (TxInput(funding.txid(), 0, sequence=4294967294),), (TxOutput(value - 1000, key.script_pubkey),), contract.refund_height)
                refund = sign_spend(refund, 0, funding.outputs[0], contract, key)
                state['funding_raw'] = funding.serialize().hex()
                state['refund_raw'] = refund.serialize().hex()
                self._save(session, state)
            funding = Transaction.deserialize(bytes.fromhex(state['funding_raw']))
            node.broadcast(funding)
            return self.status(session)

    def claim(self, session):
        with self.lock:
            terms, state = self._get(session)
            keys = self.vault.keys()
            contracts = self._contracts(terms, state)
            coin = 'btc' if self._selling(terms) else 'smw'
            node = self.nodes[coin]
            if state['refund_sent']:
                raise ValueError('Local funding refund was already submitted')
            if not state['claim_raw']:
                funding, index, previous = self._funding(terms, state, coin, contracts)
                self._unspent(coin, funding, index, previous)
                if coin == 'btc':
                    own, oi, op = self._funding(terms, state, 'smw', contracts)
                    self._unspent('smw', own, oi, op)
                    if contracts['btc'].refund_height - node.info()['height'] < 3:
                        raise ValueError('BTC refund window too close')
                    secret = self._secret(session, keys)
                else:
                    btc, bi, bp = self._funding(terms, state, 'btc', contracts)
                    claim_id = self.nodes['btc'].find_spend(display(btc), bi, 0)
                    if not claim_id:
                        raise ValueError('No confirmed Bitcoin claim revealing the secret yet')
                    claim, confirmations = self.nodes['btc'].transaction(claim_id)
                    matches = [i for i, item in enumerate(claim.inputs) if item.prev_txid == btc.txid() and item.prev_index == bi]
                    if confirmations < 1 or len(matches) != 1 or (not verify_spend(claim, matches[0], bp)):
                        raise ValueError('Invalid observed Bitcoin spend')
                    witness = claim.inputs[matches[0]].witness
                    if len(witness) != 4:
                        raise ValueError('Bitcoin output was refunded, not claimed')
                    secret = witness[1]
                if hashlib.sha256(secret).digest() != contracts[coin].secret_hash:
                    raise ValueError('Wrong observed secret')
                claim = Transaction(2, (TxInput(funding.txid(), index, sequence=4294967294),), (TxOutput(previous.value - 1000, keys[coin].script_pubkey),), 0)
                claim = sign_spend(claim, 0, previous, contracts[coin], keys[coin], secret=secret)
                state['claim_raw'] = claim.serialize().hex()
                self._save(session, state)
            node.broadcast(Transaction.deserialize(bytes.fromhex(state['claim_raw'])))
            return self.status(session)

    def refund(self, session):
        with self.lock:
            terms, state = self._get(session)
            coin = 'smw' if self._selling(terms) else 'btc'
            if not state['refund_raw']:
                raise ValueError('No local funding/refund plan')
            refund = Transaction.deserialize(bytes.fromhex(state['refund_raw']))
            if self.nodes[coin].info()['height'] < refund.lock_time:
                raise ValueError('Refund height has not arrived')
            self.nodes[coin].broadcast(refund)
            state['refund_sent'] = True
            self._save(session, state)
            return self.status(session)

    def status(self, session):
        with self.lock:
            terms, state = self._get(session)
            result = {'session': session, 'network': 'regtest-only', 'independent_parties': True, 'public_funds': False, 'prepared': True, 'peer_ready': bool(state['remote']), 'funding_saved': bool(state['funding_raw']), 'refund_saved': bool(state['refund_raw']), 'received_confirmed': False, 'refund_confirmed': False}
            own = 'smw' if self._selling(terms) else 'btc'
            receive = 'btc' if own == 'smw' else 'smw'
            for field, coin, flag in (('claim_raw', receive, 'received_confirmed'), ('refund_raw', own, 'refund_confirmed')):
                raw = state[field]
                if not raw or (field == 'refund_raw' and (not state['refund_sent'])):
                    continue
                expected = Transaction.deserialize(bytes.fromhex(raw))
                try:
                    actual, count = self.nodes[coin].transaction(display(expected))
                    result[flag] = actual.serialize() == expected.serialize() and count >= 1
                except ValueError:
                    pass
            return result

    def listing(self):
        with self.store.connect() as conn:
            sessions = [r[0] for r in conn.execute('SELECT session FROM peer_swaps')]
        return [self._local_status(session) for session in sessions]

    def _local_status(self, session):
        terms, state = self._get(session)
        return {'session': session, 'direction': 'sell' if self._selling(terms) else 'buy', 'peer_ready': bool(state['remote']), 'funding_saved': bool(state['funding_raw']), 'claim_saved': bool(state['claim_raw']), 'refund_saved': bool(state['refund_raw']), 'refund_sent': state['refund_sent']}
