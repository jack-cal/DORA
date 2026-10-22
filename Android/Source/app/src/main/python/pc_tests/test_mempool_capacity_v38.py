"""Local overload is temporary, observable and does not debit a failed transfer."""
import asyncio
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from sumuww.block import GENESIS_TIME
from sumuww.chain import Chain
from sumuww.errors import MempoolFull
from sumuww.i18n import LANGUAGE_CODES, Translator, set_translator
from sumuww.peer import PeerNode
from sumuww.rpc import RpcServer
from sumuww.transaction import Transaction, TxInput, TxOutput
from sumuww.wallet import RegtestKey, sign_p2wpkh

NOW = GENESIS_TIME + 4000
KEY = RegtestKey.from_int(38101)
TOKEN = '38' * 32
MESSAGE = "This node's pending transaction pool is full. Your transfer was not queued. Try again after pending transactions are confirmed."


class MempoolCapacityTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_directory = tempfile.TemporaryDirectory(prefix='sumuww-owned-capacity-seed-')
        cls.seed = Path(cls.seed_directory.name) / 'seed.sqlite'
        with Chain(cls.seed, clock=lambda: NOW) as chain:
            first = chain.mine(KEY.script_pubkey, 100)[0].transactions[0]
            value = (first.outputs[0].value - 100_000) // 4
            unsigned = Transaction(2, (TxInput(first.txid(), 0),),
                                   tuple(TxOutput(value, KEY.script_pubkey) for _ in range(4)))
            cls.funding = sign_p2wpkh(unsigned, 0, first.outputs[0], KEY)
            chain.submit_transaction(cls.funding)
            chain.mine(KEY.script_pubkey)
            chain.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    @classmethod
    def tearDownClass(cls):
        cls.seed_directory.cleanup()

    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='sumuww-owned-capacity-')
        path = Path(self.directory.name) / 'chain.sqlite'
        shutil.copy2(self.seed, path)
        self.node = PeerNode(path, port=0, clock=lambda: NOW)
        await self.node.start()
        self.rpc = RpcServer(lambda: self.node, TOKEN, port=0)
        await self.rpc.start()

    async def asyncTearDown(self):
        await self.rpc.stop()
        await self.node.stop()
        self.directory.cleanup()

    def transaction(self, index):
        output = self.funding.outputs[index]
        tx = Transaction(2, (TxInput(self.funding.txid(), index),),
                         (TxOutput(output.value - 1000, KEY.script_pubkey),))
        return sign_p2wpkh(tx, 0, output, KEY)

    async def http(self, method, path, body=None, *, authenticated=True):
        raw = json.dumps(body).encode() if body is not None else b''
        fields = [f'Host: {self.rpc.address[0]}:{self.rpc.address[1]}']
        if authenticated:
            fields.append('Authorization: Bearer ' + TOKEN)
        if body is not None:
            fields.extend(['Content-Type: application/json', f'Content-Length: {len(raw)}'])
        packet = (f'{method} {path} HTTP/1.1\r\n' + '\r\n'.join(fields) + '\r\n\r\n').encode() + raw
        reader, writer = await asyncio.open_connection(*self.rpc.address)
        try:
            writer.write(packet)
            await writer.drain()
            result = await asyncio.wait_for(reader.read(), 3)
        finally:
            writer.close()
            await writer.wait_closed()
        head, payload = result.split(b'\r\n\r\n', 1)
        return int(head.split(b' ')[1]), json.loads(payload)

    async def test_capacity_endpoint_reports_count_bytes_without_wallet_secrets(self):
        initial = self.rpc.call('getmempoolinfo')
        self.assertEqual({'size': 0, 'bytes': 0, 'max_transactions': 1000, 'max_bytes': 4_000_000,
                          'remaining_transactions': 1000, 'remaining_bytes': 4_000_000, 'full': False}, initial)
        tx = self.transaction(0)
        self.node.chain.submit_transaction(tx)
        status, result = await self.http('GET', '/api/v1/mempool/info')
        self.assertEqual(200, status)
        self.assertEqual(1, result['size'])
        self.assertEqual(len(tx.serialize()), result['bytes'])
        self.assertEqual(999, result['remaining_transactions'])
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertEqual(401, (await self.http('GET', '/api/v1/mempool/info', authenticated=False))[0])

    async def test_count_overflow_not_queued_not_debited_then_confirmation_reopens_capacity(self):
        chain = self.node.chain
        with patch('sumuww.chain.MAX_MEMPOOL_TRANSACTIONS', 2):
            chain.submit_transaction(self.transaction(0))
            chain.submit_transaction(self.transaction(1))
            rejected = self.transaction(2)
            commitment = chain.state_commitment()
            with self.assertRaises(MempoolFull):
                chain.submit_transaction(rejected)
            self.assertEqual(commitment, chain.state_commitment())
            self.assertFalse(chain.has_mempool_transaction(rejected.txid()))
            self.assertTrue(chain.mempool_info()['full'])
            status, result = await self.http('POST', '/api/v1/transactions', {'hex': rejected.serialize().hex()})
            self.assertEqual(503, status)
            self.assertEqual(-32005, result['error']['code'])
            self.assertIn('not queued', result['error']['message'])
            self.assertEqual(2, chain.mempool_info()['size'])
            chain.mine(KEY.script_pubkey)
            self.assertFalse(chain.mempool_info()['full'])
            self.assertEqual(2, chain.mempool_info()['remaining_transactions'])
            status, result = await self.http('POST', '/api/v1/transactions', {'hex': rejected.serialize().hex()})
            self.assertEqual(200, status)
            self.assertTrue(result['accepted'])

    async def test_byte_capacity_exact_boundary_rejects_addition_without_mutating_pool(self):
        chain = self.node.chain
        first = self.transaction(0)
        with patch('sumuww.chain.MAX_MEMPOOL_BYTES', len(first.serialize())):
            chain.submit_transaction(first)
            self.assertTrue(chain.mempool_info()['full'])
            self.assertEqual(0, chain.mempool_info()['remaining_bytes'])
            with self.assertRaises(MempoolFull):
                chain.submit_transaction(self.transaction(1))
            self.assertEqual((first,), chain.mempool_transactions())

    async def test_json_rpc_reports_retryable_capacity_and_keeps_validation_distinct(self):
        with patch('sumuww.chain.MAX_MEMPOOL_TRANSACTIONS', 0):
            request = {'jsonrpc': '2.0', 'id': 38, 'method': 'sendrawtransaction',
                       'params': [self.transaction(0).serialize().hex()]}
            status, result = await self.http('POST', '/rpc', request)
            self.assertEqual(200, status)
            self.assertEqual(38, result['id'])
            self.assertEqual(-32005, result['error']['code'])
        self.assertEqual(0, self.node.chain.mempool_info()['size'])
        request['params'] = ['00']
        _, invalid = await self.http('POST', '/rpc', request)
        self.assertNotEqual(-32005, invalid['error']['code'])

    async def test_capacity_error_is_localized_for_all_eleven_languages(self):
        from sumuww.app import _error_message
        try:
            for language in LANGUAGE_CODES:
                translator = Translator(language)
                set_translator(translator)
                self.assertEqual(translator.render(MESSAGE), str(_error_message(MempoolFull('Local mempool resource limit'))))
                if language != 'en':
                    self.assertNotEqual(MESSAGE, translator.render(MESSAGE))
        finally:
            set_translator(Translator('en'))


if __name__ == '__main__':
    unittest.main()
