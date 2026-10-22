"""Bootstrap fixture permissions and input-path isolation before daemon startup."""
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sumuww import peerd
from sumuww.profiles import REGTEST
from tests.test_peerd import FakeNode


class BootstrapCliPermissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-bootstrap-cli-options-')
        self.directory = Path(self.temporary.name)
        self.database = self.directory / 'node.sqlite'
        self.manifest = self.directory / 'fixture-bootstrap.json'

    def tearDown(self):
        self.temporary.cleanup()

    def rejected(self, arguments):
        with patch.object(peerd, 'PeerNode') as constructor, redirect_stderr(StringIO()):
            code = peerd.main(['--database', str(self.database), *arguments])
        self.assertEqual(2, code)
        constructor.assert_not_called()
        self.assertFalse(self.database.exists())

    def test_main_profile_never_accepts_loopback_bootstrap_fixture_scope(self):
        self.rejected(['--network', 'dora', '--allow-internet',
                       '--bootstrap-scope', 'loopback'])

    def test_explicit_bootstrap_manifest_requires_internet_optin(self):
        self.rejected(['--network', 'regtest', '--bootstrap-manifest', str(self.manifest)])

    def test_manifest_input_cannot_alias_database_state_or_auxiliary_outputs(self):
        for suffix in ('', '-wal', '-shm', '-journal', '.peers.json', '.peers.json.tmp'):
            with self.subTest(suffix=suffix):
                self.rejected(['--network', 'regtest', '--allow-internet',
                               '--bootstrap-manifest', str(Path(str(self.database) + suffix))])
        for argument in ('--ready-file', '--stop-file', '--rpc-token-file'):
            arguments = ['--network', 'regtest', '--allow-internet',
                         '--bootstrap-manifest', str(self.manifest), argument, str(self.manifest)]
            if argument == '--rpc-token-file':
                arguments.append('--rpc')
            with self.subTest(argument=argument):
                self.rejected(arguments)


class BootstrapDaemonOptionTests(unittest.IsolatedAsyncioTestCase):
    async def test_nonmain_explicit_loopback_manifest_is_separate_from_manual_peers(self):
        with tempfile.TemporaryDirectory(prefix='sumuww-bootstrap-daemon-options-') as temporary:
            directory = Path(temporary)
            manifest = directory / 'fixture-bootstrap.json'
            manifest.write_text(json.dumps({
                'schema_version': 2, 'network': 'regtest', 'genesis': REGTEST.genesis.block_hash().hex(),
                'dns_seeds': [], 'fallback_peers': [{'host': '127.0.0.1', 'port': 18444}],
            }), encoding='utf-8')
            stop = directory / 'stop'
            stop.write_text('stop\n', encoding='utf-8')
            options = SimpleNamespace(database=directory / 'node.sqlite', network='regtest',
                                      allow_internet=True, allow_lan=False, listen='127.0.0.1:0',
                                      peer=[], poll_interval=.1, timeout=1, max_peers=8,
                                      bootstrap_manifest=manifest, bootstrap_scope='loopback',
                                      ready_file=None, stop_file=stop, rpc=False, advertise=None)
            with patch.object(peerd, 'PeerNode', FakeNode), patch('builtins.print'):
                await peerd.serve(options)
            self.assertEqual((), FakeNode.instance.constructor_options['peers'])
            self.assertEqual((('127.0.0.1', 18444),), FakeNode.instance.constructor_options['bootstrap_peers'])
            self.assertEqual('loopback', FakeNode.instance.constructor_options['bootstrap_scope'])
            self.assertEqual('loopback', FakeNode.instance.constructor_options['discovery_scope'])
            self.assertTrue(FakeNode.instance.stopped)
            self.assertFalse((directory / 'node.sqlite').exists())


if __name__ == '__main__':
    unittest.main()
