"""Database/network queries remain responsive during a sustained PoW search."""
from pathlib import Path
import tempfile
import threading
import time
import unittest

from sumuww.app_service import _search_active_chain
from sumuww.block import GENESIS_TIME, Header, mine_header
from sumuww.chain import Chain
from sumuww.profiles import REGTEST
from sumuww.wallet import RegtestKey


class HardSearch:
    tip_hash = bytes(32)

    def make_block(self, script, *, parent_hash, mining_cancel):
        # A negligible target keeps this owned worker searching until cancelled.
        return mine_header(Header(4, parent_hash, bytes(32), 1, 0x01010000, 0),
                           max_attempts=100_000_000, pow_limit=REGTEST.pow_limit,
                           cancel_check=mining_cancel)


class MiningActorFairnessTests(unittest.TestCase):
    def test_wallet_and_peer_queries_do_not_starve_behind_hash_worker(self):
        with tempfile.TemporaryDirectory(prefix='sumuww-fairness-') as folder:
            with Chain(Path(folder)/'node.sqlite', clock=lambda: GENESIS_TIME + 10000) as chain:
                chain.mine(RegtestKey.from_int(39).script_pubkey, 2048)
                stop = threading.Event()
                errors = []

                def worker():
                    try:
                        _search_active_chain(HardSearch(), b'', stop)
                    except BaseException as error:
                        errors.append(error)

                thread = threading.Thread(target=worker)
                thread.start()
                try:
                    time.sleep(.05)
                    started = time.monotonic()
                    self.assertEqual(2048, len(chain.list_utxos()))
                    chain.headers_after(chain.block_locator())
                    elapsed = time.monotonic() - started
                    self.assertLess(elapsed, 3, 'Hash worker starved wallet/peer database queries')
                finally:
                    stopped = time.monotonic()
                    stop.set()
                    thread.join(2)
                self.assertFalse(thread.is_alive())
                self.assertFalse(errors, errors)
                self.assertLess(time.monotonic() - stopped, 2)


if __name__ == '__main__':
    unittest.main()
