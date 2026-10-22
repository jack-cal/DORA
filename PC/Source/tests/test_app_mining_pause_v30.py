"""Mining lifecycle regression using fresh actor paths, never user data.

Main-profile readiness and hash workers in these unit tests are synthetic:
they make zero main blocks or coins. Ordinary TCP and actual regtest block
integration are exercised separately by the release's bounded probes.
"""

from concurrent.futures import Future
import gc
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from coincurve import PrivateKey

from sumuww.app_service import AppService
from sumuww.keystore import WalletKey
from sumuww.profiles import SUMUWW


def eventually(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError('Owned fixture condition did not become true')
        time.sleep(.01)


class MiningPauseLifecycleTests(unittest.TestCase):
    def setUp(self):
        # Destroyed Tk reference cycles from earlier UI tests must be collected
        # on the main thread, before a fresh actor/executor can trigger GC.
        gc.collect()
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-v30-pause-lifecycle-')
        self.directory = Path(self.temporary.name)
        self.ready = threading.Event()
        self.ready.set()
        self.service = AppService(self.directory, network=SUMUWW, listen='127.0.0.1:0',
                                  peers=[], allow_internet=False, allow_lan=False)
        make_node = self.service._make_node

        def fixture_node(settings):
            node = make_node(settings)
            synchronization = node.synchronization_info

            def fixture_synchronization():
                result = synchronization()
                result['mining_ready'] = self.ready.is_set()
                return result
            node.synchronization_info = fixture_synchronization
            return node
        self.service._make_node = fixture_node
        self.service.start().result(timeout=10)
        self.fixture_key = WalletKey(PrivateKey((1).to_bytes(32, 'big')), SUMUWW)
        with patch('sumuww.app_service.keystore_create', return_value=self.fixture_key):
            self.service.create_wallet('owned-fixture.json', 'public test fixture').result(timeout=5)
        self.active = self.maximum = self.calls = 0
        self.worker_lock = threading.Lock()
        self.accept = threading.Event()

    def tearDown(self):
        self.service.stop().result(timeout=10)
        self.temporary.cleanup()

    def worker(self, database, network, script, interruption):
        self.assertEqual(SUMUWW, network)
        self.assertEqual(self.fixture_key.script_pubkey, script)
        with self.worker_lock:
            self.calls += 1
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        try:
            while not interruption.wait(.01):
                if self.accept.is_set():
                    return b'\x03' * 32  # synthetic accepted-result contract only
            return None
        finally:
            with self.worker_lock:
                self.active -= 1

    def waiting(self):
        self.ready.clear()
        eventually(lambda: self.service.status().result(timeout=5)['mining']['state'] == 'waiting')
        eventually(lambda: self.active == 0)

    def test_repeated_pauses_preserve_future_reservation_and_single_worker(self):
        with patch('sumuww.app_service._mine_block', self.worker):
            future = self.service.mine_one()
            eventually(lambda: self.calls == 1)
            for expected_calls in (1, 2, 3):
                self.waiting()
                self.assertFalse(future.done())
                snapshot = self.service.status().result(timeout=5)
                self.assertEqual('network', snapshot['mining']['wait_reason'])
                self.assertTrue(snapshot['mining']['reserved'])
                self.assertFalse(self.service._mining_cancel.is_set())
                with self.assertRaisesRegex(RuntimeError, 'already running'):
                    self.service.mine_one().result(timeout=2)
                self.ready.set()
                eventually(lambda: self.calls == expected_calls + 1)
            self.accept.set()
            result = future.result(timeout=5)
        self.assertFalse(result['cancelled'])
        self.assertIsNone(result['cancel_reason'])
        self.assertEqual(3, result['network_pauses'])
        self.assertIn('block_hash', result)
        self.assertEqual(1, self.maximum)
        self.assertEqual(0, self.service.status().result(timeout=5)['node']['height'])

    def test_user_stop_while_waiting_prevents_recovery_restart(self):
        with patch('sumuww.app_service._mine_block', self.worker):
            future = self.service.mine_one()
            eventually(lambda: self.active == 1)
            self.waiting()
            self.service.cancel_mining()
            result = future.result(timeout=5)
            self.ready.set()
            time.sleep(.25)
        self.assertTrue(result['cancelled'])
        self.assertEqual('user_stop', result['cancel_reason'])
        self.assertNotIn('block_hash', result)
        self.assertEqual(1, self.calls)
        self.assertFalse(self.service.status().result(timeout=5)['mining']['reserved'])

    def test_shutdown_while_waiting_joins_worker_and_never_restarts(self):
        with patch('sumuww.app_service._mine_block', self.worker):
            future = self.service.mine_one()
            eventually(lambda: self.active == 1)
            self.waiting()
            self.service.stop().result(timeout=5)
            result = future.result(timeout=5)
            self.ready.set()
            time.sleep(.15)
        self.assertTrue(result['cancelled'])
        self.assertEqual('shutdown', result['cancel_reason'])
        self.assertEqual((1, 0), (self.calls, self.active))

    def test_wallet_lock_while_waiting_is_terminal_and_retains_identity(self):
        with patch('sumuww.app_service._mine_block', self.worker):
            future = self.service.mine_one()
            eventually(lambda: self.active == 1)
            self.waiting()
            wallet = self.service.lock_wallet().result(timeout=5)
            result = future.result(timeout=5)
            self.ready.set()
            time.sleep(.15)
        self.assertFalse(wallet['unlocked'])
        self.assertEqual(self.fixture_key.address, wallet['address'])
        self.assertTrue(result['cancelled'])
        self.assertEqual('wallet_change', result['cancel_reason'])
        self.assertEqual((1, 0), (self.calls, self.active))

    def test_wallet_selection_joins_active_worker_before_replacing_identity(self):
        replacement = WalletKey(PrivateKey((2).to_bytes(32, 'big')), SUMUWW)
        with patch('sumuww.app_service._mine_block', self.worker):
            future = self.service.mine_one()
            eventually(lambda: self.active == 1)
            with patch('sumuww.app_service.keystore_create', return_value=replacement):
                selected = self.service.create_wallet('other-owned-fixture.json',
                                                       'public test fixture').result(timeout=5)
            result = future.result(timeout=5)
            time.sleep(.15)
        self.assertEqual(replacement.address, selected['address'])
        self.assertTrue(result['cancelled'])
        self.assertEqual('wallet_change', result['cancel_reason'])
        self.assertNotIn('block_hash', result)
        self.assertEqual((1, 0), (self.calls, self.active))

    def test_worker_without_accepted_block_is_error_and_releases_reservation(self):
        with patch('sumuww.app_service._mine_block', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'without an accepted block'):
                self.service.mine_one().result(timeout=5)
        self.assertFalse(self.service.status().result(timeout=5)['mining']['reserved'])
        self.assertEqual(0, self.service.status().result(timeout=5)['node']['height'])

    def test_initial_offline_guard_does_not_dispatch_or_wait(self):
        self.ready.clear()
        with patch('sumuww.app_service._mine_block') as worker:
            with self.assertRaisesRegex(RuntimeError, 'Connect and synchronize'):
                self.service.mine_one().result(timeout=5)
            worker.assert_not_called()
        self.assertFalse(self.service.status().result(timeout=5)['mining']['reserved'])


class MiningPauseGuiTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from sumuww.app import SumuwwApp
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-v30-pause-ui-')
        self.directory = Path(self.temporary.name)
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.temporary.cleanup()
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.root.update_idletasks()
        self.status = {'node': {'height': 17, 'peers': 1, 'mining_ready': True,
                               'listen': {'host': '127.0.0.1', 'port': 12345}},
                       'wallet': {'address': 'dora1qpublicfixture', 'path': 'fixture.json',
                                  'unlocked': True},
                       'mining': {'state': 'running', 'reserved': True}}
        self.mines = 0

        def pending_mine():
            self.mines += 1
            return Future()
        self.service = SimpleNamespace(directory=self.directory, network=SUMUWW,
            start=lambda: Future(), status=lambda: Future(), mine_one=pending_mine,
            cancel_mining=lambda: Future())
        self.app = SumuwwApp(self.root, self.service, language='en',
                           language_path=self.directory / 'language.json')
        self.app._started = True
        self.app._apply_status(self.status)
        self.app._mining = True
        self.app._mine_inflight = True
        self.app._mine_completed, self.app._mine_target = 17, 100
        self.app.mine_progress.configure(maximum=100, value=17)

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app._finish_close()
            del self.app
        if hasattr(self, 'root'):
            del self.root
        gc.collect()
        self.temporary.cleanup()

    def test_initial_guard_race_preserves_batch_until_fresh_ready_status(self):
        with patch('sumuww.app.messagebox.showerror') as popup:
            self.app._mine_failed(RuntimeError('Connect and synchronize with a peer before SUMUWW mining'))
            popup.assert_not_called()
        self.assertTrue(self.app._mining_waiting)
        self.assertFalse(self.app._mine_inflight)
        self.assertEqual((17, 100), (self.app._mine_completed, self.app._mine_target))
        self.app._apply_status(self.status)
        time.sleep(.025)
        self.root.update()
        self.assertEqual(1, self.mines)
        self.assertTrue(self.app._mine_inflight)

    def test_empty_worker_result_never_increments_completed_blocks(self):
        with patch('sumuww.app.messagebox.showerror') as popup:
            self.app._mine_done({'cancelled': False, 'node': self.status['node']})
            self.assertTrue(popup.called)
        self.assertEqual(17, self.app._mine_completed)
        self.assertFalse(self.app._mining)
        self.assertEqual(17, float(self.app.mine_progress['value']))

    def test_stop_between_blocks_cancels_queued_resumption(self):
        self.app._mine_inflight = False
        self.app._wait_for_mining_sync()
        self.app._apply_status(self.status)
        self.app._stop_mining()
        time.sleep(.025)
        self.root.update()
        self.assertEqual(0, self.mines)
        self.assertFalse(self.app._mining)
        self.assertFalse(self.app._mining_waiting)
        self.assertEqual((17, 100), (self.app._mine_completed, self.app._mine_target))


if __name__ == '__main__':
    unittest.main()
