"""Bounded display summaries on fully validated, owned development chains."""

from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from coincurve import PrivateKey

from sumuww.app_service import AppService
from sumuww.chain import Chain
from sumuww.errors import StorageError, ValidationError
from sumuww.keystore import WalletKey
from sumuww.primitives import format_amount, subsidy
from sumuww.profiles import REGTEST, RETARGET_LAB
from sumuww.wallet import RegtestKey


ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)
EVIDENCE = {}


def eventually(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError('Owned summary peer fixture did not synchronize')
        time.sleep(.02)


class StatusSummaryTests(unittest.TestCase):
    BLOCKS = 512

    @classmethod
    def setUpClass(cls):
        cls.fixture_directory = tempfile.TemporaryDirectory(prefix='sumuww-v34-summary-seed-')
        cls.fixture = Path(cls.fixture_directory.name) / 'owned-regtest.sqlite'
        with Chain(cls.fixture, network=REGTEST) as chain:
            chain.mine(ALICE.script_pubkey, cls.BLOCKS)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_directory.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-v34-summary-')
        self.directory = Path(self.temporary.name)
        self.database = self.directory / 'owned-regtest.sqlite'
        shutil.copyfile(self.fixture, self.database)

    def tearDown(self):
        self.temporary.cleanup()

    def test_external_commits_do_not_rebuild_paths_or_commitments_for_summary(self):
        full_seconds, summary_seconds = [], []
        full_path_reads, summary_rows = [], []
        with Chain(self.database, network=REGTEST) as reader, Chain(self.database, network=REGTEST) as writer:
            for _ in range(5):
                writer.mine(BOB.script_pubkey)
                with (patch.object(reader, '_path', side_effect=AssertionError('Display walked chain path')),
                      patch.object(reader, '_replay', side_effect=AssertionError('Display replayed chain')),
                      patch.object(reader, '_load_utxos', side_effect=AssertionError('Display loaded UTXOs')),
                      patch.object(reader, 'state_commitment', side_effect=AssertionError('Display hashed UTXOs')),
                      patch.object(reader, '_row', side_effect=AssertionError('Display read a full block body')),
                      patch.object(reader, '_summary_row', wraps=reader._summary_row) as rows):
                    began = time.perf_counter()
                    summary = reader.summary()
                    summary_seconds.append(time.perf_counter() - began)
                    summary_rows.append(rows.call_count)
                with patch.object(reader, '_read_index_path', wraps=reader._read_index_path) as paths:
                    began = time.perf_counter()
                    full = reader.info()
                    full_seconds.append(time.perf_counter() - began)
                    full_path_reads.append(paths.call_count)
                self.assertIn('utxo_commitment', full)
                self.assertEqual(64, len(full.pop('utxo_commitment')))
                self.assertEqual(full, summary)
                self.assertEqual(80, len(reader._summary_row(reader.tip_hash)[4]))
                self.assertFalse(reader.connection.in_transaction)
        self.assertEqual([1] * 5, summary_rows)
        self.assertEqual([1] * 5, full_path_reads)
        EVIDENCE['external_commit_summary'] = {
            'initial_regtest_height': self.BLOCKS, 'external_commits': 5,
            'summary_index_rows_per_call': summary_rows,
            'summary_block_header_bytes_per_row': 80,
            'full_info_path_rebuilds_per_call': full_path_reads,
            'summary_path_rebuilds': 0, 'summary_replays': 0,
            'summary_utxo_loads': 0, 'summary_commitments': 0,
            'full_info_seconds': full_seconds, 'summary_seconds': summary_seconds,
            'comparison': 'Current full diagnostics versus bounded summary at the same five committed tips; not a user-machine benchmark',
        }

    def test_wallet_utxos_keep_values_and_order_without_loading_unrelated_coins(self):
        with Chain(self.database, network=REGTEST) as chain:
            chain.mine(BOB.script_pubkey, 3)
            old_state = chain._load_utxos()
            expected_all = sorted(old_state.items())
            expected_alice = [(outpoint, coin) for outpoint, coin in expected_all
                              if coin.output.script_pubkey == ALICE.script_pubkey]
            with patch.object(chain, '_load_utxos', side_effect=AssertionError('Wallet loaded complete state')):
                self.assertEqual(expected_all, chain.list_utxos())
                self.assertEqual(expected_alice, chain.list_utxos(ALICE.script_pubkey))
                self.assertEqual([], chain.list_utxos(b'owned-no-match'))
                self.assertEqual(sum(coin.output.value for _, coin in expected_alice),
                                 chain.balance(ALICE.script_pubkey))

    def test_actual_retarget_boundaries_read_only_the_required_branch_interval(self):
        database = self.directory / 'owned-retarget-lab.sqlite'
        looked_up = {}
        with Chain(database, network=RETARGET_LAB) as chain:
            for height in range(1, 33):
                block = chain.make_block(ALICE.script_pubkey,
                                         timestamp=RETARGET_LAB.genesis.header.timestamp + height)
                self.assertTrue(chain.accept_block(block))
                if height not in (14, 15, 16, 30, 31, 32):
                    continue
                full = chain.info()
                with (patch.object(chain, '_path', side_effect=AssertionError('Summary rebuilt lab path')),
                      patch.object(chain, '_row', side_effect=AssertionError('Summary read full lab blocks')),
                      patch.object(chain, '_summary_row', wraps=chain._summary_row) as rows):
                    summary = chain.summary()
                self.assertEqual(full['next_bits'], summary['next_bits'])
                expected_rows = RETARGET_LAB.retarget_interval if (height + 1) % 16 == 0 else 1
                self.assertEqual(expected_rows, rows.call_count)
                looked_up[str(height)] = rows.call_count
        EVIDENCE['retarget_lab_summary'] = {'actual_accepted_blocks': 32,
                                           'index_rows_by_parent_height': looked_up}

    def test_summary_rejects_a_header_index_mismatch(self):
        with Chain(self.database, network=REGTEST) as chain:
            row = chain._row(chain.tip_hash)
            malformed = bytes([row[4][0] ^ 1]) + row[4][1:]
            chain.connection.execute('UPDATE blocks SET raw=? WHERE hash=?', (malformed, row[0]))
            with self.assertRaisesRegex(StorageError, 'header/index mismatch'):
                chain.summary()

    def test_constructor_still_replays_and_rejects_corrupt_persisted_block_bodies(self):
        original_replay = Chain._replay
        replays = []

        def replay(chain, path):
            replays.append(len(path))
            return original_replay(chain, path)

        with patch.object(Chain, '_replay', replay):
            with Chain(self.database, network=REGTEST) as chain:
                self.assertEqual([self.BLOCKS + 1], replays)
                for _ in range(5):
                    self.assertEqual(self.BLOCKS, chain.summary()['height'])
                self.assertEqual([self.BLOCKS + 1], replays)
                row = chain._row(chain.tip_hash)
                # Preserve the header but corrupt the transaction body in this
                # owned file. Periodic display is not persisted-state validation.
                malformed = row[4][:-1] + bytes([row[4][-1] ^ 1])
                chain.connection.execute('UPDATE blocks SET raw=? WHERE hash=?', (malformed, row[0]))
                self.assertEqual(self.BLOCKS, chain.summary()['height'])
            with self.assertRaises((StorageError, ValidationError, ValueError)):
                Chain(self.database, network=REGTEST)
        EVIDENCE['persisted_validation'] = {
            'initial_complete_replay_length': self.BLOCKS + 1,
            'replays_after_five_summaries': 1, 'corrupt_body_reopen_rejected': True,
        }

    def test_actor_summary_mining_and_wallet_refresh_preserve_a_loopback_peer(self):
        services = []
        source, target = None, None
        status_seconds = []
        try:
            for name in ('source', 'target'):
                directory = self.directory / name
                directory.mkdir()
                shutil.copyfile(self.fixture, directory / 'node.sqlite')
                service = AppService(directory, network=REGTEST, listen='127.0.0.1:0',
                                     peers=[], allow_internet=False, allow_lan=False)
                services.append(service)
                service.start().result(timeout=10)
            source, target = services
            key = WalletKey(PrivateKey((1).to_bytes(32, 'big')), REGTEST)
            with patch('sumuww.app_service.keystore_create', return_value=key):
                source.create_wallet('owned-public-wallet-fixture.json', 'public test fixture').result(timeout=5)
            initial = source.status().result(timeout=10)
            self.assertEqual(format_amount(self.BLOCKS * subsidy(1)), initial['wallet']['total_smw'])
            listener = target.status().result(timeout=5)['node']['listen']
            source.add_peer(f"{listener['host']}:{listener['port']}").result(timeout=5)

            def ready():
                return all(service.status().result(timeout=5)['node']['mining_ready']
                           for service in services)

            eventually(ready)
            with (patch.object(source._node.chain, 'info', side_effect=AssertionError('Actor requested full diagnostics')),
                  patch.object(source._node.chain, 'state_commitment', side_effect=AssertionError('Actor hashed state'))):
                for height in range(self.BLOCKS + 1, self.BLOCKS + 9):
                    result = source.mine_one().result(timeout=10)
                    self.assertFalse(result['cancelled'])
                    self.assertEqual(height, result['node']['height'])
                    self.assertNotIn('utxo_commitment', result['node'])
                    began = time.perf_counter()
                    state = source.status().result(timeout=5)
                    status_seconds.append(time.perf_counter() - began)
                    self.assertEqual(format_amount(height * subsidy(1)), state['wallet']['total_smw'])
                    self.assertNotIn('utxo_commitment', state['node'])
                eventually(lambda: target.status().result(timeout=5)['node']['height'] == self.BLOCKS + 8)
                eventually(ready)
                self.assertEqual(1, source.status().result(timeout=5)['node']['peers'])
                self.assertEqual(1, target.status().result(timeout=5)['node']['peers'])
                EVIDENCE['actor_loopback_peer'] = {
                    'initial_regtest_height': self.BLOCKS, 'accepted_mining_results': 8,
                    'source_and_target_final_height': self.BLOCKS + 8,
                    'final_connected_peers': [1, 1], 'final_mining_ready': [True, True],
                    'status_seconds': status_seconds,
                    'full_diagnostic_calls_in_status_and_mine': 0,
                    'utxo_commitment_calls_in_status_and_mine': 0,
                    'wallet_totals_checked_on_every_refresh': True,
                    'scope': 'Two owned loopback regtest actor threads; no public network or main-profile mining',
                }
        finally:
            for service in reversed(services):
                service.stop().result(timeout=10)


if __name__ == '__main__':
    unittest.main()
