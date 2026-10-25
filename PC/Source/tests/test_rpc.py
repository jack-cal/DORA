"""Real loopback HTTP requests and existing consensus through the public API."""

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from sumuww.address import encode_address
from sumuww.block import Block, GENESIS_TIME, mine_header
from sumuww.chain import Chain
from sumuww.peer import PeerNode
from sumuww.primitives import COIN, hash_to_display
from sumuww.rpc import (MAX_BATCH, MAX_BODY, MAX_HEADER, RpcServer,
                      load_or_create_token, read_token, validate_rpc_endpoint)
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh


NOW = GENESIS_TIME + 1000
ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)
TOKEN = '12' * 32


class RpcTokenTests(unittest.TestCase):
    def test_creation_reuse_and_existing_only_reader(self):
        with tempfile.TemporaryDirectory(prefix='rpc-token-') as directory:
            path = Path(directory) / 'user' / 'rpc.token'
            self.assertRaises(ValueError, read_token, path)
            self.assertFalse(path.exists())
            token = load_or_create_token(path)
            self.assertRegex(token, r'^[0-9a-f]{64}$')
            self.assertEqual(token, read_token(path))
            path.write_bytes((token + '\r\n').encode('ascii'))
            self.assertEqual(token, read_token(path))
            before = path.read_bytes()
            self.assertEqual(token, load_or_create_token(path))
            self.assertEqual(before, path.read_bytes())
            other = load_or_create_token(Path(directory) / 'other.token')
            self.assertNotEqual(token, other)

    def test_malformed_file_never_replaced_and_errors_do_not_disclose_path(self):
        with tempfile.TemporaryDirectory(prefix='rpc-token-') as directory:
            path = Path(directory) / 'rpc.token'
            for data in (b'', b'0' * 63, b'0' * 66, b'f' * 64 + b'\n\n',
                         b'F' * 64, b'\xff' * 64, b'../private/wallet'):
                path.write_bytes(data)
                for reader in (load_or_create_token, read_token):
                    with self.assertRaises(ValueError) as caught:
                        reader(path)
                    self.assertNotIn(str(path), str(caught.exception))
                    self.assertEqual(data, path.read_bytes())

    def test_numeric_loopback_only_and_strict_integer_ports(self):
        self.assertEqual(('127.0.0.1', 18443), validate_rpc_endpoint('127.0.0.1', 18443))
        self.assertEqual(('127.0.0.2', 0), validate_rpc_endpoint('127.0.0.2', 0))
        for host in ('0.0.0.0', '192.168.0.1', '8.8.8.8', 'localhost', '::1', None):
            self.assertRaises(ValueError, validate_rpc_endpoint, host, 18443)
        for port in (-1, 65536, '18443', True, 1.0):
            self.assertRaises(ValueError, validate_rpc_endpoint, '127.0.0.1', port)


class RpcHttpTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_directory = tempfile.TemporaryDirectory(prefix='rpc-seed-')
        cls.seed = Path(cls.seed_directory.name) / 'seed.sqlite'
        with Chain(cls.seed, clock=lambda: NOW) as chain:
            cls.blocks = chain.mine(ALICE.script_pubkey, 100)
            chain.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    @classmethod
    def tearDownClass(cls):
        cls.seed_directory.cleanup()

    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='rpc-case-')
        self.database = Path(self.directory.name) / 'chain.sqlite'
        shutil.copy2(self.seed, self.database)
        self.node = PeerNode(self.database, port=0, clock=lambda: NOW)
        await self.node.start()
        self.current_node = self.node
        self.server = RpcServer(lambda: self.current_node, TOKEN, port=0)
        await self.server.start()
        self.other_nodes = []
        self.writers = []
        self.address = encode_address(ALICE.script_pubkey)
        self.bob_address = encode_address(BOB.script_pubkey)

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.close()
        await self.server.stop()
        await self.node.stop()
        for node in self.other_nodes:
            await node.stop()
        self.directory.cleanup()

    async def raw_request(self, raw):
        reader, writer = await asyncio.open_connection(*self.server.address)
        writer.write(raw)
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), 5)
        writer.close()
        await writer.wait_closed()
        head, body = response.split(b'\r\n\r\n', 1)
        lines = head.decode('ascii').split('\r\n')
        headers = dict(line.lower().split(': ', 1) for line in lines[1:])
        self.assertEqual('close', headers['connection'])
        self.assertEqual(len(body), int(headers['content-length']))
        self.assertNotIn('access-control-allow-origin', headers)
        return int(lines[0].split(' ')[1]), json.loads(body) if body else None

    def packet(self, method='GET', path='/api/v1/info', body=None, headers=None):
        raw = b'' if body is None else body if isinstance(body, bytes) else json.dumps(body).encode()
        fields = {'Host': f'{self.server.address[0]}:{self.server.address[1]}',
                  'Authorization': 'Bearer ' + TOKEN}
        if method == 'POST':
            fields.update({'Content-Type': 'application/json', 'Content-Length': str(len(raw))})
        fields.update(headers or {})
        return (f'{method} {path} HTTP/1.1\r\n' +
                ''.join(f'{name}: {value}\r\n' for name, value in fields.items()) +
                '\r\n').encode() + raw

    async def request(self, method='GET', path='/api/v1/info', body=None, headers=None):
        return await self.raw_request(self.packet(method, path, body, headers))

    async def rpc(self, method, params=None, identifier=1):
        request = {'jsonrpc': '2.0', 'method': method, 'id': identifier}
        if params is not None:
            request['params'] = params
        status, response = await self.request('POST', '/rpc', request)
        self.assertEqual(200, status)
        self.assertEqual(identifier, response['id'])
        return response

    async def result(self, method, params=None):
        response = await self.rpc(method, params)
        self.assertNotIn('error', response, response)
        return response['result']

    def spend(self):
        previous = self.blocks[0].transactions[0]
        unsigned = Transaction(2, (TxInput(previous.txid(), 0),), (
            TxOutput(3 * COIN, BOB.script_pubkey),
            TxOutput(47 * COIN - 100_000, ALICE.script_pubkey)))
        return sign_p2wpkh(unsigned, 0, previous.outputs[0], ALICE)

    async def eventually(self, predicate):
        deadline = asyncio.get_running_loop().time() + 5
        while not predicate():
            if asyncio.get_running_loop().time() >= deadline:
                self.fail('Actual peer did not synchronize the API submission')
            await asyncio.sleep(.02)

    async def test_rpc_and_rest_real_node_reads(self):
        self.assertEqual(100, await self.result('getblockcount'))
        self.assertEqual(hash_to_display(self.blocks[-1].block_hash()),
                         await self.result('getbestblockhash'))
        info = await self.result('getblockchaininfo')
        self.assertEqual(100, info['height'])
        self.assertEqual('regtest', info['network'])
        for path in ('/api/v1/info', '/api/v1/network', '/api/v1/mempool'):
            status, value = await self.request(path=path)
            self.assertEqual(200, status)
            if path.endswith('/network'):
                self.assertNotIn('last_peer_error', value)
        self.assertEqual([], await self.result('getrawmempool'))
        self.assertNotIn(TOKEN, json.dumps(self.server.info()))
        self.assertTrue(self.server.info()['enabled'])

    async def test_auth_required_and_bad_token_no_reflection(self):
        for value in ('', 'Bearer wrong', 'Basic ' + TOKEN):
            status, response = await self.request(headers={'Authorization': value})
            self.assertEqual(401, status)
            self.assertNotIn(TOKEN, json.dumps(response))
            self.assertNotIn('wrong', json.dumps(response))

    async def test_host_origin_and_browser_csrf_rejected(self):
        for headers in ({'Host': 'evil.example'}, {'Host': 'localhost:18443'},
                        {'Origin': 'https://evil.example'}, {'Origin': 'null'},
                        {'Referer': 'https://evil.example/'},
                        {'Sec-Fetch-Site': 'cross-site'}, {'Sec-Fetch-Site': 'same-origin'}):
            status, _ = await self.request(headers=headers)
            self.assertEqual(403, status, headers)

    async def test_methods_parameters_and_precise_errors(self):
        unknown = await self.rpc('unlockwallet', ['password'])
        self.assertEqual(-32601, unknown['error']['code'])
        for method, params in [('getblockcount', [1]), ('getblockhash', []),
                               ('getblockhash', [True]), ('getblockhash', [1.5]),
                               ('getblockhash', {'height': 1, 'extra': 2}),
                               ('getblock', ['ff' * 32, 1]),
                               ('listunspent', [self.address, 1001]),
                               ('listunspent', [self.address, 1, -1]),
                               ('getaddressbalance', [self.bob_address.upper()[:-1] + 'x']),
                               ('sendrawtransaction', ['gg']),
                               ('submitblock', ['00 ']),
                               ('getrawtransaction', ['not-a-hash'])]:
            response = await self.rpc(method, params)
            self.assertEqual(-32602, response['error']['code'], (method, params, response))
        missing = await self.rpc('getblockhash', [101])
        self.assertEqual(-32001, missing['error']['code'])
        help_info = await self.result('help')
        self.assertFalse(help_info['wallet_signing'])
        self.assertIn('getblocktemplate', help_info['methods'])

    async def test_strict_json_invalid_requests_and_parse_errors(self):
        for raw in (b'{"jsonrpc":"2.0","method":"getblockcount","id":1,"id":2}',
                    b'{"jsonrpc":"2.0","method":"getblockhash","params":[NaN],"id":1}',
                    b'{"jsonrpc":"2.0","method":"getblockhash","params":[1e999],"id":1}',
                    b'\xff', b'{'):
            status, response = await self.request('POST', '/rpc', raw)
            self.assertEqual(200, status)
            self.assertEqual(-32700, response['error']['code'])
        for value in ([], None, 1, 'method', {},
                      {'jsonrpc': '1.0', 'method': 'getblockcount', 'id': 1},
                      {'jsonrpc': '2.0', 'method': 'getblockcount', 'params': 1, 'id': 1},
                      {'jsonrpc': '2.0', 'method': 'getblockcount', 'id': True},
                      {'jsonrpc': '2.0', 'method': 'getblockcount', 'id': 1, 'extra': 1}):
            raw = json.dumps(value).encode()
            _, response = await self.request('POST', '/rpc', raw)
            self.assertEqual(-32600, response['error']['code'], value)

    async def test_notification_batches_have_spec_responses(self):
        notification = {'jsonrpc': '2.0', 'method': 'getblockcount'}
        for value in (notification, [notification, {'jsonrpc': '2.0', 'method': 'unknown'}]):
            status, response = await self.request('POST', '/rpc', value)
            self.assertEqual((204, None), (status, response))
        batch = [notification, {'jsonrpc': '2.0', 'method': 'getblockcount', 'id': 7},
                 False, {'jsonrpc': '2.0', 'method': 'missing', 'id': 'x'}]
        status, response = await self.request('POST', '/rpc', batch)
        self.assertEqual(200, status)
        self.assertEqual(3, len(response))
        self.assertEqual(100, response[0]['result'])
        self.assertEqual(-32600, response[1]['error']['code'])
        self.assertEqual(-32601, response[2]['error']['code'])
        _, response = await self.request('POST', '/rpc', [notification] * (MAX_BATCH + 1))
        self.assertEqual(-32600, response['error']['code'])

    async def test_request_framing_resource_limits_and_media_type(self):
        basic = self.packet('POST', '/rpc', {'jsonrpc': '2.0', 'method': 'getblockcount', 'id': 1})
        header, body = basic.split(b'\r\n\r\n', 1)
        for extra in (b'\r\nContent-Length: ' + str(len(body)).encode(),
                      b'\r\nTransfer-Encoding: chunked', b'\r\nExpect: 100-continue',
                      b'\r\nAuthorization: Bearer ' + TOKEN.encode()):
            status, _ = await self.raw_request(header + extra + b'\r\n\r\n' + body)
            self.assertEqual(400, status)
        for length in ('-1', '00', '+1', 'one'):
            status, _ = await self.request('POST', '/rpc', b'{}', {'Content-Length': length})
            self.assertEqual(400, status)
        status, _ = await self.request('POST', '/rpc', b'', {'Content-Length': str(MAX_BODY + 1)})
        self.assertEqual(413, status)
        status, _ = await self.request('POST', '/rpc', b'{}', {'Content-Type': 'text/plain'})
        self.assertEqual(415, status)
        status, _ = await self.request(headers={'X-Fill': 'x' * (MAX_HEADER + 10)})
        self.assertIn(status, (400, 413))
        status, _ = await self.request('GET', '/api/v1/info', b'{}', {'Content-Length': '2'})
        self.assertEqual(400, status)

    async def test_deadline_and_stop_close_incomplete_connections(self):
        with patch('sumuww.rpc.REQUEST_TIMEOUT', .1):
            reader, writer = await asyncio.open_connection(*self.server.address)
            writer.write(b'POST /rpc HTTP/1.1\r\n')
            await writer.drain()
            response = await asyncio.wait_for(reader.read(), 2)
            self.assertIn(b'400', response.split(b'\r\n')[0])
            writer.close()
            await writer.wait_closed()
        reader, writer = await asyncio.open_connection(*self.server.address)
        self.writers.append(writer)
        writer.write(b'GET /api/v1/info HTTP/1.1\r\n')
        await writer.drain()
        await self.server.stop()
        self.assertEqual(b'', await asyncio.wait_for(reader.read(), 2))
        self.assertFalse(self.server.info()['enabled'])

    async def test_connection_limit_closes_excess(self):
        with patch('sumuww.rpc.MAX_CONNECTIONS', 2):
            for _ in range(2):
                _, writer = await asyncio.open_connection(*self.server.address)
                self.writers.append(writer)
                writer.write(b'GET /api/v1/info HTTP/1.1\r\n')
                await writer.drain()
            await asyncio.sleep(.01)
            reader, writer = await asyncio.open_connection(*self.server.address)
            self.writers.append(writer)
            self.assertEqual(b'', await asyncio.wait_for(reader.read(), 2))

    async def test_balances_maturity_and_bounded_utxos(self):
        balance = await self.result('getaddressbalance', {'address': self.address})
        self.assertEqual(5000 * COIN, balance['confirmed_units'])
        self.assertEqual(50 * COIN, balance['mature_units'])
        self.assertEqual('50.00000000', balance['available_smw'])
        status, page = await self.request(path=f'/api/v1/addresses/{self.address}/utxos?limit=7&offset=3')
        self.assertEqual(200, status)
        self.assertEqual(100, page['total'])
        self.assertEqual(7, len(page['utxos']))
        self.assertTrue(all(not item['mature'] for item in page['utxos']))
        page = await self.result('listunspent', [self.address, 100])
        first = next(item for item in page['utxos'] if item['height'] == 1)
        self.assertTrue(first['spendable'])
        self.assertEqual(100, first['confirmations'])
        for query in ('limit=0', 'limit=1001', 'offset=-1', 'offset=1000001',
                      'limit=2&limit=3', 'unknown=1', 'limit=1.5'):
            status, _ = await self.request(path=f'/api/v1/addresses/{self.address}/utxos?{query}')
            self.assertEqual(400, status)

    async def test_gettxout_exposes_only_unspent_spendable_pending_outputs(self):
        previous=self.blocks[0].transactions[0]
        tx=Transaction(2,(TxInput(previous.txid(),0),),(
            TxOutput(50*COIN-100_000,ALICE.script_pubkey),TxOutput(0,b'\x6a\x01x')))
        tx=sign_p2wpkh(tx,0,previous.outputs[0],ALICE)
        txid=(await self.result('sendrawtransaction',[tx.serialize().hex()]))['txid']
        out=await self.result('gettxout',[txid,0])
        self.assertEqual(0,out['confirmations']);self.assertFalse(out['coinbase'])
        self.assertIsNone(await self.result('gettxout',[txid,0,False]))
        self.assertIsNone(await self.result('gettxout',[txid,1]))
        child=Transaction(2,(TxInput(tx.txid(),0),),(TxOutput(tx.outputs[0].value-100_000,ALICE.script_pubkey),))
        child=sign_p2wpkh(child,0,tx.outputs[0],ALICE)
        await self.result('sendrawtransaction',[child.serialize().hex()])
        self.assertIsNone(await self.result('gettxout',[txid,0]))

    async def test_signed_transaction_mempool_template_block_and_confirmations(self):
        tx = self.spend()
        status, submitted = await self.request('POST', '/api/v1/transactions', {'hex': tx.serialize().hex()})
        self.assertEqual(200, status)
        self.assertEqual(hash_to_display(tx.txid()), submitted['txid'])
        self.assertEqual([submitted['txid']], await self.result('getrawmempool'))
        balance = await self.result('getaddressbalance', [self.address])
        self.assertEqual(50 * COIN, balance['pending_spent_units'])
        self.assertEqual(0, balance['available_units'])
        utxos = await self.result('listunspent', [self.address, 100])
        spent = next(item for item in utxos['utxos'] if item['height'] == 1)
        self.assertTrue(spent['pending_spent'])
        self.assertFalse(spent['spendable'])
        transaction = await self.result('getrawtransaction', [submitted['txid']])
        self.assertEqual(0, transaction['confirmations'])
        self.assertTrue(transaction['in_mempool'])
        self.assertEqual(tx.serialize().hex(), await self.result('getrawtransaction', [submitted['txid'], False]))
        status, template = await self.request('POST', '/api/v1/mining/template', {'address': self.address})
        self.assertEqual(200, status)
        self.assertEqual(101, template['height'])
        candidate = Block.deserialize(bytes.fromhex(template['block_hex']))
        self.assertEqual(tx, candidate.transactions[1])
        self.assertEqual(50 * COIN + 100_000, template['coinbase_value_units'])
        block = Block(mine_header(candidate.header), candidate.transactions)
        submitted_block = await self.result('submitblock', {'hex': block.serialize().hex()})
        self.assertTrue(submitted_block['activated'])
        self.assertEqual(101, await self.result('getblockcount'))
        self.assertEqual([], await self.result('getrawmempool'))
        transaction = await self.result('getrawtransaction', [submitted['txid']])
        self.assertEqual(1, transaction['confirmations'])
        self.assertFalse(transaction['in_mempool'])
        balance = await self.result('getaddressbalance', [self.bob_address])
        self.assertEqual(3 * COIN, balance['available_units'])
        status, viewed = await self.request(path='/api/v1/blocks/101')
        self.assertEqual(200, status)
        self.assertEqual(submitted_block['hash'], viewed['hash'])
        self.assertEqual(block.serialize().hex(), await self.result('getblock', [viewed['hash'], False]))
        duplicate = await self.result('submitblock', [block.serialize().hex()])
        self.assertTrue(duplicate['already_known'])
        self.assertFalse(duplicate['activated'])

    async def test_invalid_signature_double_spend_immaturity_and_block_pow_rejected(self):
        tx = self.spend()
        broken = replace(tx, inputs=(replace(tx.inputs[0], witness=(b'bad', tx.inputs[0].witness[1])),))
        for raw in (broken.serialize().hex(), '00'):
            response = await self.rpc('sendrawtransaction', [raw])
            self.assertEqual(-32002, response['error']['code'])
        immature = self.blocks[1].transactions[0]
        spending = Transaction(2, (TxInput(immature.txid(), 0),), (TxOutput(50 * COIN - 1, BOB.script_pubkey),))
        spending = sign_p2wpkh(spending, 0, immature.outputs[0], ALICE)
        response = await self.rpc('sendrawtransaction', [spending.serialize().hex()])
        self.assertEqual(-32002, response['error']['code'])
        await self.result('sendrawtransaction', [tx.serialize().hex()])
        duplicate = await self.rpc('sendrawtransaction', [tx.serialize().hex()])
        self.assertEqual(-32002, duplicate['error']['code'])
        template = await self.result('getblocktemplate', [self.address])
        block = Block.deserialize(bytes.fromhex(template['block_hex']))
        # A harder bits field is invalid contextually even if accidentally valid PoW.
        block = replace(block, header=replace(block.header, bits=0x1D00FFFF))
        response = await self.rpc('submitblock', [block.serialize().hex()])
        self.assertEqual(-32002, response['error']['code'])
        self.assertEqual(100, await self.result('getblockcount'))

    async def test_greater_work_reorg_updates_active_lookup_and_reenters_transaction(self):
        tx = self.spend()
        await self.result('sendrawtransaction', [tx.serialize().hex()])
        original = self.node.chain.make_block(ALICE.script_pubkey)
        await self.result('submitblock', [original.serialize().hex()])
        self.assertEqual(1, (await self.result('getrawtransaction', [hash_to_display(tx.txid())]))['confirmations'])
        side = self.node.chain.make_block(BOB.script_pubkey, transactions=(),
                                          parent_hash=self.blocks[-1].block_hash(), extra_nonce=11)
        side_result = await self.result('submitblock', [side.serialize().hex()])
        self.assertFalse(side_result['activated'])
        child = self.node.chain.make_block(BOB.script_pubkey, transactions=(),
                                           parent_hash=side.block_hash(), extra_nonce=12)
        await self.result('submitblock', [child.serialize().hex()])
        self.assertEqual(hash_to_display(side.block_hash()), await self.result('getblockhash', [101]))
        original_view = await self.result('getblock', [hash_to_display(original.block_hash())])
        self.assertFalse(original_view['active'])
        self.assertEqual(-1, original_view['confirmations'])
        reverted = await self.result('getrawtransaction', [hash_to_display(tx.txid())])
        self.assertEqual(0, reverted['confirmations'])
        self.assertTrue(reverted['in_mempool'])
        removed_coinbase = await self.rpc('getrawtransaction', [hash_to_display(original.transactions[0].txid())])
        self.assertEqual(-32001, removed_coinbase['error']['code'])
        self.assertEqual(102, await self.result('getblockcount'))

    async def test_rest_numeric_height_uses_one_revision_across_concurrent_reorg(self):
        with Chain(self.database, clock=lambda: NOW) as writer:
            side = writer.make_block(BOB.script_pubkey,
                                     parent_hash=self.blocks[98].block_hash(), extra_nonce=41)
            self.assertFalse(writer.accept_block(side))
            child = writer.make_block(BOB.script_pubkey,
                                      parent_hash=side.block_hash(), extra_nonce=42)
            original_call = self.server.call
            switched = False

            def commit_between_resolution_and_view(method, params=None):
                nonlocal switched
                if method == 'getblock' and not switched:
                    switched = True
                    self.assertTrue(writer.accept_block(child))
                return original_call(method, params)

            with patch.object(self.server, 'call', side_effect=commit_between_resolution_and_view):
                status, before = await self.request(path='/api/v1/blocks/100')
            self.assertEqual(200, status)
            self.assertTrue(switched)
            self.assertEqual(hash_to_display(self.blocks[-1].block_hash()), before['hash'])
            self.assertTrue(before['active'])
            self.assertEqual(1, before['confirmations'])
            self.assertFalse(self.node.chain.connection.in_transaction)
            status, after = await self.request(path='/api/v1/blocks/100')
            self.assertEqual(200, status)
            self.assertEqual(hash_to_display(side.block_hash()), after['hash'])
            self.assertTrue(after['active'])
            self.assertEqual(2, after['confirmations'])

    async def test_public_template_requires_connected_synced_peers(self):
        public = PeerNode(Path(self.directory.name) / 'public.sqlite', port=0, network='dora',
                          clock=lambda: 1_790_985_600 + 1000)
        self.other_nodes.append(public)
        await public.start()
        self.current_node = public
        address = encode_address(ALICE.script_pubkey, network='dora')
        denied = await self.rpc('getblocktemplate', [address])
        self.assertEqual(-32003, denied['error']['code'])
        other = PeerNode(Path(self.directory.name) / 'public-other.sqlite', port=0, network='dora',
                         poll_interval=.05, clock=lambda: 1_790_985_600 + 1000)
        self.other_nodes.append(other)
        await other.start()
        await public.connect(*other.address)
        await self.eventually(lambda: public.synchronization_info()['mining_ready'])
        template = await self.result('getblocktemplate', [address])
        self.assertEqual(1, template['height'])
        self.assertEqual('1e0377ae', template['bits'])
        await other.stop()
        await self.eventually(lambda: not public.synchronization_info()['mining_ready'])
        denied = await self.rpc('getblocktemplate', [address])
        self.assertEqual(-32003, denied['error']['code'])

    async def test_api_mutations_broadcast_over_existing_real_p2p(self):
        database = Path(self.directory.name) / 'peer.sqlite'
        shutil.copy2(self.seed, database)
        peer = PeerNode(database, port=0, poll_interval=.05, clock=lambda: NOW)
        self.other_nodes.append(peer)
        await peer.start()
        await peer.connect(*self.node.address)
        transaction = self.spend()
        await self.result('sendrawtransaction', [transaction.serialize().hex()])
        await self.eventually(lambda: peer.chain.has_mempool_transaction(transaction.txid()))
        template = await self.result('getblocktemplate', [self.address])
        candidate = Block.deserialize(bytes.fromhex(template['block_hex']))
        block = Block(mine_header(candidate.header), candidate.transactions)
        await self.result('submitblock', [block.serialize().hex()])
        await self.eventually(lambda: peer.chain.tip_hash == block.block_hash())
        self.assertEqual(101, peer.chain.info()['height'])
        self.assertEqual((), peer.chain.mempool_transactions())

    async def test_provider_reconfiguration_and_no_running_node(self):
        self.current_node = None
        response = await self.rpc('getblockcount')
        self.assertEqual(-32003, response['error']['code'])
        self.current_node = self.node
        self.assertEqual(100, await self.result('getblockcount'))
        replacement = PeerNode(Path(self.directory.name) / 'replacement.sqlite', port=0, clock=lambda: NOW)
        self.other_nodes.append(replacement)
        await replacement.start()
        self.current_node = replacement
        self.assertEqual(0, await self.result('getblockcount'))
        await replacement.stop()
        response = await self.rpc('getblockcount')
        self.assertEqual(-32003, response['error']['code'])

    async def test_error_messages_never_return_backend_paths_or_tokens(self):
        with patch.object(self.node.chain, 'info', side_effect=RuntimeError('/private/user/' + TOKEN)):
            response = await self.rpc('getblockchaininfo')
            self.assertEqual(-32603, response['error']['code'])
            self.assertNotIn(TOKEN, json.dumps(response))
            self.assertNotIn('/private', json.dumps(response))
        self.node._last_error = 'wallet /private/user/' + TOKEN
        info = await self.result('getnetworkinfo')
        self.assertNotIn(TOKEN, json.dumps(info))
        self.assertNotIn('last_peer_error', info)


if __name__ == '__main__':
    unittest.main()
