"""Owned Tk recovery transitions preserve an active mining request and inputs."""
from concurrent.futures import Future
import unittest

from tests import test_app_discovery_v33 as prior_fixture
from sumuww.i18n import LANGUAGE_CODES

LISTENER = 'Node listener unavailable · Restoring connections…'
RECOVERY = 'Mining waiting for node recovery · {0}/{1} blocks completed'
COUNTDOWN = 'Mining waiting for nodes · {0}/{1} blocks completed · Next search in {2}s'
SEARCHING = 'Mining waiting for nodes · {0}/{1} blocks completed · Searching…'


class RecoveryStatusTests(unittest.TestCase):
    setUp = prior_fixture.DiscoveryStatusTests.setUp
    tearDown = prior_fixture.DiscoveryStatusTests.tearDown

    def batch(self):
        self.app._mining = self.app._mine_inflight = True
        self.app._mine_completed, self.app._mine_target = 46, 10000
        self.app.mine_progress.configure(maximum=10000, value=46)
        self.app.send_address.set('dora1qtypedpublicfixture')
        self.app.send_amount.set('1.25000000')
        self.future = Future()
        self.app._watch(self.future, None)

    def apply(self, *, seconds=15, round_in_progress=False, peers=0, ready=False,
              listener_active=True, state='active', network='dora'):
        self.app.network_name = network
        self.app._apply_status({'node': {'height': 2090, 'peers': peers, 'mining_ready': ready,
            'listener_active': listener_active,
            'listen': {'host': '127.0.0.1', 'port': 12345},
            'dht_discovery': {'state': state, 'round_in_progress': round_in_progress,
                              'next_query_seconds': seconds}},
            'wallet': self.wallet, 'transactions': []})

    def preserved(self):
        self.assertEqual((46, 10000), (self.app._mine_completed, self.app._mine_target))
        self.assertEqual(46, self.app.mine_progress['value'])
        self.assertTrue(self.app._mining)
        self.assertTrue(self.app._mine_inflight)
        self.assertFalse(self.future.done())
        self.assertEqual('dora1qtypedpublicfixture', self.app.send_address.get())
        self.assertEqual('1.25000000', self.app.send_amount.get())
        self.assertEqual(self.wallet['total_smw'], self.app._wallet['total_smw'])

    def test_active_batch_countdown_refresh_preserves_future_and_work(self):
        self.batch()
        for seconds in (15, 12, 1):
            self.apply(seconds=seconds)
            self.assertEqual(self.app.translator.render(COUNTDOWN, 46, 10000, seconds),
                             self.app.mine_text.get())
            self.preserved()

    def test_search_round_and_invalid_counter_do_not_promise_a_deadline(self):
        self.batch()
        self.apply(seconds=15, round_in_progress=True)
        self.assertEqual(self.app.translator.render(SEARCHING, 46, 10000), self.app.mine_text.get())
        for seconds in (0, -1, None, True, '15'):
            self.apply(seconds=seconds)
            self.assertEqual(self.app.translator.render(SEARCHING, 46, 10000), self.app.mine_text.get())
        self.preserved()

    def test_listener_failure_then_recovery_resumes_same_pending_batch(self):
        self.batch()
        self.apply(listener_active=False, peers=0, ready=False)
        self.assertFalse(self.app._mining_allowed())
        self.assertTrue(self.app._mining_waiting)
        self.assertEqual(self.app.translator.render(LISTENER), self.app.sync_text.get())
        self.assertEqual(self.app.translator.render(RECOVERY, 46, 10000), self.app.mine_text.get())
        self.preserved()
        self.apply(listener_active=True, peers=1, ready=True)
        self.assertTrue(self.app._mining_allowed())
        self.assertFalse(self.app._mining_waiting)
        self.assertEqual(self.app.translator.render('Mining · {0}/{1} blocks completed', 46, 10000),
                         self.app.mine_text.get())
        self.preserved()

    def test_synced_outbound_connection_keeps_mining_during_listener_recovery(self):
        self.batch()
        self.apply(listener_active=False, peers=1, ready=True)
        self.assertTrue(self.app._mining_allowed())
        self.assertFalse(self.app._mining_waiting)
        self.preserved()

    def test_eleven_languages_render_recovery_and_batch_counter(self):
        self.batch()
        for language in LANGUAGE_CODES:
            with self.subTest(language=language):
                self.assertTrue(self.app.set_language(language))
                self.apply(seconds=12)
                catalog = self.app.translator.catalog(language)
                self.assertEqual(catalog[COUNTDOWN].format(46, 10000, 12), self.app.mine_text.get())
                self.apply(listener_active=False)
                self.assertEqual(catalog[RECOVERY].format(46, 10000), self.app.mine_text.get())
                self.assertEqual(catalog[LISTENER], self.app.sync_text.get())
                self.preserved()


if __name__ == '__main__':
    unittest.main()
