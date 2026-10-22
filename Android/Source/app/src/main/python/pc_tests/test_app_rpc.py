"""Authenticated API lifecycle on the real node actor, using temporary data."""

import json
from concurrent.futures import Future
from pathlib import Path
import socket
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import urllib.error
import urllib.request

from coincurve import PrivateKey

from sumuww.app_service import AppService, RPC_SETTINGS_NAME, RPC_TOKEN_NAME
from sumuww.keystore import WalletKey
from sumuww.profiles import REGTEST
from sumuww.rpc import read_token


class AppRpcTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-app-rpc-')
        self.directory = Path(self.temp.name)
        self.services = []

    def tearDown(self):
        for service in reversed(self.services):
            service.stop().result(timeout=15)
        self.temp.cleanup()

    def service(self):
        service = AppService(self.directory, network=REGTEST, peers=[])
        self.services.append(service)
        service.start().result(timeout=10)
        return service

    def test_unchanged_connection_settings_and_wallet_actions_keep_node_instance(self):
        service = self.service()
        original = service._node
        settings = dict(service._settings)
        service.configure_network(settings['listen'], settings['peers'],
            allow_internet=settings['allow_internet'],allow_lan=settings['allow_lan'],
            auto_address=service._auto_address).result(timeout=10)
        self.assertIs(original,service._node)
        self.wallet(service)
        self.assertIs(original,service._node)
        service.lock_wallet().result(timeout=10)
        self.assertIs(original,service._node)

    def query(self, endpoint, method='getblockcount', token=None):
        request = urllib.request.Request(
            endpoint, data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method}).encode(),
            headers={'Content-Type': 'application/json',
                     'Authorization': 'Bearer ' + (token or read_token(self.directory / RPC_TOKEN_NAME))})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def wallet(self, service):
        key = WalletKey(PrivateKey((1).to_bytes(32, 'big')), REGTEST)
        with patch('sumuww.app_service.keystore_create', return_value=key):
            wallet = service.create_wallet('fixture.json', 'test only').result(timeout=10)
        return wallet

    def assert_closed(self, port):
        with self.assertRaises(OSError):
            socket.create_connection(('127.0.0.1', port), timeout=.5)

    def test_disabled_default_auth_enable_mining_and_disable_keep_wallet(self):
        service = self.service()
        first = service.status().result(timeout=5)
        self.assertFalse(first['rpc']['enabled'])
        self.assertFalse((self.directory / RPC_TOKEN_NAME).exists())
        wallet = self.wallet(service)
        enabled = service.configure_rpc(True, 0).result(timeout=5)
        self.assertEqual(wallet['address'], enabled['wallet']['address'])
        self.assertTrue(enabled['wallet']['unlocked'])
        self.assertEqual(0, self.query(enabled['rpc']['endpoint'])['result'])
        with self.assertRaises(urllib.error.HTTPError) as denied:
            self.query(enabled['rpc']['endpoint'], token='bad token')
        self.assertEqual(401, denied.exception.code)
        service.mine_one().result(timeout=10)
        self.assertEqual(1, self.query(enabled['rpc']['endpoint'])['result'])
        unsupported = self.query(enabled['rpc']['endpoint'], method='sendtoaddress')
        self.assertEqual(-32601, unsupported['error']['code'])
        secret = read_token(self.directory / RPC_TOKEN_NAME)
        self.assertNotIn(secret, json.dumps(enabled))
        self.assertNotIn(secret, (self.directory / RPC_SETTINGS_NAME).read_text())
        disabled = service.configure_rpc(False, 0).result(timeout=5)
        self.assertFalse(disabled['rpc']['enabled'])
        self.assertEqual(wallet['address'], disabled['wallet']['address'])
        self.assertTrue(disabled['wallet']['unlocked'])
        self.assert_closed(enabled['rpc']['active_port'])

    def test_reconfigure_moves_listener_and_network_swap_keeps_api_working(self):
        service = self.service()
        self.wallet(service)
        original = service.configure_rpc(True, 0).result(timeout=5)['rpc']
        # Request a new ephemeral listener by changing the saved port first.
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            candidate_port = reservation.getsockname()[1]
        changed = service.configure_rpc(True, candidate_port).result(timeout=5)['rpc']
        self.assert_closed(original['active_port'])
        self.assertEqual(0, self.query(changed['endpoint'])['result'])
        updated = service.configure_network('127.0.0.1:0', [], allow_lan=True).result(timeout=10)
        self.assertTrue(updated['wallet']['unlocked'])
        self.assertEqual(changed['endpoint'], updated['rpc']['endpoint'])
        self.assertEqual(0, self.query(changed['endpoint'])['result'])
        service.mine_one().result(timeout=10)
        self.assertEqual(1, self.query(changed['endpoint'])['result'])

    def test_bind_and_atomic_save_failures_preserve_listener_wallet_and_preferences(self):
        service = self.service()
        wallet = self.wallet(service)
        original = service.configure_rpc(True, 0).result(timeout=5)['rpc']
        before = (self.directory / RPC_SETTINGS_NAME).read_bytes()
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            with self.assertRaises(Exception):
                service.configure_rpc(True, occupied.getsockname()[1]).result(timeout=5)
        with patch('sumuww.app_service._atomic_json', side_effect=PermissionError('fixture')):
            with self.assertRaises(Exception):
                service.configure_rpc(False, 0).result(timeout=5)
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                candidate_port = reservation.getsockname()[1]
            with self.assertRaises(Exception):
                service.configure_rpc(True, candidate_port).result(timeout=5)
            self.assert_closed(candidate_port)
        current = service.status().result(timeout=5)
        self.assertEqual(original['endpoint'], current['rpc']['endpoint'])
        self.assertEqual(wallet['address'], current['wallet']['address'])
        self.assertTrue(current['wallet']['unlocked'])
        self.assertEqual(before, (self.directory / RPC_SETTINGS_NAME).read_bytes())
        self.assertEqual(0, self.query(original['endpoint'])['result'])

    def test_persisted_enable_restarts_and_shutdown_closes_partial_http_client(self):
        service = self.service()
        enabled = service.configure_rpc(True, 0).result(timeout=5)['rpc']
        token = read_token(self.directory / RPC_TOKEN_NAME)
        service.stop().result(timeout=10)
        self.assert_closed(enabled['active_port'])
        restarted = self.service()
        rpc = restarted.status().result(timeout=5)['rpc']
        self.assertTrue(rpc['enabled'])
        self.assertEqual(token, read_token(self.directory / RPC_TOKEN_NAME))
        client = socket.create_connection(('127.0.0.1', rpc['active_port']), timeout=2)
        try:
            client.sendall(b'POST /rpc HTTP/1.1\r\nHost: 127.0.0.1\r\n')
            before = time.monotonic()
            restarted.stop().result(timeout=10)
            self.assertLess(time.monotonic() - before, 3, 'Partial HTTP client delayed node shutdown')
            received = b''
            try:
                while True:
                    chunk = client.recv(1024)
                    if not chunk:
                        break
                    received += chunk
                    self.assertLess(len(received), 8192)
            except ConnectionResetError:
                pass
        finally:
            client.close()
        self.assert_closed(rpc['active_port'])

    def test_malformed_preferences_fail_closed_and_rpc_paths_cannot_be_wallets(self):
        for document in ('{broken', '{"schema_version":1,"enabled":true,"port":true}',
                         '{"schema_version":1,"enabled":true,"port":18443,"token":"bad"}',
                         'x' * 5000):
            with self.subTest(document=document[:50]):
                (self.directory / RPC_SETTINGS_NAME).write_text(document, encoding='utf-8')
                service = self.service()
                self.assertFalse(service.status().result(timeout=5)['rpc']['enabled'])
                self.assertFalse((self.directory / RPC_TOKEN_NAME).exists())
                service.stop().result(timeout=10)
        service = self.service()
        for name in (RPC_TOKEN_NAME, RPC_SETTINGS_NAME):
            with self.assertRaisesRegex(Exception, 'Wallet and backup paths'):
                service.create_wallet(name, 'unused password').result(timeout=5)

    def test_saved_enabled_occupied_port_does_not_block_wallet_start(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            (self.directory / RPC_SETTINGS_NAME).write_text(json.dumps(
                {'schema_version': 1, 'enabled': True, 'port': occupied.getsockname()[1]}), encoding='utf-8')
            service = self.service()
            status = service.status().result(timeout=5)
            self.assertFalse(status['rpc']['enabled'])
            self.assertTrue(status['rpc']['configured_enabled'])
            self.assertIsNotNone(status['rpc']['error'])
            self.wallet(service)
            self.assertTrue(service.configure_rpc(True, 0).result(timeout=5)['wallet']['unlocked'])


class RpcUiTests(unittest.TestCase):
    def test_rpc_action_while_mining_preserves_wallet_inputs_and_localizes_status(self):
        import tkinter as tk
        from sumuww.app import SumuwwApp
        with tempfile.TemporaryDirectory(prefix='sumuww-rpc-ui-') as directory:
            try:
                root = tk.Tk()
            except tk.TclError as error:
                self.skipTest(f'Tk display unavailable: {error}')
            root.withdraw()
            status = {'node': {'height': 0, 'peers': 0},
                      'wallet': {'address': 'drt1qfixture', 'path': 'fixture.json', 'unlocked': True},
                      'rpc': {'enabled': True, 'configured_enabled': True, 'port': 0,
                              'active_port': 34567, 'endpoint': 'http://127.0.0.1:34567/rpc',
                              'token_file': str(Path(directory) / 'rpc-token'), 'error': None}}

            def completed(value):
                future = Future()
                future.set_result(value)
                return future

            calls = []
            service = SimpleNamespace(directory=Path(directory), network=REGTEST,
                                      start=lambda: completed(status), status=lambda: completed(status),
                                      configure_rpc=lambda enabled, port: (calls.append((enabled, port))
                                                                          or completed(status)))
            app = SumuwwApp(root, service, language='en', language_path=Path(directory) / 'language.json')
            try:
                app._started = True
                app._apply_status(status)
                app.send_address.set('drt1qtyped')
                app.send_amount.set('1.25000000')
                app._mining = app._mine_inflight = True
                app._mine_completed, app._mine_target = 2, 10
                app._sync_controls()
                self.assertEqual('normal', str(app.rpc_button.cget('state')))
                with patch('sumuww.app._RpcDialog', return_value=SimpleNamespace(result={'enabled': True, 'port': 0})):
                    app._configure_rpc()
                app._pump()
                self.assertEqual([(True, 0)], calls)
                self.assertTrue(app._mining)
                self.assertTrue(app._mine_inflight)
                self.assertEqual((2, 10), (app._mine_completed, app._mine_target))
                self.assertTrue(app._wallet['unlocked'])
                self.assertEqual('drt1qtyped', app.send_address.get())
                self.assertEqual('1.25000000', app.send_amount.get())
                self.assertEqual('RPC/API active · Port 34567', app.rpc_text.get())
                self.assertTrue(app.set_language('ko'))
                self.assertEqual('RPC/API \uc0ac\uc6a9 \uc911 \xb7 \ud3ec\ud2b8 34567', app.rpc_text.get())
                self.assertIn(app.translator.render('RPC/API guide'),
                              [message.render() for _, message in app._docs_menu_records])
            finally:
                app._finish_close()


if __name__ == '__main__':
    unittest.main()
