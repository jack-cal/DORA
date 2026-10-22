"""Persistent, fully verified hash-thread sessions on owned regtest fixtures."""

import gc
import inspect
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from coincurve import PrivateKey

from sumuww.app_service import AppService, _mine_block
from sumuww.chain import Chain
from sumuww.keystore import WalletKey
from sumuww.profiles import REGTEST
from sumuww.wallet import RegtestKey


ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)


def eventually(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError('Owned mining session fixture did not become ready')
        time.sleep(.01)


class MiningSessionTests(unittest.TestCase):
    def setUp(self):
        gc.collect()
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-v32-mining-session-')
        self.directory = Path(self.temporary.name)
        self.services = []
        self.allowed_stop_errors = set()
        self.verifications = []
        self.closes = []
        original_verify, original_close = Chain.verify_persisted_state, Chain.close

        def verify(chain):
            if threading.current_thread().name.startswith('sumuww-app-hash'):
                self.verifications.append((id(chain), threading.get_ident()))
            return original_verify(chain)

        def close(chain):
            original_close(chain)
            if threading.current_thread().name.startswith('sumuww-app-hash'):
                with self.assertRaises(sqlite3.ProgrammingError):
                    chain.connection.execute('SELECT 1')
                self.closes.append((id(chain), threading.get_ident()))
        self.verify_patch = patch.object(Chain, 'verify_persisted_state', verify)
        self.close_patch = patch.object(Chain, 'close', close)
        self.verify_patch.start()
        self.close_patch.start()

    def tearDown(self):
        try:
            for service in reversed(self.services):
                try:
                    service.stop().result(timeout=10)
                except RuntimeError:
                    if service not in self.allowed_stop_errors:
                        raise
        finally:
            self.close_patch.stop()
            self.verify_patch.stop()
            self.temporary.cleanup()

    def service(self, name='app'):
        service = AppService(self.directory / name, network=REGTEST,
                             listen='127.0.0.1:0', peers=[],
                             allow_internet=False, allow_lan=False)
        self.services.append(service)
        service.start().result(timeout=10)
        self.select(service, 1)
        return service

    def select(self, service, scalar):
        key = WalletKey(PrivateKey(scalar.to_bytes(32, 'big')), REGTEST)
        with patch('sumuww.app_service.keystore_create', return_value=key):
            service.create_wallet(f'owned-public-fixture-{scalar}.json',
                                  'public test fixture').result(timeout=5)

    def test_five_blocks_verify_once_on_one_thread_and_stop_closes_that_connection(self):
        service = self.service()
        executor = service._mining_executor
        for height in range(1, 6):
            result = service.mine_one().result(timeout=10)
            self.assertFalse(result['cancelled'])
            self.assertEqual(height, result['node']['height'])
        self.assertEqual(1, len(self.verifications))
        session = service._mining_session
        self.assertNotIn('_key', vars(session))
        self.assertNotIn('public_script', vars(session))
        service.stop().result(timeout=10)
        self.assertEqual(self.verifications, self.closes)
        self.assertIsNone(session._chain)
        self.assertIsNone(service._mining_executor)
        self.assertIsNone(service._mining_session)
        self.assertTrue(all(not thread.is_alive() for thread in executor._threads))

    def test_cancel_preserves_session_and_next_explicit_request_reuses_it(self):
        service = self.service()
        service.mine_one().result(timeout=10)
        started = threading.Event()
        original_make = Chain.make_block

        def wait_for_cancel(chain, script, **options):
            started.set()
            eventually(options['mining_cancel'])
            raise RuntimeError('Mining cancelled')
        with patch.object(Chain, 'make_block', wait_for_cancel):
            future = service.mine_one()
            self.assertTrue(started.wait(3))
            with self.assertRaisesRegex(RuntimeError, 'already running'):
                service.mine_one().result(timeout=2)
            service.cancel_mining()
            cancelled = future.result(timeout=5)
        self.assertTrue(cancelled['cancelled'])
        self.assertEqual('user_stop', cancelled['cancel_reason'])
        self.assertNotIn('block_hash', cancelled)
        self.assertEqual(1, service.status().result(timeout=5)['node']['height'])
        self.assertEqual(2, service.mine_one().result(timeout=10)['node']['height'])
        self.assertEqual(1, len(self.verifications))

    def test_pause_resume_uses_same_verified_chain_without_final_user_cancel(self):
        service = self.service()
        started = threading.Event()
        original_make = Chain.make_block
        attempts = []

        def paused_search(chain, script, **options):
            attempts.append((id(chain), threading.get_ident()))
            if len(attempts) == 1:
                started.set()
                eventually(options['mining_cancel'])
                raise RuntimeError('Mining cancelled')
            return original_make(chain, script, **options)
        with patch.object(Chain, 'make_block', paused_search):
            future = service.mine_one()
            self.assertTrue(started.wait(3))
            # Regtest intentionally has no public-network guard. Inject only
            # its thread-safe pause signal to exercise session reuse; actual
            # main-profile TCP guard transitions are separate release tests.
            service._mining_pause.set()
            result = future.result(timeout=10)
        self.assertFalse(result['cancelled'])
        self.assertFalse(service._mining_cancel.is_set())
        self.assertEqual(1, result['network_pauses'])
        self.assertEqual(2, len(attempts))
        self.assertEqual(attempts[0], attempts[1])
        self.assertEqual(1, len(self.verifications))
        self.assertEqual(1, result['node']['height'])

    def test_wallet_switch_changes_reward_script_without_reopening_session(self):
        service = self.service()
        first = service.mine_one().result(timeout=10)
        self.select(service, 2)
        second = service.mine_one().result(timeout=10)
        self.assertEqual((1, 2), (first['node']['height'], second['node']['height']))
        self.assertEqual(1, len(self.verifications))
        with Chain(service.database, network=REGTEST) as chain:
            block = chain.get_block(chain.tip_hash)
            self.assertEqual(BOB.script_pubkey, block.transactions[0].outputs[0].script_pubkey)
            self.assertEqual(50_00000000, chain.balance(ALICE.script_pubkey))
            self.assertEqual(50_00000000, chain.balance(BOB.script_pubkey))

    def test_external_valid_advance_and_fork_renew_same_session_parent(self):
        service = self.service()
        service.mine_one().result(timeout=10)
        with Chain(service.database, network=REGTEST) as writer:
            writer.mine(BOB.script_pubkey, 2)
            parent = writer.tip_hash
            service.mine_one().result(timeout=10)
            self.assertEqual(parent, writer.get_block(writer.tip_hash).header.previous_hash)
            branch = writer.network.genesis.block_hash()
            for index in range(5):
                block = writer.make_block(BOB.script_pubkey, parent_hash=branch,
                                          extra_nonce=200 + index)
                writer.accept_block(block)
                branch = block.block_hash()
            self.assertEqual(branch, writer.tip_hash)
            result = service.mine_one().result(timeout=10)
            self.assertEqual(6, result['node']['height'])
            self.assertEqual(branch, writer.get_block(writer.tip_hash).header.previous_hash)
            self.assertTrue(writer.verify_persisted_state())
        self.assertEqual(1, len(self.verifications))

    def test_worker_error_discards_session_and_next_request_fully_verifies(self):
        service = self.service()
        service.mine_one().result(timeout=10)
        with patch.object(Chain, 'make_block', side_effect=RuntimeError('owned worker failure')):
            with self.assertRaisesRegex(RuntimeError, 'Service operation failed'):
                service.mine_one().result(timeout=5)
        self.assertIsNone(service._mining_session._chain)
        self.assertEqual(1, len(self.closes))
        result = service.mine_one().result(timeout=10)
        self.assertEqual(2, result['node']['height'])
        self.assertEqual(2, len(self.verifications))
        executor = service._mining_executor
        service.stop().result(timeout=10)
        self.assertEqual(2, len(self.closes))
        self.assertTrue(all(not thread.is_alive() for thread in executor._threads))

    def test_startup_failure_disposes_unused_executor_and_closes_actor(self):
        service = AppService(self.directory / 'failed-start', network=REGTEST,
                             listen='127.0.0.1:0', peers=[], allow_internet=False)
        self.services.append(service)
        with patch.object(service, '_persist_network', side_effect=RuntimeError('owned startup failure')):
            with self.assertRaisesRegex(RuntimeError, 'Service operation failed'):
                service.start().result(timeout=10)
        service.stop().result(timeout=10)
        self.assertIsNone(service._mining_executor)
        self.assertIsNone(service._mining_session)
        self.assertFalse(service._thread.is_alive())

    def test_cleanup_error_still_releases_connection_and_joins_executor(self):
        service = self.service()
        service.mine_one().result(timeout=10)
        executor = service._mining_executor
        original_close = Chain.close

        def close_then_report(chain):
            original_close(chain)
            if threading.current_thread().name.startswith('sumuww-app-hash'):
                raise RuntimeError('owned cleanup failure')
        self.allowed_stop_errors.add(service)
        with patch.object(Chain, 'close', close_then_report):
            with self.assertRaisesRegex(RuntimeError, 'Service operation failed'):
                service.stop().result(timeout=10)
        self.assertIsNone(service._mining_executor)
        self.assertIsNone(service._mining_session)
        self.assertFalse(service._thread.is_alive())
        self.assertTrue(all(not thread.is_alive() for thread in executor._threads))

    def test_first_use_does_not_skip_full_persisted_state_validation(self):
        service = self.service()
        with Chain(service.database, network=REGTEST) as writer:
            writer.mine(ALICE.script_pubkey)
            writer.connection.execute('UPDATE utxos SET value=value+1')
        with self.assertRaisesRegex(RuntimeError, 'UTXO does not match'):
            service.mine_one().result(timeout=10)
        self.assertIsNone(service._mining_session._chain)
        self.assertEqual(1, len(self.verifications))

    def test_stop_during_active_search_settles_future_then_closes_and_joins(self):
        service = self.service()
        service.mine_one().result(timeout=10)
        executor = service._mining_executor
        started = threading.Event()

        def wait_for_stop(chain, script, **options):
            started.set()
            eventually(options['mining_cancel'])
            raise RuntimeError('Mining cancelled')
        with patch.object(Chain, 'make_block', wait_for_stop):
            mined = service.mine_one()
            self.assertTrue(started.wait(3))
            service.stop().result(timeout=10)
            result = mined.result(timeout=2)
        self.assertTrue(result['cancelled'])
        self.assertEqual('shutdown', result['cancel_reason'])
        self.assertNotIn('block_hash', result)
        self.assertEqual(self.verifications, self.closes)
        self.assertFalse(service._thread.is_alive())
        self.assertTrue(all(not thread.is_alive() for thread in executor._threads))

    def test_active_wallet_switch_stops_old_script_then_reuses_session_for_new_reward(self):
        service = self.service()
        service.mine_one().result(timeout=10)
        started = threading.Event()

        def wait_for_wallet_change(chain, script, **options):
            self.assertEqual(ALICE.script_pubkey, script)
            started.set()
            eventually(options['mining_cancel'])
            raise RuntimeError('Mining cancelled')
        with patch.object(Chain, 'make_block', wait_for_wallet_change):
            mined = service.mine_one()
            self.assertTrue(started.wait(3))
            self.select(service, 2)
            result = mined.result(timeout=2)
        self.assertTrue(result['cancelled'])
        self.assertEqual('wallet_change', result['cancel_reason'])
        self.assertNotIn('block_hash', result)
        self.assertEqual(2, service.mine_one().result(timeout=10)['node']['height'])
        self.assertEqual(1, len(self.verifications))
        with Chain(service.database, network=REGTEST) as chain:
            self.assertEqual(BOB.script_pubkey,
                             chain.get_block(chain.tip_hash).transactions[0].outputs[0].script_pubkey)

    def test_standalone_four_argument_worker_still_verifies_and_closes_each_call(self):
        database = self.directory / 'standalone.sqlite'
        original_verify, original_close = Chain.verify_persisted_state, Chain.close
        verified, closed = [], []

        def verify(chain):
            verified.append(id(chain))
            return original_verify(chain)

        def close(chain):
            closed.append(id(chain))
            return original_close(chain)
        self.assertEqual(('database', 'network', 'public_script', 'cancellation'),
                         tuple(inspect.signature(_mine_block).parameters))
        with patch.object(Chain, 'verify_persisted_state', verify), patch.object(Chain, 'close', close):
            for _ in range(2):
                self.assertIsNotNone(_mine_block(database, REGTEST, ALICE.script_pubkey,
                                                threading.Event()))
        self.assertEqual(2, len(verified))
        self.assertEqual(verified, closed)
        with Chain(database, network=REGTEST) as chain:
            self.assertEqual(2, chain.info()['height'])


if __name__ == '__main__':
    unittest.main()
