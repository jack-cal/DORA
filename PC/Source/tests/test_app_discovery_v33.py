"""Owned Tk status tests with synthetic public snapshots, no node/user data."""
from concurrent.futures import Future
import gc
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from sumuww.i18n import LANGUAGE_CODES
from sumuww.profiles import SUMUWW


COUNTDOWN = 'No connected nodes · Next automatic search in {0}s'
SEARCHING = 'Searching the distributed network for SMW nodes…'


class DiscoveryStatusTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from sumuww.app import SumuwwApp
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-v33-discovery-ui-')
        self.directory = Path(self.temporary.name)
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.temporary.cleanup()
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.root.update_idletasks()
        self.service = SimpleNamespace(directory=self.directory, network=SUMUWW,
                                       start=lambda: Future(), status=lambda: Future())
        self.app = SumuwwApp(self.root, self.service, language='en',
                           language_path=self.directory / 'language.json')
        self.app._started = True
        self.wallet = {'address': 'dora1qpublicfixture', 'path': 'owned-public-fixture.json',
                       'unlocked': False, 'total_smw': '150.00000000',
                       'spendable_smw': '50.00000000', 'available_smw': '50.00000000',
                       'pending_smw': '0.00000000', 'immature_smw': '100.00000000'}

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app._finish_close()
            del self.app
        if hasattr(self, 'root'):
            del self.root
        gc.collect()
        self.temporary.cleanup()

    def apply(self, *, seconds=15, round_in_progress=False, peers=0,
              ready=False, state='active', network='dora'):
        self.app.network_name = network
        self.app._apply_status({'node': {'height': 100, 'peers': peers, 'mining_ready': ready,
            'listen': {'host': '127.0.0.1', 'port': 12345},
            'dht_discovery': {'state': state, 'round_in_progress': round_in_progress,
                              'next_query_seconds': seconds}},
            'wallet': self.wallet,
            'connection': {'allow_internet': True, 'allow_lan': False, 'auto_address': True,
                           'listen': '127.0.0.1:0', 'peers': []},
            'transactions': []})

    def test_retry_countdown_refreshes_without_changing_wallet_or_inputs(self):
        self.app.send_address.set('dora1qtypedpublicfixture')
        self.app.send_amount.set('1.25000000')
        for seconds in (15, 14, 1):
            with self.subTest(seconds=seconds):
                self.apply(seconds=seconds)
                self.assertEqual(self.app.translator.render(COUNTDOWN, seconds),
                                 self.app.sync_text.get())
                self.assertEqual(self.wallet['address'], self.app.address_text.get())
                self.assertEqual(self.wallet['total_smw'], self.app._wallet['total_smw'])
                self.assertEqual('dora1qtypedpublicfixture', self.app.send_address.get())
                self.assertEqual('1.25000000', self.app.send_amount.get())

    def test_actual_lookup_round_has_searching_text_even_with_old_positive_countdown(self):
        self.apply(seconds=15, round_in_progress=True)
        self.assertEqual(self.app.translator.render(SEARCHING), self.app.sync_text.get())

    def test_zero_or_invalid_counter_does_not_claim_a_retry_deadline(self):
        for seconds in (0, -1, None, '15', 15.0, True, False):
            with self.subTest(seconds=seconds):
                self.apply(seconds=seconds)
                self.assertEqual(self.app.translator.render(SEARCHING), self.app.sync_text.get())

    def test_connected_sync_and_ready_take_priority_over_discovery_counter(self):
        self.apply(peers=2, ready=False)
        self.assertEqual(self.app.translator.render('Synchronizing with connected nodes · Mining waiting'),
                         self.app.sync_text.get())
        self.apply(peers=2, ready=True)
        self.assertEqual(self.app.translator.render('Synchronized with connected nodes · Mining ready'),
                         self.app.sync_text.get())

    def test_unavailable_or_disabled_dht_does_not_show_active_countdown(self):
        self.apply(state='unavailable')
        self.assertEqual(self.app.translator.render('Distributed node search is unavailable. Retrying…'),
                         self.app.sync_text.get())
        self.apply(state='disabled')
        self.assertEqual(self.app.translator.render('Waiting for peers · Mining starts after synchronization'),
                         self.app.sync_text.get())
        self.apply(network='regtest')
        self.assertEqual(self.app.translator.render('Test network · Offline mining is available.'),
                         self.app.sync_text.get())

    def test_all_eleven_languages_keep_counter_and_existing_waiting_batch(self):
        self.app._mining = self.app._mine_inflight = True
        self.app._mine_target, self.app._mine_completed = 100, 17
        self.app.mine_progress.configure(maximum=100, value=17)
        self.app.send_address.set('dora1qtypedpublicfixture')
        pending = Future()
        self.app._watch(pending, None)
        self.apply(seconds=12)
        futures = list(self.app._pending)
        for language in LANGUAGE_CODES:
            with self.subTest(language=language):
                self.assertTrue(self.app.set_language(language))
                self.assertEqual(self.app.translator.catalog(language)[COUNTDOWN].format(12),
                                 self.app.sync_text.get())
                self.assertNotIn('{0}', self.app.sync_text.get())
                self.assertEqual((17, 100), (self.app._mine_completed, self.app._mine_target))
                self.assertTrue(self.app._mining_waiting)
                self.assertTrue(self.app._mine_inflight)
                self.assertEqual(futures, self.app._pending)
                self.assertEqual(self.wallet['address'], self.app.address_text.get())
                self.assertEqual('dora1qtypedpublicfixture', self.app.send_address.get())


if __name__ == '__main__':
    unittest.main()
