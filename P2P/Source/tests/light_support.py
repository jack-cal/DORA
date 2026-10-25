"""Three noncustodial Electrum-protocol fixtures backed by real Core regtest.

These are test servers, not an independent production Electrum implementation.
"""
import copy
import hashlib
import json
import socketserver
import threading
from sumuww.transaction import Transaction
from smw_trade.market.light_headers import sha256d


class Index:
    def __init__(self, btc):
        self.btc = btc
        self.lock = threading.RLock()
        self.tip = None
        self.block_cache = {}
        self.blocks = []
        self.transactions = {}
        self.heights = {}
        self.histories = {}
        self.unspent = {}

    @staticmethod
    def sh(script):
        return hashlib.sha256(script).digest()[::-1].hex()

    def update(self):
        head = self.btc.rpc('getbestblockhash')
        mempool = tuple(sorted(self.btc.rpc('getrawmempool')))
        if self.tip == (head, mempool):
            return
        height = self.btc.rpc('getblockcount')
        blocks = []
        for h in range(height + 1):
            digest = self.btc.rpc('getblockhash', h)
            if digest not in self.block_cache:
                self.block_cache[digest] = (self.btc.rpc('getblockheader', digest, False), self.btc.rpc('getblock', digest, 2)['tx'])
            blocks.append(self.block_cache[digest])
        self.blocks = blocks
        transactions, heights, histories, unspent, outputs = {}, {}, {}, {}, {}

        def add(digest, raw, h):
            tx = Transaction.deserialize(bytes.fromhex(raw))
            transactions[digest] = raw
            heights[digest] = h
            touched = set()
            for index, out in enumerate(tx.outputs):
                sh = self.sh(out.script_pubkey)
                outputs[(digest, index)] = sh
                unspent[(digest, index)] = (sh, h, out.value)
                touched.add(sh)
            for inp in tx.inputs:
                point = (inp.prev_txid[::-1].hex(), inp.prev_index)
                if point in outputs:
                    touched.add(outputs[point])
                unspent.pop(point, None)
            for sh in touched:
                histories.setdefault(sh, []).append({'tx_hash': digest, 'height': h})

        for h, (_, txs) in enumerate(blocks):
            for tx in txs:
                raw = tx.get('hex') or self.btc.rpc('getrawtransaction', tx['txid'], False, self.btc.rpc('getblockhash', h))
                add(tx['txid'], raw, h)
        for digest in mempool:
            add(digest, self.btc.rpc('getrawtransaction', digest), 0)
        self.transactions, self.heights, self.histories, self.unspent = transactions, heights, histories, unspent
        self.tip = (head, mempool)

    def call(self, method, params):
        with self.lock:
            if method == 'server.version':
                return ['SUMUWW-disposable-fixture', '1.4']
            if method == 'server.features':
                return {'genesis_hash': self.btc.rpc('getblockhash', 0)}
            if method == 'blockchain.transaction.broadcast':
                return self.btc.rpc('sendrawtransaction', *params)
            if method == 'blockchain.relayfee':
                return self.btc.rpc('getmempoolinfo')['minrelaytxfee']
            if method == 'mempool.get_fee_histogram':
                pool=self.btc.rpc('getrawmempool',True)
                return sorted([[float(e['fees']['base'])*100000000/e['vsize'],e['vsize']] for e in pool.values()],reverse=True)
            self.update()
            if method == 'blockchain.headers.subscribe':
                return {'height': len(self.blocks) - 1, 'hex': self.blocks[-1][0]}
            if method == 'blockchain.block.header':
                return self.blocks[params[0]][0]
            if method == 'blockchain.block.headers':
                start, count = params
                rows = self.blocks[start:start + count]
                return {'count': len(rows), 'hex': ''.join(row[0] for row in rows), 'max': 2016}
            if method == 'blockchain.scripthash.get_history':
                return copy.deepcopy(self.histories.get(params[0], []))
            if method == 'blockchain.scripthash.listunspent':
                return [{'tx_hash': digest, 'tx_pos': index, 'height': h, 'value': value}
                        for (digest, index), (sh, h, value) in self.unspent.items() if sh == params[0]]
            if method == 'blockchain.transaction.get':
                return self.transactions[params[0]]
            if method == 'blockchain.transaction.get_merkle':
                digest, h = params
                ids = [tx['txid'] for tx in self.blocks[h][1]]
                position = ids.index(digest)
                hashes = [bytes.fromhex(d)[::-1] for d in ids]
                index, branch = position, []
                while len(hashes) > 1:
                    if len(hashes) % 2:
                        hashes.append(hashes[-1])
                    branch.append(hashes[index ^ 1][::-1].hex())
                    hashes = [sha256d(hashes[i] + hashes[i + 1]) for i in range(0, len(hashes), 2)]
                    index //= 2
                return {'block_height': h, 'pos': position, 'merkle': branch}
            raise ValueError('Unsupported fixture method: ' + method)


class ElectrumFixture:
    def __init__(self, index):
        self.index = index
        self.offline = False
        self.mutate = lambda method, result: result
        self.calls = []
        owner = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(30)
                try:
                    while raw := self.rfile.readline(8_100_001):
                        if owner.offline:
                            return
                        packet = json.loads(raw)
                        method, params = packet['method'], packet.get('params', [])
                        owner.calls.append(method)
                        try:
                            result = owner.mutate(method, owner.index.call(method, params))
                            response = {'jsonrpc': '2.0', 'id': packet['id'], 'result': result}
                        except Exception:
                            response = {'jsonrpc': '2.0', 'id': packet['id'], 'error': {'code': 1, 'message': 'Test failure'}}
                        self.wfile.write(json.dumps(response).encode() + b'\n')
                except (OSError, ValueError):
                    return

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.server = Server(('127.0.0.1', 0), Handler)
        self.url = 'tcp://127.0.0.1:' + str(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
