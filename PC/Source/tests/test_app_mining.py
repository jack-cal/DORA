"""The GUI mining worker renews work after another SQLite writer advances tip."""

from pathlib import Path
import asyncio
import tempfile
import threading
import unittest
from unittest.mock import patch

from sumuww.app_service import _mine_block
from sumuww.app_service import AppService
from sumuww.chain import Chain
from sumuww.profiles import REGTEST
from sumuww.wallet import RegtestKey
from sumuww.network_settings import load_settings, save_settings
from sumuww.node_manager import probe_peer
from sumuww.peer import PeerNode


ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)


class AppMiningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-app-miner-')
        self.database = Path(self.temp.name) / 'node.sqlite'
        self.cancel = threading.Event()

    def tearDown(self):
        self.temp.cleanup()

    def test_external_tip_interrupts_search_and_renews_parent(self):
        original = Chain.make_block
        parents = []
        with Chain(self.database) as other:
            competitor = other.make_block(BOB.script_pubkey)
            def search(chain, script, **options):
                parents.append(options['parent_hash'])
                if len(parents) == 1:
                    self.assertTrue(other.accept_block(competitor))
                    self.assertTrue(options['mining_cancel']())
                    raise RuntimeError('Mining cancelled')
                return original(chain, script, **options)
            with patch.object(Chain, 'make_block', search):
                result = _mine_block(self.database, REGTEST, ALICE.script_pubkey, self.cancel)
            self.assertEqual(competitor.block_hash(), parents[1])
            self.assertEqual(result, other.tip_hash)
            self.assertEqual(2, other.info()['height'])

    def test_tip_race_after_search_retries_before_publishing(self):
        original = Chain.make_block
        attempts = []
        with Chain(self.database) as other:
            competitor = other.make_block(BOB.script_pubkey)
            def search(chain, script, **options):
                block = original(chain, script, **options)
                attempts.append(block)
                if len(attempts) == 1:
                    other.accept_block(competitor)
                return block
            with patch.object(Chain, 'make_block', search):
                result = _mine_block(self.database, REGTEST, ALICE.script_pubkey, self.cancel)
            self.assertEqual(2, len(attempts))
            self.assertEqual(competitor.block_hash(), attempts[1].header.previous_hash)
            self.assertEqual(result, other.tip_hash)

    def test_inactive_acceptance_is_not_reported_as_a_reward(self):
        original = Chain.accept_block
        attempts = []
        def accept(chain, block):
            attempts.append(block)
            if len(attempts) == 1:
                return False
            return original(chain, block)
        with patch.object(Chain, 'accept_block', accept):
            result = _mine_block(self.database, REGTEST, ALICE.script_pubkey, self.cancel)
        self.assertEqual(2, len(attempts))
        with Chain(self.database) as chain:
            self.assertEqual(chain.tip_hash, result)
            self.assertEqual(1, chain.info()['height'])

    def test_cancellation_exits_without_claiming_reward(self):
        def search(chain, script, **options):
            self.cancel.set()
            self.assertTrue(options['mining_cancel']())
            raise RuntimeError('Mining cancelled')
        with patch.object(Chain, 'make_block', search):
            self.assertIsNone(_mine_block(self.database, REGTEST, ALICE.script_pubkey, self.cancel))
        with Chain(self.database) as chain:
            self.assertEqual(0, chain.info()['height'])

    def test_unexpected_mining_error_is_not_swallowed(self):
        with patch.object(Chain, 'make_block', side_effect=RuntimeError('unexpected failure')):
            with self.assertRaisesRegex(RuntimeError, 'unexpected failure'):
                _mine_block(self.database, REGTEST, ALICE.script_pubkey, self.cancel)

    def test_gui_bootstrap_only_applies_to_missing_preferences(self):
        directory = Path(self.temp.name)
        self.assertFalse(load_settings(directory)['allow_internet'])
        fresh = load_settings(directory, bootstrap=True)
        self.assertTrue(fresh['allow_internet'])
        self.assertEqual([], fresh['peers'])
        existing = load_settings(directory)
        save_settings(directory, existing)
        self.assertEqual(existing, load_settings(directory, bootstrap=True))
        configured = {'listen': '127.0.0.1:0', 'peers': ['127.0.0.1:18444'],
                      'allow_internet': True, 'allow_lan': False}
        save_settings(directory, configured)
        restored = load_settings(directory, bootstrap=True)
        self.assertEqual(['127.0.0.1:18444'], restored['peers'])
        self.assertTrue(restored['allow_internet'])


class MonitorMiningInteractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_delayed_on_demand_query_does_not_cancel_normal_main_profile_miner(self):
        # Real ordinary peers synchronize the registered main profile. Only
        # hash computation waits synthetically: no main coin or block is made.
        with tempfile.TemporaryDirectory(prefix='sumuww-query-mining-regression-') as temporary:
            directory = Path(temporary)
            ordinary = PeerNode(directory / 'ordinary.sqlite', network='dora',
                                host='127.0.0.1', port=0, poll_interval=.03,
                                timeout=2, discover_peers=False)
            await ordinary.start()
            actor = AppService(directory / 'app', network='dora', listen='127.0.0.1:0',
                               peers=[f'{ordinary.address[0]}:{ordinary.address[1]}'])
            worker_started = threading.Event()
            mined = None
            try:
                await asyncio.wrap_future(actor.start())
                for _ in range(100):
                    state = await asyncio.wrap_future(actor.status())
                    if state['node']['mining_ready']:
                        break
                    await asyncio.sleep(.02)
                self.assertTrue(state['node']['mining_ready'])
                await asyncio.wrap_future(actor.create_wallet('wallet.json', 'isolated test password'))

                def waiting_worker(database, network, script, cancellation):
                    worker_started.set()
                    cancellation.wait(10)
                    return None

                original_send = PeerNode._send

                async def delayed_ack(node, session, command, payload=b''):
                    if command == 'verack' and session.outgoing is None:
                        # Simulate an ordinary 200ms identity-response delay,
                        # which exceeds the 100ms mining guard poll interval.
                        await asyncio.sleep(.2)
                    return await original_send(node, session, command, payload)

                with patch('sumuww.app_service._mine_block', waiting_worker), patch.object(PeerNode, '_send', delayed_ack):
                    mined = actor.mine_one()
                    self.assertTrue(await asyncio.to_thread(worker_started.wait, 2))
                    endpoint = f'{state["node"]["listen"]["host"]}:{state["node"]["listen"]["port"]}'
                    checks = await asyncio.gather(*(probe_peer(endpoint, network='dora', timeout=2) for _ in range(3)))
                    self.assertEqual(['reachable'] * 3, [item['status'] for item in checks])
                    await asyncio.sleep(.15)
                    self.assertFalse(mined.done(), 'A node query must not cancel ordinary mining')
                    after = await asyncio.wrap_future(actor.status())
                    self.assertTrue(after['node']['mining_ready'])
                    self.assertEqual(1, after['node']['synchronized_peers'])
                    self.assertEqual(0, after['node']['height'])
                    actor.cancel_mining()
                    self.assertTrue((await asyncio.wrap_future(mined))['cancelled'])
            finally:
                actor.cancel_mining()
                await asyncio.wrap_future(actor.stop())
                await ordinary.stop()


if __name__ == '__main__':
    unittest.main()
