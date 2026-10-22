"""Index/HTTP checks use isolated fixtures, never the user's chain or wallet."""
import hashlib
import csv
import io
import copy
import server as explorer_module
import http.client
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from types import SimpleNamespace

from server import Explorer, Handler, NotFound, DataUnavailable, SnapshotChanged, ExplorerHTTPServer as ThreadingHTTPServer, amount, default_database, verify_merkle_proof
from sumuww.address import encode_address
from sumuww.block import Block, build_coinbase
from sumuww.primitives import Header, merkle_root, hash_to_display
from sumuww.profiles import SUMUWW
from sumuww.transaction import Transaction, TxInput, TxOutput

class ExplorerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.db=self.root/'node.sqlite'
        self.script=b'\x00\x14'+b'\x12'*20
        self.recipient=b'\x00\x14'+b'\x34'*20
        self.address=encode_address(self.script,network=SUMUWW)
        self.c=sqlite3.connect(self.db)
        self.c.executescript('''CREATE TABLE metadata(name TEXT PRIMARY KEY,value);
          CREATE TABLE blocks(hash BLOB PRIMARY KEY,parent BLOB,height INTEGER,work TEXT,raw BLOB);
          CREATE TABLE utxos(txid BLOB,idx INTEGER,value INTEGER,script BLOB,height INTEGER,coinbase INTEGER);
          CREATE TABLE mempool(id INTEGER PRIMARY KEY,txid BLOB,raw BLOB);''')
        for key,value in [('profile',SUMUWW.profile_id),('schema','1'),('genesis',SUMUWW.genesis.block_hash()),('tip',SUMUWW.genesis.block_hash())]:
            self.c.execute('INSERT INTO metadata VALUES (?,?)',(key,value))
        self.add(SUMUWW.genesis,0)
        self.one=self.make(SUMUWW.genesis,1)
        self.add(self.one,1)
        self.tx=Transaction(2,(TxInput(self.one.transactions[0].txid(),0,b'',0xffffffff,()),),
                            (TxOutput(4900000000,self.recipient),),0)
        # Synthetic records only exercise the reader; they do not assert consensus validity.
        self.two=self.make(self.one,2,transactions=(self.tx,))
        self.add(self.two,2)
        self.c.execute('INSERT INTO utxos VALUES (?,?,?,?,?,?)',(self.tx.txid(),0,4900000000,self.recipient,2,0))
        self.c.commit()
        self.explorer=Explorer(self.db,self.root/'explorer.sqlite')

    def tearDown(self):
        self.explorer.close();self.c.close();self.temp.cleanup()

    def make(self,parent,height,nonce=0,transactions=()):
        txs=(build_coinbase(height,self.script,extra_nonce=nonce),)+transactions
        root,_=merkle_root([tx.txid() for tx in txs])
        return Block(Header(1,parent.block_hash(),root,parent.header.timestamp+600,SUMUWW.initial_bits,nonce),txs)

    def add(self,block,height,active=True):
        self.c.execute('INSERT INTO blocks VALUES (?,?,?,?,?)',(block.block_hash(),block.header.previous_hash,height,str(height+1),block.serialize()))
        if active:self.c.execute("UPDATE metadata SET value=? WHERE name='tip'",(block.block_hash(),))

    def test_source_read_only_and_same_bytes(self):
        digest=hashlib.sha256(self.db.read_bytes()).hexdigest()
        source=self.explorer.source()
        with self.assertRaises(sqlite3.OperationalError):
            source.execute('DELETE FROM blocks')
        source.close()
        self.explorer.run('overview')
        self.explorer.run('address',self.address)
        self.assertEqual(digest,hashlib.sha256(self.db.read_bytes()).hexdigest())

    def test_block_transaction_and_address(self):
        self.assertEqual(self.explorer.run('overview')['height'],2)
        tx=self.explorer.run('transaction',hash_to_display(self.tx.txid()))
        self.assertEqual(tx['fee'],'1.00000000')
        self.assertEqual(tx['confirmations'],1)
        source=self.explorer.run('transaction',hash_to_display(self.one.transactions[0].txid()))
        self.assertEqual(source['outputs'][0]['spent_by'],tx['txid'])
        result=self.explorer.run('address',encode_address(self.recipient,network=SUMUWW))
        self.assertEqual(result['confirmed'],'49.00000000')
        self.assertEqual(result['available'],'49.00000000')
        self.assertEqual(result['total_transactions'],1)
        self.assertEqual(self.explorer.run('search','2')['type'],'block')

    def test_transaction_lists_separate_rewards_and_ordinary_transfers(self):
        overview=self.explorer.run('overview')
        self.assertEqual(overview['transactions'],4)
        self.assertEqual(overview['coinbase_transactions'],3)
        self.assertEqual(overview['ordinary_transactions'],1)
        ordinary=self.explorer.run('transactions','ordinary')
        self.assertEqual(ordinary['total'],1)
        self.assertEqual(ordinary['transactions'][0]['txid'],hash_to_display(self.tx.txid()))
        self.assertEqual(ordinary['transactions'][0]['confirmations'],1)
        rewards=self.explorer.run('transactions','coinbase')
        self.assertEqual(rewards['total'],3)
        self.assertTrue(all(row['coinbase'] for row in rewards['transactions']))
        self.assertEqual(self.explorer.run('transactions','all')['total'],4)
        self.assertEqual(self.explorer.run('transactions','all')['transactions'][0]['txid'],hash_to_display(self.tx.txid()))
        self.assertEqual(self.explorer.run('transactions','ordinary',25)['transactions'],[])
        for kind in ['pending','x OR 1=1','']:
            with self.assertRaises(ValueError):self.explorer.run('transactions',kind)
        with self.assertRaises(ValueError):self.explorer.run('transactions','all',1000001)

    def test_transaction_list_pagination_and_reorg(self):
        parent=self.two
        for height in range(3,31):
            parent=self.make(parent,height);self.add(parent,height)
        self.c.commit();self.explorer.refresh(force=True)
        first=self.explorer.run('transactions','coinbase',0);second=self.explorer.run('transactions','coinbase',25)
        self.assertEqual(len(first['transactions']),25);self.assertEqual(len(second['transactions']),6)
        self.assertEqual([row['height'] for row in first['transactions']],list(range(30,5,-1)))
        self.assertFalse(set(r['txid'] for r in first['transactions'])&set(r['txid'] for r in second['transactions']))
        self.c.execute("UPDATE metadata SET value=? WHERE name='tip'",(self.one.block_hash(),));self.c.execute('DELETE FROM utxos');self.c.commit()
        self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.run('transactions','ordinary')['total'],0)
        self.assertEqual(self.explorer.run('transactions','coinbase')['total'],2)

    def test_http_transaction_filters_and_translation_asset(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.explorer=self.explorer
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            for path,status in [('/api/transactions',200),('/api/transactions?kind=ordinary',200),
                                ('/api/transactions?kind=coinbase&offset=25',200),('/api/transactions?kind=all',200),
                                ('/api/transactions?kind=bad',400),('/api/transactions?kind=all&kind=ordinary',400),
                                ('/api/transactions?offset=-1',400),('/api/transactions?snapshot='+'0'*64,409),
                                ('/languages.js',200)]:
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port);connection.request('GET',path)
                response=connection.getresponse();raw=response.read();connection.close()
                self.assertEqual(response.status,status,path)
                if path=='/api/transactions':self.assertEqual(json.loads(raw)['kind'],'ordinary')
                if path=='/languages.js':self.assertIn(b'const explorerLanguages=',raw)
        finally:server.shutdown();server.server_close();thread.join()

    def test_reorg_removes_old_transactions_and_address_history(self):
        fork=self.make(self.one,2,nonce=44)
        self.add(fork,2)
        self.c.execute('DELETE FROM utxos')
        self.c.commit()
        self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.run('block','2')['hash'],hash_to_display(fork.block_hash()))
        with self.assertRaises(NotFound):self.explorer.run('transaction',hash_to_display(self.tx.txid()))
        result=self.explorer.run('address',encode_address(self.recipient,network=SUMUWW))
        self.assertEqual(result['total_transactions'],0)
        self.assertEqual(result['confirmed'],'0.00000000')

    def test_pending_spend_and_received(self):
        tx=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,()),),(TxOutput(4800000000,self.script),),0)
        self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(1,tx.txid(),tx.serialize()));self.c.commit()
        self.explorer.refresh(force=True)
        sender=self.explorer.run('address',encode_address(self.recipient,network=SUMUWW))
        self.assertEqual(sender['available'],'0.00000000')
        self.assertTrue(sender['utxos'][0]['pending_spent'])
        receiver=self.explorer.run('address',self.address)
        self.assertEqual(receiver['pending_received'],'48.00000000')
        self.assertEqual(len(receiver['pending']),1)
        self.assertTrue(self.explorer.run('transaction',hash_to_display(tx.txid()))['pending'])

    def test_maturity_boundary_and_restart(self):
        self.c.execute('INSERT INTO utxos VALUES (?,?,?,?,?,?)',(self.one.transactions[0].txid(),0,5000000000,self.script,1,1));self.c.commit()
        self.explorer.refresh(force=True)
        result=self.explorer.run('address',self.address)
        self.assertEqual(result['immature'],'50.00000000')
        # Advancing a synthetic chain to 100 allows inclusion of a spend in 101.
        parent=self.two
        for height in range(3,101):
            parent=self.make(parent,height);self.add(parent,height)
        self.c.commit();self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.run('address',self.address)['available'],'50.00000000')
        self.explorer.close()
        self.explorer=Explorer(self.db,self.root/'explorer.sqlite')
        self.assertEqual(self.explorer.run('overview')['height'],100)

    def test_invalid_inputs_and_network(self):
        with self.assertRaises(ValueError):self.explorer.run('search','<script>alert(1)</script>')
        with self.assertRaises(ValueError):self.explorer.run('transaction','garbage')
        self.c.execute("UPDATE metadata SET value='wrong' WHERE name='profile'");self.c.commit()
        with self.assertRaises(DataUnavailable):self.explorer.refresh(force=True)
        self.assertEqual(amount(1799999997690000),'17999999.97690000')

    def test_genesis_outputs_and_pagination(self):
        genesis=self.explorer.run('transaction',hash_to_display(SUMUWW.genesis.transactions[0].txid()))
        self.assertTrue(genesis['outputs'][0]['unspendable'])
        page=self.explorer.run('overview',2)
        self.assertEqual([b['height'] for b in page['blocks']],[1,0])
        self.assertIsNone(page['next_before'])
        self.assertEqual(self.explorer.run('block','1')['transactions'][0]['height'],1)
        self.assertEqual(self.explorer.run('mempool')['total'],0)

    def test_failed_refresh_does_not_commit_half_snapshot(self):
        three=self.make(self.two,3);self.add(three,3)
        self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(1,bytes(32),self.tx.serialize()))
        self.c.commit()
        with self.assertRaises(Exception):self.explorer.refresh(force=True)
        with closing(sqlite3.connect(self.explorer.index)) as c:
            self.assertEqual(c.execute('SELECT max(height) FROM blocks').fetchone()[0],2)

    def test_pending_chain_does_not_double_count_received(self):
        a=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,()),),(TxOutput(4800000000,self.script),),0)
        b=Transaction(2,(TxInput(a.txid(),0,b'',0xffffffff,()),),(TxOutput(4700000000,self.script),),0)
        for i,tx in enumerate([a,b]):self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(i,tx.txid(),tx.serialize()))
        self.c.commit();self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.run('address',self.address)['pending_received'],'47.00000000')

    def test_source_body_corruption_is_rejected(self):
        block=self.make(self.two,3)
        altered=Transaction(2,block.transactions[0].inputs,(TxOutput(123,self.script),),0)
        broken=Block(block.header,(altered,))
        self.add(broken,3);self.c.commit()
        with self.assertRaises(Exception):self.explorer.refresh(force=True)

    def test_foreign_index_is_not_modified(self):
        foreign=self.root/'foreign.sqlite'
        with closing(sqlite3.connect(foreign)) as c,c:c.execute('CREATE TABLE private_data(value)')
        digest=hashlib.sha256(foreign.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):Explorer(self.db,foreign)
        self.assertEqual(digest,hashlib.sha256(foreign.read_bytes()).hexdigest())

    def test_hardlinked_source_cannot_be_an_index(self):
        alias=self.root/'alias.sqlite';os.link(self.db,alias)
        digest=hashlib.sha256(self.db.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):Explorer(self.db,alias)
        self.assertEqual(digest,hashlib.sha256(self.db.read_bytes()).hexdigest())

    def test_query_ranges_are_bounded(self):
        with self.assertRaises(ValueError):self.explorer.run('overview',1<<100)

    def test_index_has_one_owner_and_can_reopen(self):
        with self.assertRaises(ValueError):Explorer(self.db,self.explorer.index)
        self.explorer.close()
        self.explorer=Explorer(self.db,self.root/'explorer.sqlite')
        self.assertEqual(self.explorer.run('overview')['height'],2)

    def test_source_sidecars_cannot_be_index_or_lock(self):
        for suffix in ['-wal','-shm','-journal']:
            with self.assertRaises(ValueError):Explorer(self.db,Path(str(self.db)+suffix))
        alias=self.root/'alias-lock.sqlite.lock';os.link(self.db,alias)
        with self.assertRaises(ValueError):Explorer(self.db,self.root/'alias-lock.sqlite')

    def test_failed_insert_rolls_back_every_new_row(self):
        three=self.make(self.two,3);self.add(three,3);self.c.commit()
        insert=self.explorer.insert_block
        def fail(*args):
            insert(*args);raise sqlite3.OperationalError('simulated disk failure')
        snapshot=self.explorer.snapshot
        with patch.object(self.explorer,'insert_block',side_effect=fail):
            with self.assertRaises(DataUnavailable):self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.snapshot,snapshot)
        with closing(sqlite3.connect(self.explorer.index)) as c:
            self.assertEqual(c.execute('SELECT max(height) FROM blocks').fetchone()[0],2)
        self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.run('overview')['height'],3)

    def test_snapshot_guards_both_chain_and_mempool_changes(self):
        snapshot=self.explorer.run('overview')['snapshot']
        self.assertEqual(self.explorer.run('block','2',snapshot=snapshot)['snapshot'],snapshot)
        pending=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,()),),(TxOutput(1,self.script),),0)
        self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(1,pending.txid(),pending.serialize()));self.c.commit()
        self.explorer.refresh(force=True)
        with self.assertRaises(SnapshotChanged):self.explorer.run('block','2',snapshot=snapshot)

    def test_unchanged_refresh_keeps_download_snapshot_valid(self):
        snapshot=self.explorer.snapshot
        for _ in range(3):self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.snapshot,snapshot)
        self.assertTrue(self.explorer.run('export_statistics',24,snapshot=snapshot)['data'])

    def test_utxo_only_change_invalidates_download_snapshot(self):
        snapshot=self.explorer.snapshot
        self.c.execute('UPDATE utxos SET value=value-1');self.c.commit()
        self.explorer.refresh(force=True)
        with self.assertRaises(SnapshotChanged):self.explorer.run('export_address',self.address,snapshot=snapshot)

    def test_missing_source_recovers_without_recreating_it(self):
        snapshot=self.explorer.snapshot
        self.c.close();saved=self.db.with_suffix('.saved');self.db.rename(saved)
        try:
            with self.assertRaises(DataUnavailable):self.explorer.refresh(force=True)
            self.assertFalse(self.db.exists())
            self.assertEqual(self.explorer.snapshot,snapshot)
        finally:
            saved.rename(self.db);self.c=sqlite3.connect(self.db)
        self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.run('overview')['height'],2)

    def test_pending_confirmation_updates_address_and_proof_together(self):
        pending=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,()),),(TxOutput(4800000000,self.script),),0)
        txid=hash_to_display(pending.txid())
        self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(1,pending.txid(),pending.serialize()));self.c.commit()
        self.explorer.refresh(force=True)
        self.assertTrue(self.explorer.run('transaction',txid)['pending'])
        self.assertEqual(self.explorer.run('address',self.address)['pending_received'],'48.00000000')
        three=self.make(self.two,3,transactions=(pending,));self.add(three,3)
        self.c.execute('DELETE FROM mempool');self.c.execute('DELETE FROM utxos')
        self.c.execute('INSERT INTO utxos VALUES (?,?,?,?,?,?)',(pending.txid(),0,4800000000,self.script,3,0));self.c.commit()
        self.explorer.refresh(force=True)
        self.assertFalse(self.explorer.run('transaction',txid)['pending'])
        result=self.explorer.run('address',self.address)
        self.assertEqual(result['available'],'48.00000000');self.assertEqual(result['pending_received'],'0.00000000')
        self.assertEqual(result['pending'],[])
        self.assertTrue(verify_merkle_proof(self.explorer.run('proof',txid)))

    def test_pending_witness_change_invalidates_snapshot(self):
        tx=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,(b'first',)),),(TxOutput(1,self.script),),0)
        self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(1,tx.txid(),tx.serialize()));self.c.commit()
        self.explorer.refresh(force=True);snapshot=self.explorer.snapshot
        changed=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,(b'second',)),),tx.outputs,0)
        self.assertEqual(changed.txid(),tx.txid())
        self.c.execute('UPDATE mempool SET raw=?',(changed.serialize(),));self.c.commit();self.explorer.refresh(force=True)
        with self.assertRaises(SnapshotChanged):self.explorer.run('raw_transaction',hash_to_display(tx.txid()),snapshot=snapshot)

    def test_source_wal_writer_cannot_mix_read_snapshot(self):
        self.c.execute('PRAGMA journal_mode=WAL')
        three=self.make(self.two,3);four=self.make(three,4)
        self.add(three,3);self.c.commit()
        insert=self.explorer.insert_block
        def write_during_index(*args):
            self.add(four,4)
            self.c.execute('UPDATE utxos SET value=4800000000');self.c.commit()
            insert(*args)
        with patch.object(self.explorer,'insert_block',side_effect=write_during_index):
            self.explorer.refresh(force=True)
        receiver=encode_address(self.recipient,network=SUMUWW)
        self.assertEqual(self.explorer.run('overview')['height'],3)
        self.assertEqual(self.explorer.run('address',receiver)['confirmed'],'49.00000000')
        self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.run('overview')['height'],4)
        self.assertEqual(self.explorer.run('address',receiver)['confirmed'],'48.00000000')

    def test_shorter_reorg_removes_suffix(self):
        self.c.execute("UPDATE metadata SET value=? WHERE name='tip'",(self.one.block_hash(),))
        self.c.execute('DELETE FROM utxos');self.c.commit()
        self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.run('overview')['height'],1)
        with self.assertRaises(NotFound):self.explorer.run('block','2')

    def test_missing_parent_does_not_change_index(self):
        three=self.make(self.two,3);self.add(three,3)
        self.c.execute('UPDATE blocks SET parent=? WHERE hash=?',(bytes([9])*32,three.block_hash()));self.c.commit()
        with self.assertRaises(DataUnavailable):self.explorer.refresh(force=True)
        with closing(sqlite3.connect(self.explorer.index)) as c:
            self.assertEqual(c.execute('SELECT max(height) FROM blocks').fetchone()[0],2)

    def test_empty_malformed_and_corrupt_sources(self):
        with self.assertRaises(ValueError):Explorer(self.root/'missing.sqlite',self.root/'unused.sqlite')
        self.assertFalse((self.root/'missing.sqlite').exists())
        malformed=self.root/'malformed.sqlite';malformed.write_bytes(b'not a database')
        with self.assertRaises(DataUnavailable):Explorer(malformed,self.root/'other-index.sqlite')
        corrupt=self.root/'corrupt-index.sqlite';corrupt.write_bytes(b'broken index')
        with self.assertRaises(sqlite3.DatabaseError):Explorer(self.db,corrupt)
        # Repeated failures release the ownership lock and SQLite handles.
        with self.assertRaises(sqlite3.DatabaseError):Explorer(self.db,corrupt)

    def test_mempool_pagination_is_bounded_and_summary_only(self):
        for i in range(55):
            tx=Transaction(2,(TxInput(bytes([i])*32,i,b'',0xffffffff,()),),(TxOutput(1,self.script),),0)
            self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(i,tx.txid(),tx.serialize()))
        self.c.commit();self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.run('mempool')['total'],55)
        self.assertEqual(len(self.explorer.run('mempool')['transactions']),25)
        self.assertEqual(len(self.explorer.run('mempool',50)['transactions']),5)
        self.assertEqual(len(self.explorer.run('overview')['mempool']),20)
        self.assertNotIn('inputs',self.explorer.run('overview')['mempool'][0])
        self.assertEqual(self.explorer.run('address',self.address)['pending_received'],'0.00000055')

    def test_address_alias_and_case_have_same_result(self):
        from sumuww.address import _bech32_encode,_bech32_decode
        _,data=_bech32_decode(self.address)
        alias=_bech32_encode('dora',data)
        for text in [self.address.upper(),alias]:
            self.assertEqual(self.explorer.run('address',text)['address'],self.address)
        with self.assertRaises(ValueError):self.explorer.run('address',self.address[:5].upper()+self.address[5:])

    def test_clock_rollback_does_not_block_refresh(self):
        with patch('server.time.time',return_value=1):self.explorer.refresh(force=True)
        self.explorer._refreshed-=4
        self.explorer.run('overview')
        self.assertGreater(self.explorer.updated,1)

    def test_concurrent_reads_are_consistent(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            results=list(executor.map(lambda _:self.explorer.run('overview'),range(24)))
        self.assertEqual({r['snapshot'] for r in results},{self.explorer.snapshot})
        self.assertEqual({r['height'] for r in results},{2})

    def test_corrupt_utxo_cannot_be_published_as_a_balance(self):
        for field,value in [('value',-1),('script','not bytes'),('height',999),('coinbase',3)]:
            self.c.execute('BEGIN')
            self.c.execute('UPDATE utxos SET '+field+'=?',(value,))
            self.c.commit()
            with self.assertRaises(DataUnavailable):self.explorer.refresh(force=True)
            self.c.execute('UPDATE utxos SET value=4900000000,script=?,height=2,coinbase=0',(self.recipient,));self.c.commit()
        self.explorer.refresh(force=True)

    def test_unchanged_tip_has_no_index_mutations(self):
        statements=[];connect=self.explorer.connect_index
        def traced():
            connection=connect();connection.set_trace_callback(statements.append);return connection
        with patch.object(self.explorer,'connect_index',side_effect=traced):self.explorer.refresh(force=True)
        self.assertFalse(any(sql.lstrip().split()[0].upper() in ['INSERT','UPDATE','DELETE','REPLACE'] for sql in statements))

    def test_default_path_rejects_bad_markers_and_preserves_override(self):
        state=self.root/'state';(state/'SUMUWW').mkdir(parents=True)
        marker=state/'SUMUWW/active-node.json'
        with patch.dict(os.environ,{'LOCALAPPDATA':str(state),'DORA_DATA_DIR':''}):
            marker.write_text('not json')
            with self.assertRaises(ValueError):default_database()
            for data in [{'directory':7},{'directory':''},{'directory':'a','extra':1}]:
                marker.write_text(json.dumps(data))
                with self.assertRaises(ValueError):default_database()
            marker.write_text(json.dumps({'directory':str(self.root)}))
            self.assertEqual(default_database(),self.db)
            with patch.dict(os.environ,{'DORA_DATA_DIR':str(self.root/'override')}):
                self.assertEqual(default_database(),self.root/'override/node.sqlite')

    def test_http_read_only_host_and_cross_site(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.explorer=self.explorer
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            for method,path,headers,status in [('GET','/api/overview',{},200),('POST','/api/overview',{},405),
              ('GET','/api/overview',{'Host':'evil.example'},403),
              ('GET','/api/overview',{'Sec-Fetch-Site':'cross-site'},403),
              ('GET','/api/overview',{'Origin':'http://evil.example'},403),
              ('GET','/api/block/999',{},404),('GET','/api/block/1?offset=-1',{},400),('GET','/../server.py',{},404)]:
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
                conn.request(method,path,headers=headers);response=conn.getresponse()
                self.assertEqual(response.status,status,(method,path));response.read();conn.close()
        finally:server.shutdown();server.server_close();thread.join()

    def test_duplicate_listening_port_is_refused(self):
        from http.server import ThreadingHTTPServer as LegacyServer
        first=LegacyServer(('127.0.0.1',0),Handler)
        try:
            with self.assertRaises(OSError):ThreadingHTTPServer(('127.0.0.1',first.server_port),Handler)
        finally:first.server_close()

    def test_launcher_reuses_running_explorer_without_opening_database(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.explorer=self.explorer
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with patch('sys.argv',['server.py','--open-browser','--port',str(server.server_port)]), \
                 patch.object(explorer_module,'default_database',side_effect=AssertionError('Must reuse the existing instance')), \
                 patch.object(explorer_module.webbrowser,'open',return_value=True) as browser:
                self.assertEqual(explorer_module.main(),0)
                browser.assert_called_once_with('http://127.0.0.1:'+str(server.server_port))
            self.assertEqual(self.explorer.run('overview')['height'],2)
        finally:server.shutdown();server.server_close();thread.join()

    def test_launcher_starts_server_then_opens_bound_port(self):
        launched=[]
        def end_after_start(server):
            launched.append(server.server_port)
            self.assertGreater(server.server_port,0)
        with patch('sys.argv',['server.py','--database',str(self.db),'--index',str(self.root/'launch.sqlite'),'--port','0','--open-browser']), \
             patch.object(ThreadingHTTPServer,'serve_forever',end_after_start), \
             patch.object(explorer_module.webbrowser,'open',return_value=True) as browser:
            self.assertEqual(explorer_module.main(),0)
            browser.assert_called_once_with('http://127.0.0.1:'+str(launched[0]))
        # Startup shutdown releases the index ownership lock.
        reopened=Explorer(self.db,self.root/'launch.sqlite');reopened.close()

    def test_headless_launch_does_not_open_browser(self):
        with patch('sys.argv',['server.py','--database',str(self.db),'--index',str(self.root/'headless.sqlite'),'--port','0','--no-browser']), \
             patch.object(ThreadingHTTPServer,'serve_forever',return_value=None), \
             patch.object(explorer_module.webbrowser,'open') as browser:
            self.assertEqual(explorer_module.main(),0);browser.assert_not_called()

    def test_custom_database_is_not_silently_replaced_by_running_explorer(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        try:
            with patch('sys.argv',['server.py','--database',str(self.db),'--open-browser','--port',str(server.server_port)]), \
                 patch.object(explorer_module.webbrowser,'open') as browser:
                self.assertEqual(explorer_module.main(),1);browser.assert_not_called()
        finally:server.server_close()

    def test_running_instance_detection_rejects_other_or_broken_responses(self):
        from unittest.mock import MagicMock
        valid=self.explorer.run('overview')
        for raw in [b'not json',b'[]',b'{}',json.dumps({**valid,'source':'other app'}).encode(),
                    json.dumps({**valid,'height':True}).encode(),json.dumps({**valid,'tip':'broken'}).encode()]:
            response=MagicMock();response.__enter__.return_value=response;response.status=200;response.read.return_value=raw
            with patch.object(explorer_module,'urlopen',return_value=response):
                self.assertFalse(explorer_module.running_explorer(8770))
        with patch.object(explorer_module,'urlopen',side_effect=TimeoutError()):
            self.assertFalse(explorer_module.running_explorer(8770))

    def test_browser_launch_failure_keeps_manual_address_available(self):
        for behavior in [dict(return_value=False),dict(side_effect=OSError('No browser'))]:
            with patch.object(explorer_module.webbrowser,'open',**behavior),patch('sys.stdout',new_callable=io.StringIO) as output:
                explorer_module.open_explorer_browser(8770)
                self.assertIn('http://127.0.0.1:8770',output.getvalue())

    def test_http_bad_queries_and_failure_recovery(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.explorer=self.explorer
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def get(path,method='GET'):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=8)
            conn.request(method,path);response=conn.getresponse();raw=response.read();conn.close()
            return response.status,json.loads(raw) if raw else None
        try:
            for path in ['/api/overview?before='+str(1<<100),'/api/overview?before=-1','/api/overview?before=',
              '/api/overview?before=1&before=2','/api/overview?before=1.1','/api/overview?unknown=1',
              '/api/block/1?offset=1000001','/api/address/nope','/api/overview?snapshot=invalid',
              '/api/overview?'+'&'.join('before=1' for _ in range(9))]:
                self.assertEqual(get(path)[0],400,path)
            self.assertEqual(get('/api/overview?snapshot='+'0'*64)[0],409)
            for method in ['PUT','PATCH','DELETE','OPTIONS']:
                self.assertEqual(get('/api/overview',method)[0],405)
            self.assertEqual(get('/','HEAD')[0],200)
            self.explorer._refreshed-=4
            self.c.execute('BEGIN EXCLUSIVE')
            self.assertEqual(get('/api/overview')[0],503)
            self.c.rollback()
            self.assertEqual(get('/api/overview')[0],200)
        finally:self.c.rollback();server.shutdown();server.server_close();thread.join()

    def test_address_received_spent_and_change_are_distinct(self):
        change=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,()),),
                           (TxOutput(3000000000,self.script),TxOutput(1800000000,self.recipient)),0)
        three=self.make(self.two,3,transactions=(change,));self.add(three,3);self.c.commit()
        self.explorer.refresh(force=True)
        data=self.explorer.run('address',encode_address(self.recipient,network=SUMUWW))
        row=data['transactions'][0]
        self.assertEqual(row['received'],'18.00000000')
        self.assertEqual(row['spent'],'49.00000000')
        self.assertEqual(row['net_change'],'-31.00000000')
        self.assertEqual(row['output_total'],'48.00000000')
        receiver=self.explorer.run('address',self.address)['transactions'][0]
        self.assertEqual(receiver['net_change'],'30.00000000')

    def test_pending_self_transfer_shows_only_net_fee_loss(self):
        tx=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,()),),(TxOutput(4800000000,self.recipient),),0)
        self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(1,tx.txid(),tx.serialize()));self.c.commit();self.explorer.refresh(force=True)
        row=self.explorer.run('address',encode_address(self.recipient,network=SUMUWW))['pending'][0]
        self.assertEqual(row['received'],'48.00000000');self.assertEqual(row['spent'],'49.00000000')
        self.assertEqual(row['net_change'],'-1.00000000')

    def test_unknown_pending_input_is_not_reported_as_zero_spent(self):
        tx=Transaction(2,(TxInput(bytes([7])*32,0,b'',0xffffffff,()),),(TxOutput(1,self.script),),0)
        self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(1,tx.txid(),tx.serialize()));self.c.commit();self.explorer.refresh(force=True)
        row=self.explorer.run('address',self.address)['pending'][0]
        self.assertIsNone(row['spent']);self.assertIsNone(row['net_change'])

    def test_raw_downloads_match_original_bytes(self):
        self.assertEqual(self.explorer.run('raw_block','2')['data'],self.two.serialize())
        self.assertEqual(self.explorer.run('raw_transaction',hash_to_display(self.tx.txid()))['data'],self.tx.serialize())
        tx=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,(b'example witness',)),),(TxOutput(1,self.script),),0)
        self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(1,tx.txid(),tx.serialize()));self.c.commit();self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.run('raw_transaction',hash_to_display(tx.txid()))['data'],tx.serialize())

    def test_merkle_proofs_even_odd_and_single_transaction(self):
        genesis=self.explorer.run('proof',hash_to_display(SUMUWW.genesis.transactions[0].txid()))
        self.assertEqual(genesis['siblings'],[]);self.assertTrue(verify_merkle_proof(genesis))
        self.assertTrue(verify_merkle_proof(self.explorer.run('proof',hash_to_display(self.tx.txid()))))
        txs=tuple(Transaction(2,(TxInput(bytes([i+1])*32,i,b'',0xffffffff,()),),(TxOutput(i+1,self.script),),0) for i in range(4))
        three=self.make(self.two,3,transactions=txs);self.add(three,3);self.c.commit();self.explorer.refresh(force=True)
        for tx in three.transactions:
            proof=self.explorer.run('proof',hash_to_display(tx.txid()))
            self.assertTrue(proof['proof_valid']);self.assertTrue(verify_merkle_proof(proof))
            self.assertEqual(len(proof['siblings']),3)

    def test_tampered_merkle_proof_is_rejected(self):
        proof=self.explorer.run('proof',hash_to_display(self.tx.txid()))
        changes=[('txid','0'*64),('merkle_root','0'*64),('block_hash','0'*64),
                 ('transaction_index',-1),('transaction_index',True),('transaction_count',0),
                 ('siblings',['0'*64]),('siblings',proof['siblings']+['0'*64]),('header_hex','00')]
        for key,value in changes:
            altered=copy.deepcopy(proof);altered[key]=value;self.assertFalse(verify_merkle_proof(altered),(key,value))
        for invalid in [None,[],{},'garbage']:self.assertFalse(verify_merkle_proof(invalid))

    def test_unknown_or_missing_proof_format_is_rejected(self):
        proof=self.explorer.run('proof',hash_to_display(self.tx.txid()))
        for value in [None,'different-protocol-v1',1,[],{}]:
            altered=copy.deepcopy(proof);altered['format']=value
            self.assertFalse(verify_merkle_proof(altered))
        proof.pop('format');self.assertFalse(verify_merkle_proof(proof))

    def test_missing_and_nonbinary_raw_block_are_data_failures(self):
        for raw in [None,'not binary',b'broken']:
            self.c.execute('UPDATE blocks SET raw=? WHERE hash=?',(raw,self.two.block_hash()));self.c.commit()
            with self.assertRaises(DataUnavailable):self.explorer.run('raw_block','2')
        self.c.execute('DELETE FROM blocks WHERE hash=?',(self.two.block_hash(),));self.c.commit()
        with self.assertRaises(DataUnavailable):self.explorer.run('raw_block','2')

    def test_reorg_invalidates_proof_and_export_but_recovers(self):
        old=self.explorer.snapshot
        fork=self.make(self.one,2,nonce=91);self.add(fork,2)
        self.c.execute('DELETE FROM utxos');self.c.commit();self.explorer.refresh(force=True)
        with self.assertRaises(SnapshotChanged):self.explorer.run('export_statistics',24,snapshot=old)
        with self.assertRaises(NotFound):self.explorer.run('proof',hash_to_display(self.tx.txid()))
        proof=self.explorer.run('proof',hash_to_display(fork.transactions[0].txid()))
        self.assertTrue(verify_merkle_proof(proof))
        exported=self.explorer.run('export_blocks',1)['data'].decode('utf-8-sig')
        self.assertIn(hash_to_display(fork.block_hash()),exported)
        self.assertNotIn(hash_to_display(self.two.block_hash()),exported)

    def test_disconnected_client_does_not_receive_second_response(self):
        handler=Handler.__new__(Handler)
        handler.server=SimpleNamespace(server_port=9876,explorer=self.explorer)
        handler.headers={'Host':'127.0.0.1:9876'};handler.path='/api/overview'
        with patch.object(handler,'respond',side_effect=BrokenPipeError()) as respond:
            handler.do_GET()
        self.assertEqual(respond.call_count,1)

    def test_all_downloads_reject_old_snapshots_after_change(self):
        old=self.explorer.snapshot
        three=self.make(self.two,3);self.add(three,3);self.c.commit();self.explorer.refresh(force=True)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.explorer=self.explorer
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        paths=['/api/block/2/raw','/api/transaction/'+hash_to_display(self.tx.txid())+'/raw',
               '/api/transaction/'+hash_to_display(self.tx.txid())+'/proof?download=1',
               '/api/export/blocks.csv?limit=1','/api/export/address/'+self.address,'/api/statistics/export?limit=24']
        try:
            for path in paths:
                for snapshot,status in [(old,409),(self.explorer.snapshot,200)]:
                    conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
                    conn.request('GET',path+('&' if '?' in path else '?')+'snapshot='+snapshot)
                    result=conn.getresponse();raw=result.read();conn.close()
                    self.assertEqual(result.status,status,path)
                    if status==409:
                        self.assertEqual(json.loads(raw)['code'],'snapshot_changed')
                        self.assertIsNone(result.getheader('Content-Disposition'))
        finally:server.shutdown();server.server_close();thread.join()

    def test_pending_transaction_has_no_block_proof(self):
        self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(1,self.tx.txid(),self.tx.serialize()))
        # Use a distinct ID so the transaction is genuinely absent from confirmed history.
        self.c.execute('DELETE FROM mempool')
        tx=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,()),),(TxOutput(1,self.script),),0)
        self.c.execute('INSERT INTO mempool VALUES (?,?,?)',(1,tx.txid(),tx.serialize()));self.c.commit();self.explorer.refresh(force=True)
        with self.assertRaises(NotFound):self.explorer.run('proof',hash_to_display(tx.txid()))

    def test_raw_reads_detect_body_corruption_after_indexing(self):
        altered=Transaction(2,self.two.transactions[0].inputs,(TxOutput(1,self.script),),0)
        broken=Block(self.two.header,(altered,self.tx))
        self.c.execute('UPDATE blocks SET raw=? WHERE hash=?',(broken.serialize(),self.two.block_hash()));self.c.commit()
        with self.assertRaises(DataUnavailable):self.explorer.run('raw_block','2')

    def test_statistics_range_and_negative_timestamp_interval(self):
        data=self.explorer.run('statistics',144)
        self.assertEqual(data['block_count'],3);self.assertEqual(data['ordinary_transactions'],1)
        self.assertIsNone(data['points'][0]['interval_seconds']);self.assertEqual(data['points'][1]['interval_seconds'],600)
        self.assertTrue(all(p['difficulty_ratio']==1 for p in data['points']))
        self.assertEqual(self.explorer.run('statistics',1)['points'][0]['interval_seconds'],600)
        three=self.make(self.two,3)
        h=three.header;three=Block(Header(h.version,h.previous_hash,h.merkle_root,self.two.header.timestamp-10,h.bits,h.nonce),three.transactions)
        self.add(three,3);self.c.commit();self.explorer.refresh(force=True)
        self.assertEqual(self.explorer.run('statistics',1)['points'][0]['interval_seconds'],-10)

    def test_csv_exports_preserve_amounts_and_utc_timestamps(self):
        def rows(result):
            self.assertTrue(result['data'].startswith(b'\xef\xbb\xbf'))
            return list(csv.DictReader(io.StringIO(result['data'].decode('utf-8-sig'))))
        blocks=rows(self.explorer.run('export_blocks',2));self.assertEqual([r['height'] for r in blocks],['2','1'])
        self.assertTrue(blocks[0]['timestamp_utc'].endswith('+00:00'))
        history=rows(self.explorer.run('export_address',encode_address(self.recipient,network=SUMUWW)))
        self.assertEqual(history[0]['net_change_SMW'],'49.00000000')
        statistics=rows(self.explorer.run('export_statistics',1));self.assertEqual(statistics[0]['height'],'2')

    def test_new_endpoint_limits_are_bounded(self):
        for limit in [0,2017]:
            with self.assertRaises(ValueError):self.explorer.run('statistics',limit)
        for limit in [0,10001]:
            with self.assertRaises(ValueError):self.explorer.run('export_blocks',limit)
            with self.assertRaises(ValueError):self.explorer.run('export_address',self.address,limit)

    def test_new_http_download_routes(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.explorer=self.explorer
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            txid=hash_to_display(self.tx.txid())
            for path,attachment in [('/api/block/2/raw',True),('/api/transaction/'+txid+'/raw',True),
                  ('/api/transaction/'+txid+'/proof',False),('/api/transaction/'+txid+'/proof?download=1',True),
                  ('/api/export/blocks.csv?limit=2',True),('/api/export/address/'+self.address,True),
                  ('/api/statistics?limit=1',False),('/api/statistics/export?limit=1',True)]:
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port);conn.request('GET',path)
                r=conn.getresponse();self.assertEqual(r.status,200,path)
                self.assertEqual(r.getheader('Content-Disposition') is not None,attachment,path)
                data=r.read();self.assertTrue(data);conn.close()
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main(verbosity=2)
