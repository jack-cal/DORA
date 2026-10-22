"""Rollback and demo writers preserve owned ciphertext and normal behavior."""

import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from sumuww import app_service, demo
from sumuww.chain import Chain
from sumuww.keystore import create_hd_wallet, create_wallet
from sumuww.network_settings import normalize_settings


PASSWORD = 'owned-rollback-demo-envelope-password'


class RollbackDemoWalletWriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory(prefix='sumuww-rollback-envelopes-v36-')
        cls.addClassCleanup(cls.fixtures.cleanup)
        cls.envelopes = {}
        for hd in (False, True):
            path = Path(cls.fixtures.name) / ('v2.json' if hd else 'v1.json')
            (create_hd_wallet if hd else create_wallet)(path, PASSWORD, network='regtest')
            cls.envelopes[hd] = path.read_bytes()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-rollback-demo-v36-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / 'network-settings.json'

    def assert_preserved(self, raw, path=None):
        self.assertEqual(raw, (path or self.path).read_bytes())
        self.assertEqual([], list(self.folder.glob('*.tmp')))

    def test_rollback_neither_deletes_nor_replaces_existing_v1_v2_wallets(self):
        for hd, raw in self.envelopes.items():
            for prior in (None, b'{"schema_version":1,"old":true}\n'):
                with self.subTest(hd=hd, prior_missing=prior is None):
                    self.path.write_bytes(raw)
                    with (patch('sumuww.keystore._derive_key', side_effect=AssertionError('KDF used')),
                          patch.object(app_service.tempfile, 'NamedTemporaryFile', side_effect=AssertionError('Temporary output opened'))):
                        with self.assertRaisesRegex(ValueError, 'must not overwrite an encrypted wallet'):
                            app_service._restore_preference(self.path, prior)
                    self.assert_preserved(raw)

    def test_rollback_preserves_hardlinked_wallet_destination_and_other_name(self):
        raw = self.envelopes[True]
        wallet = self.folder / 'ordinary-wallet.json'
        wallet.write_bytes(raw)
        os.link(wallet, self.path)
        for prior in (None, b'old ordinary settings'):
            with self.assertRaises(ValueError):
                app_service._restore_preference(self.path, prior)
            self.assert_preserved(raw)
            self.assert_preserved(raw, wallet)

    def test_rollback_rechecks_wallet_appearing_after_temporary_fsync(self):
        raw = self.envelopes[False]
        self.path.write_bytes(b'ordinary new preference')
        actual_fsync = app_service.os.fsync
        def appear(descriptor):
            actual_fsync(descriptor)
            self.path.write_bytes(raw)
        with patch.object(app_service.os, 'fsync', side_effect=appear):
            with self.assertRaises(ValueError):
                app_service._restore_preference(self.path, b'exact old preference\r\n')
        self.assert_preserved(raw)

    def test_actual_network_update_failure_keeps_wallet_appearing_before_rollback(self):
        service = object.__new__(app_service.AppService)
        service.directory, service._auto_address = self.folder, False
        settings = normalize_settings('127.0.0.1:0', [])
        for hd, raw in self.envelopes.items():
            for prior in (None, json.dumps(settings).encode('utf-8')):
                with self.subTest(hd=hd, prior_missing=prior is None):
                    for name in ('network-settings.json', 'public-contact.json', 'own-address-settings.json'):
                        (self.folder / name).unlink(missing_ok=True)
                    if prior is not None:
                        self.path.write_bytes(prior)
                    def failed_followup(path, value):
                        self.path.write_bytes(raw)
                        raise OSError('owned follow-up publication failure')
                    with patch.object(app_service, '_atomic_json', side_effect=failed_followup):
                        with self.assertRaisesRegex(ValueError, 'must not overwrite an encrypted wallet'):
                            service._persist_network(settings, '127.0.0.1:18444')
                    self.assert_preserved(raw)

    def test_normal_rollback_restores_exact_bytes_deletes_new_file_and_cleans_failed_temp(self):
        prior = b'old preference exact\r\n'
        self.path.write_bytes(b'new preference')
        app_service._restore_preference(self.path, prior)
        self.assertEqual(prior, self.path.read_bytes())
        with patch.object(app_service.os, 'replace', side_effect=PermissionError('owned reader conflict')):
            with self.assertRaises(PermissionError):
                app_service._restore_preference(self.path, b'other old bytes')
        self.assertEqual(prior, self.path.read_bytes())
        self.assertEqual([], list(self.folder.glob('*.tmp')))
        app_service._restore_preference(self.path, None)
        self.assertFalse(self.path.exists())

    def test_demo_rejects_nonempty_wallet_directory_before_chain_or_mining(self):
        output = self.folder / 'demo_result.json'
        for hd, raw in self.envelopes.items():
            with self.subTest(hd=hd):
                output.write_bytes(raw)
                with patch.object(demo, 'Chain', side_effect=AssertionError('Chain opened')):
                    with self.assertRaisesRegex(ValueError, 'new or empty directory'):
                        demo.run(self.folder)
                self.assert_preserved(raw, output)
                self.assertEqual([output], list(self.folder.iterdir()))

    def test_normal_empty_directory_demo_keeps_payment_restart_reorg_result(self):
        directory = self.folder / 'new-demo'
        result = demo.run(directory)
        self.assertEqual(103, result['final']['height'])
        self.assertTrue(result['payment']['double_spend_rejected'])
        self.assertTrue(result['restart_preserved_tip_and_utxo'])
        self.assertTrue(result['reorg']['disconnected_payment_returned_to_mempool'])
        self.assertEqual(result, json.loads((directory / 'demo_result.json').read_bytes()))

    def test_demo_report_rechecks_wallet_appearing_during_result_serialization(self):
        raw = self.envelopes[True]
        directory = self.folder / 'race-demo'
        output = directory / 'demo_result.json'
        actual_dumps = demo.json.dumps
        def appear(value, *args, **kwargs):
            document = actual_dumps(value, *args, **kwargs)
            if isinstance(value, dict) and value.get('scope') == 'independent local-regtest prototype':
                output.write_bytes(raw)
            return document
        with patch.object(demo.json, 'dumps', side_effect=appear):
            with self.assertRaisesRegex(ValueError, 'must not overwrite an encrypted wallet'):
                demo.run(directory)
        self.assert_preserved(raw, output)
        # Real owned regtest work completed, but the wallet report was preserved.
        with Chain(directory / 'sumuww.sqlite') as chain:
            self.assertEqual(103, chain.info()['height'])

    def test_sqlite_readonly_preflight_rejects_v1_v2_wallet_without_mutation(self):
        database = self.folder / 'node.sqlite'
        for hd, raw in self.envelopes.items():
            with self.subTest(hd=hd):
                database.write_bytes(raw)
                with self.assertRaises(sqlite3.DatabaseError):
                    Chain(database, network='regtest')
                self.assert_preserved(raw, database)
                self.assertEqual([database], list(self.folder.iterdir()))


if __name__ == '__main__':
    unittest.main()
