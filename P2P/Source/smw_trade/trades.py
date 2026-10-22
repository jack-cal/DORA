"""Local order-bound executions. Peer notices never assert chain settlement."""
import json
from .orders import DOMAIN, authenticate, canonical, order_id, valid_hex, amount
PHASES = {'STARTING', 'AGREED', 'SMW_LOCK_CONFIRMED', 'BOTH_LOCKS_CONFIRMED', 'BTC_CLAIM_CONFIRMED', 'REFUND_WAIT', 'FINALIZING', 'COMPLETED', 'REFUNDED', 'FAILED', 'INTERRUPTED'}
TERMINAL = {'COMPLETED', 'REFUNDED', 'FAILED', 'INTERRUPTED'}

class TradeBook:

    def __init__(self, store):
        self.store = store
        with store.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS executions (\n                session TEXT PRIMARY KEY, mode TEXT NOT NULL, state TEXT NOT NULL,\n                evidence TEXT NOT NULL)')

    def _terms(self, c, request, confirmation):
        r = authenticate(request)
        b = authenticate(confirmation)
        if set(r) != {'domain', 'kind', 'maker', 'order_id', 'nonce', 'expires_at'} or r['kind'] != 'accept' or (not valid_hex(r['order_id'], 32)) or (not valid_hex(r['nonce'], 16)) or (type(r['expires_at']) is not int):
            raise ValueError('Invalid signed acceptance')
        session = order_id(r)
        if set(b) != {'domain', 'kind', 'maker', 'order_id', 'session'} or b['kind'] != 'reserve' or b['order_id'] != r['order_id'] or (b['session'] != session):
            raise ValueError('Reservation does not bind this acceptance')
        row = c.execute('SELECT packet FROM orders WHERE id=?', (r['order_id'],)).fetchone()
        if not row:
            raise ValueError('Unknown source order')
        order = self.store._validate_order(json.loads(row[0]), require_live=False)
        if b['maker'] != order['maker'] or r['maker'] == order['maker']:
            raise ValueError('Wrong order participants')
        if self.store.identity.public not in (r['maker'], order['maker']):
            raise ValueError('Not a party to this reservation')
        return {'session': session, 'order_id': r['order_id'], 'order_side': order['side'], 'maker': order['maker'], 'taker': r['maker'], 'smw_atoms': order['smw_atoms'], 'btc_sats': order['btc_sats'], 'network': 'regtest-only'}

    def remember(self, request, confirmation):
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            terms = self._terms(c, request, confirmation)
            old = c.execute('SELECT request,maker_confirmation FROM agreements WHERE order_id=?', (terms['order_id'],)).fetchone()
            if old:
                if json.loads(old[0]) != request or json.loads(old[1]) != confirmation:
                    raise ValueError('Conflicting reservation')
            else:
                c.execute('INSERT INTO agreements VALUES (?,?,?,?)', (terms['session'], terms['order_id'], canonical(request).decode(), canonical(confirmation).decode()))
            c.execute('COMMIT')
        return terms

    def terms(self, session):
        if not valid_hex(session, 32):
            raise ValueError('Invalid reservation ID')
        with self.store.connect() as c:
            row = c.execute('SELECT request,maker_confirmation FROM agreements WHERE id=?', (session,)).fetchone()
            if not row:
                raise ValueError('Reserve the peer order first.')
            return self._terms(c, json.loads(row[0]), json.loads(row[1]))

    def listing(self):
        with self.store.connect() as c:
            rows = c.execute('SELECT a.id,a.request,a.maker_confirmation,e.mode,e.state,e.evidence\n                FROM agreements a LEFT JOIN executions e ON e.session=a.id ORDER BY a.rowid DESC').fetchall()
            result = []
            for row in rows:
                terms = self._terms(c, json.loads(row['request']), json.loads(row['maker_confirmation']))
                taker = terms['taker'] == self.store.identity.public
                selling = terms['order_side'] == 'buy' if taker else terms['order_side'] == 'sell'
                result.append({**terms, 'role': 'taker' if taker else 'maker', 'direction': 'sell' if selling else 'buy', 'smw': amount(terms['smw_atoms']), 'btc': amount(terms['btc_sats']), 'mode': row['mode'], 'state': row['state'] or 'RESERVED', 'evidence': json.loads(row['evidence']) if row['evidence'] else {}, 'can_execute': taker and row['state'] is None})
            return result

    def start(self, session, mode):
        if mode not in ('success', 'refund'):
            raise ValueError('Invalid test mode')
        terms = self.terms(session)
        if terms['taker'] != self.store.identity.public:
            raise ValueError('Start this test execution on the device that reserved the order.')
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM executions WHERE session=?', (session,)).fetchone():
                raise ValueError('This reservation was already executed. Review the saved trade history.')
            c.execute('INSERT INTO executions VALUES (?,?,?,?)', (session, mode, 'STARTING', canonical(terms).decode()))
            c.execute('COMMIT')
        return terms

    def update(self, session, state, evidence):
        if state not in PHASES:
            raise ValueError('Invalid execution state')
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT state,evidence FROM executions WHERE session=?', (session,)).fetchone()
            if not old or old['state'] in TERMINAL:
                raise ValueError('Execution is not active')
            terms = self.terms(session)
            for field in ('session', 'order_id', 'smw_atoms', 'btc_sats'):
                if field in evidence and evidence[field] != terms[field]:
                    raise ValueError('Changed signed trade terms')
            full = {**terms, **evidence, 'mode': c.execute('SELECT mode FROM executions WHERE session=?', (session,)).fetchone()[0]}
            c.execute('UPDATE executions SET state=?,evidence=? WHERE session=?', (state, canonical(full).decode(), session))
            c.execute('COMMIT')

    def mark_interrupted(self):
        with self.store.connect() as c:
            rows = c.execute("SELECT session,state,evidence FROM executions WHERE state NOT IN ('COMPLETED','REFUNDED','FAILED','INTERRUPTED')").fetchall()
            for row in rows:
                evidence = json.loads(row['evidence'])
                evidence['last_phase'] = row['state']
                evidence['error'] = 'The previous execution was interrupted. Records were retained; assets are not automatically sent again.'
                c.execute('UPDATE executions SET state=?,evidence=? WHERE session=?', ('INTERRUPTED', canonical(evidence).decode(), row['session']))
