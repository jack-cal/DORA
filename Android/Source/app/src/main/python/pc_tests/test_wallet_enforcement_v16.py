"""Current-chain wallet validation, without ordinary reorg warnings or holds.

All keys are public scalar fixtures and all databases are temporary regtest
chains, except explicit default SUMUWW mining-gate tests at its genesis.
"""

import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from coincurve import PrivateKey

from sumuww.address import encode_address
from sumuww.__main__ import create_payment, main
from sumuww.app_service import AppService
from sumuww.chain import Chain
from sumuww.errors import InvalidTransaction
from sumuww.keystore import WalletKey
from sumuww.node_policy import POLICY_NAME
from sumuww.primitives import COIN, hash_to_display
from sumuww.profiles import SUMUWW, REGTEST
from sumuww.wallet import RegtestKey


ALICE = RegtestKey.from_int(1)
BOB = RegtestKey.from_int(2)
BOB_ADDRESS = encode_address(BOB.script_pubkey, network=REGTEST)


def fork(chain, parent, count, final_transactions=None):
    for index in range(count):
        options = {"parent_hash": parent, "extra_nonce": 200 + index}
        if final_transactions is not None and index == count - 1:
            options["transactions"] = final_transactions
        block = chain.make_block(BOB.script_pubkey, **options)
        chain.accept_block(block)
        parent = block.block_hash()
    return parent


class ServiceFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sumuww-wallet-enforcement-")
        self.root = Path(self.temp.name)
        self.services = []

    def tearDown(self):
        for service in reversed(self.services):
            service.stop().result(timeout=15)
        self.temp.cleanup()

    def service(self, name, network=REGTEST):
        service = AppService(self.root / name, network=network, peers=[])
        service.start().result(timeout=10)
        self.services.append(service)
        key = WalletKey(PrivateKey((1).to_bytes(32, "big")), network)
        with patch("sumuww.app_service.keystore_create", return_value=key):
            service.create_wallet("fixture.json", "test only").result(timeout=10)
        return service

    def funded_database(self, name):
        directory = self.root / name
        directory.mkdir()
        database = directory / "node.sqlite"
        with Chain(database) as chain:
            blocks = chain.mine(ALICE.script_pubkey, 100)
        return database, blocks


class WalletEnforcementTests(ServiceFixture):
    def test_valid_deep_reorg_keeps_unspent_mature_funds_usable(self):
        database, blocks = self.funded_database("valid-reorg")
        service = self.service("valid-reorg")
        initial = service.status().result(timeout=5)
        self.assertEqual("50.00000000", initial["wallet"]["available_smw"])
        with Chain(database) as writer:
            mature_outpoint = (blocks[0].transactions[0].txid(), 0)
            mature_coin = dict(writer.list_utxos(ALICE.script_pubkey))[mature_outpoint]
            old_tip = writer.tip_hash
            new_tip = fork(writer, blocks[93].block_hash(), 7)
            self.assertNotEqual(old_tip, new_tip)
            self.assertEqual(new_tip, writer.tip_hash)
            self.assertEqual(mature_coin, dict(writer.list_utxos(ALICE.script_pubkey))[mature_outpoint])
        current = service.status().result(timeout=5)
        self.assertEqual(101, current["node"]["height"])
        self.assertEqual("100.00000000", current["wallet"]["available_smw"])
        confirmed = [entry for entry in current["transactions"] if entry["status"] == "confirmed"]
        self.assertEqual(94, max(entry["height"] for entry in confirmed))
        self.assertEqual(8, confirmed[0]["confirmations"])
        payment = service.send(BOB_ADDRESS, "1", "0.001").result(timeout=10)
        self.assertEqual("local mempool", payment["status"])
        with Chain(database) as chain:
            self.assertEqual(payment["txid"], hash_to_display(chain.mempool_transactions()[0].txid()))

    def test_legacy_hold_and_corrupt_policy_files_do_not_restrict_sends(self):
        database, _ = self.funded_database("legacy")
        legacy = database.parent / POLICY_NAME
        held = json.dumps({"schema": 1, "send_hold": True, "last_reorg": {"depth": 12}}).encode("utf-8")
        legacy.write_bytes(held)
        service = self.service("legacy")
        first = service.send(BOB_ADDRESS, "1", "0.001").result(timeout=10)
        self.assertEqual("local mempool", first["status"])
        self.assertEqual(held, legacy.read_bytes())
        with Chain(database) as writer:
            writer.mine(BOB.script_pubkey)
        legacy.write_bytes(b"{broken legacy file")
        second = service.send(BOB_ADDRESS, "1", "0.001").result(timeout=10)
        self.assertEqual("local mempool", second["status"])
        self.assertEqual(b"{broken legacy file", legacy.read_bytes())
        self.assertNotEqual(first["txid"], second["txid"])

    def test_signed_input_spent_on_new_chain_is_rejected_without_mutation(self):
        database, blocks = self.funded_database("stale-input")
        with Chain(database) as chain:
            signed_before_reorg = create_payment(chain, ALICE, BOB.script_pubkey, COIN, 1000)
            replacement = create_payment(chain, ALICE, BOB.script_pubkey, 2 * COIN, 1000)
            old_tip = chain.tip_hash
            fork(chain, blocks[93].block_hash(), 7, final_transactions=[replacement])
            self.assertNotEqual(old_tip, chain.tip_hash)
            before = (chain.tip_hash, chain.state_commitment(),
                      chain.connection.execute("SELECT count(*) FROM blocks").fetchone()[0],
                      chain.mempool_transactions())
            with self.assertRaisesRegex(InvalidTransaction, "Missing or already spent input"):
                chain.submit_transaction(signed_before_reorg)
            after = (chain.tip_hash, chain.state_commitment(),
                     chain.connection.execute("SELECT count(*) FROM blocks").fetchone()[0],
                     chain.mempool_transactions())
            self.assertEqual(before, after)
            self.assertFalse(chain.connection.in_transaction)
            self.assertTrue(chain.verify_persisted_state())


