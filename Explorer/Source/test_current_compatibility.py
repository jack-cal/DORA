"""Reader regressions only; synthetic records do not assert consensus validity."""
from pathlib import Path
import os,tempfile,json,unittest
from unittest.mock import patch
import test_explorer as fixtures
from server import default_database

class CurrentPathTests(unittest.TestCase):
    def test_new_installation_detects_sumuww_database(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'LOCALAPPDATA':d},clear=True):
            db=Path(d)/'SUMUWW/data/node.sqlite';db.parent.mkdir(parents=True);db.touch()
            self.assertEqual(default_database(),db)

    def test_existing_legacy_database_still_detected(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'LOCALAPPDATA':d},clear=True):
            db=Path(d)/'DORA/data/node.sqlite';db.parent.mkdir(parents=True);db.touch()
            self.assertEqual(default_database(),db)

    def test_current_marker_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'LOCALAPPDATA':d},clear=True):
            base=Path(d)/'SUMUWW';base.mkdir()
            (base/'active-node.json').write_text(json.dumps({'directory':str(Path(d)/'chosen')}))
            self.assertEqual(default_database(),Path(d)/'chosen/node.sqlite')
            with patch.dict(os.environ,{'SUMUWW_DATA_DIR':str(Path(d)/'override')}):
                self.assertEqual(default_database(),Path(d)/'override/node.sqlite')

class ActivatedDifficultyTests(unittest.TestCase):
    setUp=fixtures.ExplorerTests.setUp
    tearDown=fixtures.ExplorerTests.tearDown
    make=fixtures.ExplorerTests.make
    add=fixtures.ExplorerTests.add

    def test_replacement_history_changes_snapshot_but_confirmed_chain_wins(self):
        from sumuww.primitives import hash_to_display
        from server import SnapshotChanged
        old=b'\x43'*32; new=b'\x44'*32
        self.explorer.refresh(force=True)
        initial=self.explorer.snapshot
        self.c.execute('CREATE TABLE mempool_replacements(old_txid BLOB PRIMARY KEY,new_txid BLOB,reason TEXT,seen INTEGER)')
        self.c.execute('INSERT INTO mempool_replacements VALUES (?,?,?,?)',(old,new,'conflict',1))
        self.c.execute('INSERT INTO mempool_replacements VALUES (?,?,?,?)',(self.tx.txid(),new,'conflict',2))
        self.c.commit();self.explorer.refresh(force=True)
        self.assertNotEqual(initial,self.explorer.snapshot)
        result=self.explorer.run('transaction',hash_to_display(old))
        self.assertEqual(result['status'],'replaced')
        self.assertEqual(result['replaced_by'],hash_to_display(new))
        confirmed=self.explorer.run('transaction',hash_to_display(self.tx.txid()))
        self.assertGreater(confirmed['confirmations'],0)
        self.assertFalse(confirmed['pending'])
        self.assertNotIn('replaced_by',confirmed)
        with self.assertRaises(SnapshotChanged):self.explorer.run('transaction',hash_to_display(old),snapshot=initial)

    def test_mining_analysis_across_actual_dgw_activation_height(self):
        parent=self.two
        for height in range(3,8064):
            parent=self.make(parent,height);self.add(parent,height)
        self.c.commit()
        self.explorer.refresh(force=True)
        before=self.explorer.run('mining_analysis',24)
        self.assertEqual(before['next_height'],8064)
        self.assertEqual(before['dgw_remaining'],0)
        parent=self.make(parent,8064);self.add(parent,8064);self.c.commit()
        self.explorer.refresh(force=True)
        for sample in (24,144,2016):
            after=self.explorer.run('mining_analysis',sample)
            self.assertEqual(after['next_height'],8065)
            self.assertEqual(after['block_count'],sample)
            self.assertGreater(after['next_difficulty'],0)

if __name__=='__main__':unittest.main()
