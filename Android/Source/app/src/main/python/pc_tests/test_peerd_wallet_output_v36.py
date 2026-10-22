"""Daemon status outputs preserve encrypted wallets in owned local fixtures."""

import argparse
import asyncio
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww import peerd
from sumuww.keystore import create_hd_wallet, create_wallet, load_wallet


PASSWORD = 'owned-peerd-writer-password'


class WalletOutputFixtures:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-peerd-wallet-v36-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.ready = self.folder / 'ready.json'

    def raw_wallet(self, hd=False):
        fixture = self.folder / ('seed-fixture.json' if hd else 'wallet-fixture.json')
        (create_hd_wallet if hd else create_wallet)(fixture, PASSWORD, network='regtest')
        return fixture.read_bytes()

    def assert_preserved(self, path, raw, *, hd=False):
        self.assertEqual(raw, path.read_bytes())
        self.assertEqual(hd, load_wallet(path, PASSWORD, network='regtest').is_hd)
        self.assertEqual([], list(self.folder.glob(path.name + '.*.tmp')))


class DaemonWalletOutputTests(WalletOutputFixtures, unittest.TestCase):
    def test_existing_v1_v2_wallets_are_never_replaced_by_status_output(self):
        for hd in (False, True):
            with self.subTest(hd=hd):
                raw = self.raw_wallet(hd)
                self.ready.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, 'must not overwrite an encrypted wallet'):
                    peerd.atomic_json(self.ready, {'running': True, 'height': 0})
                self.assert_preserved(self.ready, raw, hd=hd)

    def test_actual_cli_ready_wallet_path_rejects_and_closes_own_node(self):
        for hd in (False, True):
            with self.subTest(hd=hd):
                raw = self.raw_wallet(hd)
                wallet = self.folder / ('cli-seed.json' if hd else 'cli-wallet.json')
                wallet.write_bytes(raw)
                database = self.folder / ('seed-node.sqlite' if hd else 'wallet-node.sqlite')
                output, error = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                    code = peerd.main(['--network', 'regtest', '--database', str(database),
                        '--ready-file', str(wallet), '--listen', '127.0.0.1:0', '--poll-interval', '0.1'])
                self.assertEqual(2, code)
                self.assertEqual('ValueError', json.loads(error.getvalue())['error'])
                self.assertNotIn(PASSWORD, output.getvalue() + error.getvalue())
                self.assert_preserved(wallet, raw, hd=hd)
                # The error path must close its owned SQLite handles.
                moved = database.with_suffix('.closed')
                database.rename(moved)
                self.assertTrue(moved.exists())

    def test_hardlinked_wallet_keeps_both_names_and_spending_identity(self):
        raw = self.raw_wallet()
        wallet = self.folder / 'ordinary-wallet.json'
        wallet.write_bytes(raw)
        os.link(wallet, self.ready)
        with self.assertRaises(ValueError):
            peerd.atomic_json(self.ready, {'running': True})
        self.assert_preserved(wallet, raw)
        self.assert_preserved(self.ready, raw)

    def test_wallet_appearing_after_temporary_serialization_is_preserved(self):
        raw = self.raw_wallet(True)
        actual_dump = peerd.json.dump
        def appeared(value, output, **kwargs):
            actual_dump(value, output, **kwargs)
            self.ready.write_bytes(raw)
        with patch.object(peerd.json, 'dump', side_effect=appeared):
            with self.assertRaises(ValueError):
                peerd.atomic_json(self.ready, {'running': True})
        self.assert_preserved(self.ready, raw, hd=True)

    def test_wallet_appearing_after_permission_error_is_rechecked_before_retry(self):
        raw = self.raw_wallet()
        self.ready.write_text('{"running":true}', encoding='utf-8')
        def blocked(source, destination):
            self.ready.write_bytes(raw)
            raise PermissionError('owned publication retry fixture')
        with (patch.object(peerd.os, 'replace', side_effect=blocked) as replacement,
              patch.object(peerd.time, 'sleep')):
            with self.assertRaisesRegex(ValueError, 'must not overwrite an encrypted wallet'):
                peerd.atomic_json(self.ready, {'running': False})
        self.assertEqual(1, replacement.call_count)
        self.assert_preserved(self.ready, raw)

    def test_normal_status_unicode_retry_and_malformed_ordinary_json_behavior_are_retained(self):
        self.ready.write_bytes(b'{malformed ordinary status')
        actual_replace = peerd.os.replace
        calls = []
        def retry(source, destination):
            calls.append(1)
            if len(calls) == 1:
                raise PermissionError('owned reader conflict')
            return actual_replace(source, destination)
        expected = {'running': True, 'height': 0, 'memo': '정상 상태'}
        with patch.object(peerd.os, 'replace', side_effect=retry), patch.object(peerd.time, 'sleep'):
            peerd.atomic_json(self.ready, expected)
        self.assertEqual(2, len(calls))
        self.assertEqual(expected, json.loads(self.ready.read_text(encoding='utf-8')))
        self.assertEqual([], list(self.folder.glob('ready.json.*.tmp')))

    def test_recognizable_wallet_rejects_before_temporary_output_and_without_kdf(self):
        for format_name in ('dora-single-key-wallet', 'dora-hd-wallet'):
            with self.subTest(format=format_name):
                raw = json.dumps({'format': format_name}).encode('utf-8')
                self.ready.write_bytes(raw)
                with (patch('sumuww.keystore._derive_key', side_effect=AssertionError('KDF used')),
                      patch.object(peerd.tempfile, 'NamedTemporaryFile', side_effect=AssertionError('Temporary output opened'))):
                    with self.assertRaises(ValueError):
                        peerd.atomic_json(self.ready, {'running': True})
                self.assertEqual(raw, self.ready.read_bytes())


class DaemonLiveWalletOutputTests(WalletOutputFixtures, unittest.IsolatedAsyncioTestCase):
    async def test_wallet_appearing_during_live_status_refresh_preserves_bytes_and_closes_node(self):
        raw = self.raw_wallet(True)
        options = argparse.Namespace(database=self.folder / 'node.sqlite', listen='127.0.0.1:0',
            peer=[], poll_interval=.05, timeout=1, max_peers=8, ready_file=self.ready,
            stop_file=self.folder / 'stop', network='regtest')
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            task = asyncio.create_task(peerd.serve(options))
            for _ in range(100):
                if self.ready.exists():
                    break
                await asyncio.sleep(.01)
            self.assertTrue(self.ready.exists())
            self.assertTrue(json.loads(self.ready.read_bytes())['running'])
            self.ready.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'must not overwrite an encrypted wallet'):
                await asyncio.wait_for(task, timeout=5)
        self.assertNotIn(PASSWORD, output.getvalue() + error.getvalue())
        self.assert_preserved(self.ready, raw, hd=True)
        moved = options.database.with_suffix('.closed')
        options.database.rename(moved)
        self.assertTrue(moved.exists())


if __name__ == '__main__':
    unittest.main()
