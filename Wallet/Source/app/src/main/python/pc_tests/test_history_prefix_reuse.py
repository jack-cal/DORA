"""Reuse only same-snapshot, hash-matched ancestors for proof history lookups."""
from pathlib import Path
from contextlib import closing
import sqlite3,tempfile,unittest
from unittest.mock import patch
from sumuww.chain import Chain
from sumuww.errors import StorageError
from sumuww.wallet import RegtestKey

class HistoryPrefixTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/'node.sqlite'
        self.chain=Chain(self.path)
        self.script=RegtestKey.from_int(3888).script_pubkey
        self.chain.mine(self.script,16)
        self.tip_path=self.chain._path(self.chain.tip_hash)
    def tearDown(self):
        self.chain.close();self.folder.cleanup()
    def test_repeated_old_ancestors_do_not_reparse_genesis_history(self):
        with patch.object(self.chain,'_read_index_path',side_effect=AssertionError('ancestor history reread')):
            for _ in range(3):
                for height in (0,1,5,9):
                    path=self.chain._path(self.tip_path[height][0][0])
                    self.assertEqual(self.tip_path[:height+1],path)
                    self.assertIsInstance(path,tuple)
    def test_same_connection_index_edit_invalidates_prefix(self):
        digest=self.tip_path[5][0][0]
        self.chain.connection.execute("UPDATE blocks SET work='0' WHERE hash=?",(digest,))
        with self.assertRaises(StorageError):self.chain._path(digest)
    def test_external_index_edit_invalidates_prefix(self):
        digest=self.tip_path[5][0][0]
        with closing(sqlite3.connect(self.path,isolation_level=None)) as other:
            other.execute("UPDATE blocks SET work='0' WHERE hash=?",(digest,))
        with self.assertRaises(StorageError):self.chain._path(digest)
    def test_fork_at_same_height_never_reuses_canonical_ancestor(self):
        fork=self.chain.make_block(self.script,(),parent_hash=self.tip_path[5][0][0],extra_nonce=888)
        self.chain.accept_block(fork)
        self.chain._path(self.chain.tip_hash)
        result=self.chain._path(fork.block_hash())
        self.assertEqual(fork.block_hash(),result[-1][0][0])
        self.assertNotEqual(self.tip_path[6][0][0],result[-1][0][0])
