"""Local, durable allocations of confirmed wallet outputs to orders.

An allocation is not an on-chain escrow. Every reservation and funding spend
checks the chain again. Pending trade inputs and other orders remain excluded.
"""
import json
from ..orders import canonical
from .amounts import quote_total, show


class Funding:
    def __init__(self, engine):
        self.engine = engine
        self.board = engine.board
        with self.board.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS funding_holds (post TEXT PRIMARY KEY, coin TEXT NOT NULL, data TEXT NOT NULL)')

    def active(self):
        orders = {p['id']: p for p in self.board.listing()}
        sessions = {t['post']: t for t in self.board.sessions()}
        result = {}
        with self.board.connect() as db:
            rows = db.execute('SELECT post,coin,data FROM funding_holds').fetchall()
            states = {r[0]: json.loads(r[1]) for r in db.execute('SELECT id,state FROM swaps')}
        for oid, coin, raw in rows:
            order, terms = orders.get(oid), sessions.get(oid)
            if not order:
                continue
            state = states.get(terms['session']) if terms else None
            if state and self.engine.canceled(state) and not any(op['submitted'] for op in state['ops'].values()):
                continue
            if not terms and order['status'] != 'active':
                continue
            result[oid] = (coin, json.loads(raw))
        return result

    def reserved(self, coin, session=None, post=None):
        if session:
            post = self.board.terms(session)['post']
        return [(c['txid'], c['index']) for oid, (asset, data) in self.active().items()
                if asset == coin and oid != post for c in data['inputs']]

    def require_wallet(self):
        state = self.engine.vault.state()
        if not state['exists']:
            raise ValueError('Create a trading wallet and deposit funds first.')
        if state['locked']:
            raise ValueError('Unlock the trading wallet first.')

    def select(self, coin, amount, post=None):
        self.require_wallet()
        node = self.engine.nodes.get(coin)
        if node is None:
            raise ValueError('Configure the paying coin connection first.')
        if not node.info()['active']:
            raise ValueError('The paying chain is not ready.')
        reserved = set(self.engine.reserved_inputs(coin, include_holds=False))
        reserved.update(self.reserved(coin, post=post))
        key = self.engine.vault.key(coin)
        inputs, fee = node.select_funding(amount + node.fee, key, reserved)
        return {'amount': amount, 'fee': fee + node.fee, 'inputs': inputs}

    def save(self, post, coin, data):
        with self.board.connect() as db:
            db.execute('INSERT INTO funding_holds VALUES(?,?,?) ON CONFLICT(post) DO UPDATE SET coin=excluded.coin,data=excluded.data',
                       (post, coin, canonical(data).decode()))

    def check_post(self, post, *, maker):
        selling = (post['side'] == 'sell') == maker
        coin = 'SMW' if selling else 'BTC'
        amount = post['smw_units'] if selling else post['quote_units']
        data = self.select(coin, amount, post['id'])
        self.save(post['id'], coin, data)
        return data

    def balances(self):
        self.require_wallet()
        result = {}
        for coin in ('SMW', 'BTC'):
            node = self.engine.nodes.get(coin)
            if not node:
                result[coin] = None
                continue
            try:
                node.info()
                outputs = node.coins(self.engine.vault.key(coin))
                reserved = set(self.engine.reserved_inputs(coin))
                total = sum(c['value'] for c in outputs)
                free = sum(c['value'] for c in outputs if (c['txid'], c['index']) not in reserved)
                result[coin] = {'confirmed': show(total, coin), 'available': show(free, coin)}
            except (OSError, ValueError):
                result[coin] = None
        return result
