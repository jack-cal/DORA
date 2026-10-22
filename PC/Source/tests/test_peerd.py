"""Daemon path isolation and atomic status/lifecycle checks."""

import argparse
import asyncio
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sumuww import peerd


class DaemonFileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='sumuww-daemon-files-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.database = self.root / 'node.sqlite'

    def test_loopback_endpoints_and_dynamic_listener_port(self):
        self.assertEqual(('127.0.0.1', 0), peerd.endpoint('127.0.0.1:0'))
        self.assertEqual(('127.0.0.2', 12345), peerd.endpoint('127.0.0.2:12345', allow_zero=False))

    def test_public_hostname_ipv6_and_invalid_ports_rejected(self):
        for text in ('0.0.0.0:1000', '192.168.1.1:1000', 'localhost:1000', '::1:1000', '127.0.0.1:-1', '127.0.0.1:65536', '127.0.0.1:x'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                peerd.endpoint(text)
        with self.assertRaises(ValueError):
            peerd.endpoint('127.0.0.1:0', allow_zero=False)

    def test_database_and_sqlite_sidecars_are_reserved(self):
        for suffix in ('', '-wal', '-shm', '-journal', '.peers.json', '.peers.json.tmp'):
            reserved = Path(str(self.database) + suffix)
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                peerd.validate_state_paths(self.database, reserved, self.root / 'stop')
            with self.subTest(stop=suffix), self.assertRaises(ValueError):
                peerd.validate_state_paths(self.database, self.root / 'ready', reserved)
            with self.subTest(token=suffix), self.assertRaises(ValueError):
                peerd.validate_state_paths(self.database, rpc_token_file=reserved)

    def test_same_auxiliary_or_relative_alias_is_rejected(self):
        ready = self.root / 'ready.json'
        with self.assertRaises(ValueError):
            peerd.validate_state_paths(self.database, ready, ready)
        with self.assertRaises(ValueError):
            peerd.validate_state_paths(self.database, self.root / 'child' / '..' / 'node.sqlite')

    def test_distinct_paths_and_case_alias(self):
        peerd.validate_state_paths(self.database, self.root / 'ready', self.root / 'stop')
        import os
        if os.name == 'nt':
            with self.assertRaises(ValueError):
                peerd.validate_state_paths(self.database, self.root / 'NODE.SQLITE')

    def test_atomic_json_replaces_complete_document(self):
        path = self.root / 'ready.json'
        peerd.atomic_json(path, {'running': True, 'height': 10})
        peerd.atomic_json(path, {'running': False, '\uba54\ubaa8': '\uc815\uc0c1 \uc885\ub8cc'})
        self.assertEqual({'running': False, '\uba54\ubaa8': '\uc815\uc0c1 \uc885\ub8cc'}, json.loads(path.read_text(encoding='utf-8')))
        self.assertEqual([path], list(self.root.iterdir()))

    def test_failed_replace_keeps_old_status_and_cleans_temporary(self):
        path = self.root / 'ready.json'
        peerd.atomic_json(path, {'height': 1})
        with patch.object(peerd.os, 'replace', side_effect=OSError('storage failure')):
            with self.assertRaises(OSError):
                peerd.atomic_json(path, {'height': 2})
        self.assertEqual({'height': 1}, json.loads(path.read_text(encoding='utf-8')))
        self.assertEqual([path], list(self.root.iterdir()))

    def test_windows_reader_conflict_retries_with_bounded_budget(self):
        path = self.root / 'ready.json'
        actual = peerd.os.replace
        calls = []
        def intermittent(source, destination):
            calls.append(1)
            if len(calls) == 1:
                raise PermissionError('reader holds old status')
            actual(source, destination)
        with patch.object(peerd.os, 'replace', side_effect=intermittent), patch.object(peerd.time, 'sleep'):
            peerd.atomic_json(path, {'height': 3})
        self.assertEqual(2, len(calls))
        with patch.object(peerd.os, 'replace', side_effect=PermissionError('permanent')) as replacement, patch.object(peerd.time, 'sleep'):
            with self.assertRaises(PermissionError):
                peerd.atomic_json(path, {'height': 4})
        self.assertEqual(5, replacement.call_count)
        self.assertEqual({'height': 3}, json.loads(path.read_text(encoding='utf-8')))

    def test_cli_rejects_reserved_ready_path_before_opening_database(self):
        self.database.write_bytes(b'original bytes')
        error = StringIO()
        with patch.object(peerd, 'PeerNode') as constructor, redirect_stderr(error):
            code = peerd.main(['--database', str(self.database), '--ready-file', str(self.database)])
        self.assertEqual(2, code)
        constructor.assert_not_called()
        self.assertEqual(b'original bytes', self.database.read_bytes())
        self.assertEqual('ValueError', json.loads(error.getvalue())['error'])

    def test_cli_rejects_cache_sidecars_before_opening_database(self):
        self.database.write_bytes(b'original database')
        for suffix in ('.peers.json', '.peers.json.tmp'):
            cache = Path(str(self.database) + suffix)
            cache.write_bytes(b'original cache')
            for option in ('--ready-file', '--stop-file', '--rpc-token-file'):
                arguments = ['--database', str(self.database), option, str(cache)]
                if option == '--rpc-token-file':
                    arguments.append('--rpc')
                with self.subTest(suffix=suffix, option=option), patch.object(peerd, 'PeerNode') as constructor, redirect_stderr(StringIO()):
                    self.assertEqual(2, peerd.main(arguments))
                constructor.assert_not_called()
                self.assertEqual(b'original cache', cache.read_bytes())
                self.assertEqual(b'original database', self.database.read_bytes())

    def test_cli_invalid_advertisement_rejected_before_database_open(self):
        with patch.object(peerd, 'PeerNode') as constructor, redirect_stderr(StringIO()):
            code = peerd.main(['--database', str(self.database), '--advertise', '8.8.8.8:18444'])
        self.assertEqual(2, code)
        constructor.assert_not_called()
        self.assertFalse(self.database.exists())


class FakeNode:
    instance = None
    fail_second_status = False

    def __init__(self, *args, **kwargs):
        type(self).instance = self
        self.address = ('127.0.0.1', 12345)
        self.calls = 0
        self.stopped = False
        self.constructor_options = kwargs

    async def start(self):
        return self

    async def stop(self):
        self.stopped = True

    def info(self):
        self.calls += 1
        if self.fail_second_status and self.calls > 1:
            raise RuntimeError('injected status failure')
        return {'height': 0, 'tip': '0' * 64, 'mempool': 0}


class DaemonLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='sumuww-daemon-status-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.options = argparse.Namespace(database=self.root / 'db.sqlite', listen='127.0.0.1:0', peer=[], poll_interval=.01, timeout=1, max_peers=8, ready_file=self.root / 'ready.json', stop_file=self.root / 'stop')
        FakeNode.fail_second_status = False

    async def test_exception_marks_last_status_stopped_and_closes_node(self):
        FakeNode.fail_second_status = True
        with patch.object(peerd, 'PeerNode', FakeNode), patch('builtins.print'):
            with self.assertRaises(RuntimeError):
                await peerd.serve(self.options)
        self.assertTrue(FakeNode.instance.stopped)
        self.assertFalse(json.loads(self.options.ready_file.read_text(encoding='utf-8'))['running'])

    async def test_cancellation_marks_status_stopped_and_closes_node(self):
        with patch.object(peerd, 'PeerNode', FakeNode), patch('builtins.print'):
            task = asyncio.create_task(peerd.serve(self.options))
            for _ in range(100):
                if self.options.ready_file.exists():
                    break
                await asyncio.sleep(.001)
            self.assertTrue(self.options.ready_file.exists())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(FakeNode.instance.stopped)
        self.assertFalse(json.loads(self.options.ready_file.read_text(encoding='utf-8'))['running'])

    async def test_stop_file_ends_daemon_cleanly(self):
        self.options.stop_file.write_text('stop\n', encoding='utf-8')
        with patch.object(peerd, 'PeerNode', FakeNode), patch('builtins.print'):
            await peerd.serve(self.options)
        self.assertTrue(FakeNode.instance.stopped)
        self.assertFalse(json.loads(self.options.ready_file.read_text(encoding='utf-8'))['running'])

    async def test_explicit_public_contact_is_passed_to_peer_node(self):
        self.options.listen = '0.0.0.0:18444'
        self.options.allow_internet = True
        self.options.advertise = '8.8.8.8:18444'
        self.options.stop_file.write_text('stop\n', encoding='utf-8')
        with patch.object(peerd, 'PeerNode', FakeNode), patch('builtins.print'):
            await peerd.serve(self.options)
        self.assertEqual(('8.8.8.8', 18444), FakeNode.instance.constructor_options['advertised_endpoint'])

    async def test_omitted_public_contact_keeps_existing_daemon_behavior(self):
        self.options.stop_file.write_text('stop\n', encoding='utf-8')
        with patch.object(peerd, 'PeerNode', FakeNode), patch('builtins.print'):
            await peerd.serve(self.options)
        self.assertIsNone(FakeNode.instance.constructor_options['advertised_endpoint'])
