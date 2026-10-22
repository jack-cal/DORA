"""Real daemon/client lifecycle and credential/path isolation regressions."""

from contextlib import redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

from sumuww import peerd, rpc_client


class RpcClientDaemonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-rpc-client-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.ready = self.root / 'ready.json'
        self.stop = self.root / 'stop'
        self.token = self.root / 'rpc-token'
        source = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE='1')
        self.process = subprocess.Popen([
            sys.executable, str(source / 'sumuww_node_entry.py'), 'peer',
            '--network', 'regtest', '--database', str(self.root / 'node.sqlite'),
            '--rpc', '--rpc-port', '0', '--rpc-token-file', str(self.token),
            '--ready-file', str(self.ready), '--stop-file', str(self.stop),
            '--poll-interval', '0.1'], env=environment, cwd=self.root,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.addCleanup(self.shutdown)
        # Status publication can exceed Windows' pipe buffer. The daemon must
        # not stall because the fixture leaves its output unread.
        self.output_readers = []
        for stream in (self.process.stdout, self.process.stderr):
            thread = threading.Thread(target=stream.read, daemon=True)
            thread.start()
            self.output_readers.append(thread)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail('RPC daemon exited before readiness')
            try:
                self.state = json.loads(self.ready.read_text(encoding='utf-8'))
                break
            except (OSError, ValueError):
                time.sleep(0.03)
        else:
            self.fail('RPC daemon did not publish readiness')
        self.port = self.state['rpc']['listen']['port']
        self.url = f'http://127.0.0.1:{self.port}/rpc'

    def shutdown(self):
        self.stop.touch()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)
        for stream in (self.process.stdout, self.process.stderr):
            stream.close()
        for thread in self.output_readers:
            thread.join(timeout=2)

    def test_authenticated_client_observes_real_node_without_proxy_or_token_disclosure(self):
        with patch.dict(os.environ, {'HTTP_PROXY': 'http://127.0.0.1:1', 'NO_PROXY': ''}):
            self.assertEqual(0, rpc_client.call(self.url, self.token, 'getblockcount'))
        result = rpc_client.call(self.url, self.token, 'getblockchaininfo')
        self.assertEqual('regtest', result['network'])
        token = self.token.read_text().strip()
        self.assertNotIn(token, json.dumps(self.state))
        self.assertNotIn(token, json.dumps(result))
        self.assertEqual(0, self.state['height'])

    def test_wrong_token_and_unknown_method_fail_without_disclosing_credentials(self):
        wrong = self.root / 'wrong-token'
        wrong.write_text('0' * 64 + '\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'status 401'):
            rpc_client.call(self.url, wrong, 'getblockcount')
        with self.assertRaisesRegex(ValueError, 'RPC error -32601'):
            rpc_client.call(self.url, self.token, 'notamethod')

    def test_native_entry_route_and_large_parameter_file(self):
        source = Path(__file__).resolve().parents[1]
        parameters = self.root / 'params.json'
        parameters.write_text('{"height":0}', encoding='utf-8')
        output = subprocess.run([sys.executable, str(source / 'sumuww_node_entry.py'),
            'rpc', '--url', self.url, '--token-file', str(self.token),
            '--params-file', str(parameters), 'getblockhash'], cwd=self.root,
            capture_output=True, text=True, encoding='utf-8', timeout=10,
            env=dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE='1'),
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(0, output.returncode, output.stderr)
        self.assertEqual(self.state['tip'], json.loads(output.stdout))

    def test_shutdown_closes_rpc_listener_and_marks_readiness_stopped(self):
        self.stop.touch()
        self.assertEqual(0, self.process.wait(timeout=10))
        state = json.loads(self.ready.read_text(encoding='utf-8'))
        self.assertFalse(state['running'])
        with self.assertRaisesRegex(ValueError, 'Unable to reach'):
            rpc_client.call(self.url, self.token, 'getblockcount', timeout=1)


class RpcOptionsTests(unittest.TestCase):
    def test_remote_redirect_style_and_non_rpc_urls_are_rejected(self):
        for url in ('http://192.168.1.1:18443/rpc', 'http://localhost:18443/rpc',
                    'https://127.0.0.1:18443/rpc', 'http://127.0.0.1:18443/rpc?token=x',
                    'http://user:password@127.0.0.1:18443/rpc', 'http://127.0.0.1:18443/api'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                rpc_client._url(url)

    def test_rpc_token_collisions_rejected_before_database_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / 'node.sqlite'
            database.write_bytes(b'untouched')
            for suffix in ('', '-wal', '-shm', '-journal'):
                with self.subTest(suffix=suffix), patch.object(peerd, 'PeerNode') as node:
                    error = StringIO()
                    with redirect_stderr(error):
                        result = peerd.main(['--database', str(database), '--rpc',
                                             '--rpc-token-file', str(database) + suffix])
                    self.assertEqual(2, result)
                    node.assert_not_called()
                    self.assertEqual(b'untouched', database.read_bytes())
            with self.assertRaises(ValueError):
                peerd.validate_state_paths(database, root / 'same', root / 'stop', root / 'same')

    def test_rpc_options_require_explicit_enable_and_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'node.sqlite'
            for options in (['--rpc-port', '123'], ['--rpc-token-file', str(database.parent/'token')],
                            ['--rpc', '--rpc-port', '-1'], ['--rpc', '--rpc-port', '65536']):
                with self.subTest(options=options), patch.object(peerd, 'PeerNode') as node:
                    with redirect_stderr(StringIO()):
                        self.assertEqual(2, peerd.main(['--database', str(database), *options]))
                    node.assert_not_called()
                    self.assertFalse(database.exists())


if __name__ == '__main__':
    unittest.main()