class DefaultMiningGuardTests(ServiceFixture):
    def test_disconnected_sumuww_never_dispatches_a_mining_worker(self):
        service = self.service("offline", SUMUWW)
        with patch("sumuww.app_service._mine_block") as worker:
            with self.assertRaisesRegex(RuntimeError, "Connect and synchronize"):
                service.mine_one().result(timeout=10)
            worker.assert_not_called()
        self.assertEqual(0, service.status().result(timeout=5)["node"]["height"])

    def test_connected_sumuww_mining_waits_on_peer_disconnect_until_explicit_stop(self):
        first, second = self.service("first", SUMUWW), self.service("second", SUMUWW)
        info = second.status().result(timeout=5)["node"]
        first.add_peer(f"{info['listen']['host']}:{info['listen']['port']}").result(timeout=10)
        deadline = time.monotonic() + 10
        while not first.status().result(timeout=5)["node"]["mining_ready"]:
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.02)
        started = threading.Event()

        def slow_worker(database, network, script, cancellation):
            started.set()
            self.assertTrue(cancellation.wait(10))
            return None

        with patch("sumuww.app_service._mine_block", side_effect=slow_worker):
            future = first.mine_one()
            self.assertTrue(started.wait(5))
            second.stop().result(timeout=10)
            deadline = time.monotonic() + 5
            while first.status().result(timeout=5)['mining']['state'] != 'waiting':
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.02)
            self.assertFalse(future.done())
            self.assertTrue(first.status().result(timeout=5)['mining']['reserved'])
            first.cancel_mining()
            result = future.result(timeout=5)
            self.assertTrue(result['cancelled'])
            self.assertEqual('user_stop', result['cancel_reason'])
        self.assertFalse(first.status().result(timeout=5)["node"]["mining_ready"])

    def test_regtest_standalone_mining_and_wallet_history_still_work(self):
        service = self.service("regtest", REGTEST)
        self.assertIn("block_hash", service.mine_one().result(timeout=10))
        status = service.status().result(timeout=5)
        self.assertEqual(1, status["node"]["height"])
        self.assertEqual(1, status["transactions"][0]["confirmations"])

    def test_public_cli_does_not_offer_standalone_mining(self):
        key = WalletKey(PrivateKey((1).to_bytes(32, "big")), SUMUWW)
        with patch("sys.stderr"), patch("sys.stdout"):
            result = main(["--network", "dora", "--database", str(self.root / "cli.sqlite"),
                           "mine", "--address", key.address, "--count", "1"])
        self.assertEqual(2, result)
        with Chain(self.root / "cli.sqlite", network=SUMUWW) as chain:
            self.assertEqual(0, chain.info()["height"])


if __name__ == "__main__":
    unittest.main()
