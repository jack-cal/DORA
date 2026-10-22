"""Isolated analytics, history, observation and PDF regression checks."""
import io
import json
import sqlite3
import unittest
import threading
import http.client
from contextlib import closing
from pathlib import Path
from pypdf import PdfReader
import test_explorer as fixtures
from server import Explorer, ExplorerHTTPServer, Handler
from sumuww.primitives import hash_to_display
from sumuww.address import encode_address
from sumuww.transaction import Transaction,TxInput,TxOutput
from analytics import checked_filters, units
from reports import make_pdf

class AdvancedTests(unittest.TestCase):
    setUp=fixtures.ExplorerTests.setUp
    tearDown=fixtures.ExplorerTests.tearDown
    make=fixtures.ExplorerTests.make
    add=fixtures.ExplorerTests.add

    def pool(self,tx):
        self.c.execute('INSERT INTO mempool(txid,raw) VALUES (?,?)',(tx.txid(),tx.serialize()));self.c.commit()
        self.explorer.refresh(force=True)

    def test_fee_samples_and_exact_virtual_size(self):
        data=self.explorer.run('fee_analysis')
        self.assertEqual(data['total'],0);self.assertEqual(data['sample_count'],1)
        detail=self.explorer.run('transaction',hash_to_display(self.tx.txid()))
        self.assertEqual(detail['vsize'],(self.tx.weight()+3)//4)
        self.assertAlmostEqual(float(detail['fee_rate']),100000000/detail['vsize'],7)
        self.assertEqual(len(data['recommendations']),3)
        related=self.explorer.run('related',detail['txid'])
        self.assertEqual(related['package_fee'],detail['fee']);self.assertEqual(related['package_vsize'],detail['vsize'])

    def test_pending_packages_and_relations(self):
        first=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xfffffffd,()),),(TxOutput(4800000000,self.recipient),),0)
        second=Transaction(2,(TxInput(first.txid(),0,b'',0xffffffff,()),),(TxOutput(4600000000,self.script),),0)
        self.pool(first);self.pool(second)
        firstid,secondid=map(lambda t:hash_to_display(t.txid()),[first,second])
        data=self.explorer.run('fee_analysis');self.assertEqual(data['total_known_fees'],'3.00000000')
        child=next(r for r in data['transactions'] if r['txid']==secondid)
        self.assertEqual(child['package_fee'],'3.00000000');self.assertEqual(child['ancestors'],[firstid])
        self.assertLess(data['projected'].index(firstid),data['projected'].index(secondid))
        relation=self.explorer.run('related',firstid)
        self.assertEqual(relation['children'],[secondid]);self.assertTrue(relation['rbf_signal'])
        self.assertFalse(relation['replacement_policy_verified'])
        self.assertEqual(self.explorer.run('transaction',firstid)['fee'],'1.00000000')

    def test_unknown_pending_fee_is_not_zero(self):
        unknown=Transaction(2,(TxInput(b'\x99'*32,0,b'',0xffffffff,()),),(TxOutput(1,self.recipient),),0)
        self.pool(unknown);data=self.explorer.run('fee_analysis')
        self.assertEqual(data['unresolved_fees'],1);self.assertIsNone(data['transactions'][0]['fee'])
        self.assertNotIn(hash_to_display(unknown.txid()),data['projected'])

    def test_zero_fee_is_a_real_sample(self):
        zero=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,()),),(TxOutput(4900000000,self.recipient),),0)
        self.pool(zero);self.assertEqual(self.explorer.run('transaction',hash_to_display(zero.txid()))['fee_rate'],'0.00000000')

    def test_projection_budget_many_independent_transactions(self):
        from analytics import BLOCK_BUDGET
        model={str(i):{'fee_units':i,'weight':4000,'vsize':1000,'parents':[],'ancestors':[],'descendants':[],
            'package_fee_units':i} for i in range(2000)}
        selected,weight=self.explorer.projected_transactions(model)
        self.assertLessEqual(weight,BLOCK_BUDGET);self.assertEqual(len(selected),BLOCK_BUDGET//4000)
        self.assertEqual(selected[0],'1999');self.assertEqual(selected[-1],str(2000-len(selected)))

    def test_date_period_and_running_balance_pagination(self):
        from datetime import datetime,timezone
        date=datetime.fromtimestamp(self.two.header.timestamp,timezone.utc).date().isoformat()
        result=self.explorer.run('ledger',self.address,{'date_from':date,'date_to':date})
        self.assertEqual(result['closing_balance'],'50.00000000')
        first=self.explorer.run('ledger',self.address,{},0,1)
        second=self.explorer.run('ledger',self.address,{},1,1)
        self.assertEqual(first['transactions'][0]['balance_after'],'50.00000000')
        self.assertEqual(second['transactions'][0]['balance_after'],'100.00000000')

    def test_no_samples_do_not_invent_recommendation(self):
        with closing(self.explorer.connect_index()) as c,c:c.execute('DELETE FROM blocks WHERE height>0')
        # Read directly because the source still contains the fixture blocks.
        with closing(self.explorer.connect_index()) as c:data=self.explorer.fee_analysis(c)
        self.assertTrue(all(r['fee_rate'] is None for r in data['recommendations']))

    def test_filtered_sort_and_amount_precision(self):
        result=self.explorer.run('transactions','all',0,{'min_amount':'49','max_amount':'49','sort':'fee','order':'asc'})
        self.assertEqual(result['total'],1);self.assertEqual(result['transactions'][0]['txid'],hash_to_display(self.tx.txid()))
        self.assertEqual(units('0.00000001'),1)
        for filters in [{'sort':'height;DELETE FROM txs'},{'order':'sideways'},{'min_height':'-1'},{'min_amount':'1e-8'}, {'min_amount':'0.000000001'},{'date_from':'2026-99-99'},{'min_height':'2','max_height':'1'}]:
            with self.subTest(filters=filters),self.assertRaises(ValueError):checked_filters(filters)

    def test_historical_balance_and_period_reconciliation(self):
        result=self.explorer.run('ledger',self.address)
        self.assertEqual(result['closing_balance'],'50.00000000')
        self.assertEqual(self.explorer.run('past_balance',self.address,1)['balance'],'50.00000000')
        recipient=encode_address(self.recipient,network=__import__('server').SUMUWW)
        self.assertEqual(self.explorer.run('past_balance',recipient,1)['balance'],'0.00000000')
        self.assertEqual(self.explorer.run('past_balance',recipient,2)['balance'],'49.00000000')
        period=self.explorer.run('ledger',self.address,{'min_height':'2','max_height':'2'})
        self.assertEqual(period['opening_balance'],'50.00000000');self.assertEqual(period['net_change'],'0.00000000')
        self.assertEqual(period['transactions'][0]['balance_after'],'50.00000000')
        self.assertEqual(period['transactions'][1]['balance_after'],'100.00000000')
        self.assertEqual(period['points'][-1]['balance'],period['closing_balance'])

    def test_genesis_and_empty_range(self):
        self.assertEqual(self.explorer.run('past_balance',self.address,0)['balance'],'0.00000000')
        result=self.explorer.run('ledger',self.address,{'min_height':'999'})
        self.assertEqual(result['total'],0);self.assertEqual(result['opening_balance'],result['closing_balance'])
        with self.assertRaises(ValueError):self.explorer.run('past_balance',self.address,3)

    def test_observation_created_before_block_only_and_removed_on_reorg(self):
        self.assertFalse(self.explorer.run('block_audit','2')['available'])
        nextblock=self.make(self.two,3);self.add(nextblock,3);self.c.commit();self.explorer.refresh(force=True)
        data=self.explorer.run('block_audit','3');self.assertTrue(data['available']);self.assertEqual(data['actual'],[])
        self.c.execute("UPDATE metadata SET value=? WHERE name='tip'",(self.two.block_hash(),));self.c.commit();self.explorer.refresh(force=True)
        with closing(self.explorer.connect_index()) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM block_audits').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT count(*) FROM observations WHERE parent=?',(hash_to_display(nextblock.block_hash()),)).fetchone()[0],0)

    def test_observed_pending_transaction_matches_actual_block(self):
        tx=Transaction(2,(TxInput(self.tx.txid(),0,b'',0xffffffff,()),),(TxOutput(4800000000,self.script),),0)
        self.pool(tx);txid=hash_to_display(tx.txid())
        block=self.make(self.two,3,transactions=(tx,));self.add(block,3)
        self.c.execute('DELETE FROM mempool');self.c.commit();self.explorer.refresh(force=True)
        result=self.explorer.run('block_audit','3')
        self.assertEqual(result['expected'],[txid]);self.assertEqual(result['actual'],[txid])
        self.assertEqual(result['match_percent'],100);self.assertEqual(result['unseen'],[])

    def test_legacy_index_migrates(self):
        self.explorer.close()
        with closing(sqlite3.connect(self.root/'explorer.sqlite')) as c,c:
            c.execute('DROP TABLE block_audits');c.execute('DROP TABLE observations');c.execute('PRAGMA user_version=1')
        self.explorer=Explorer(self.db,self.root/'explorer.sqlite')
        self.assertEqual(self.explorer.run('overview')['height'],2)
        with closing(self.explorer.connect_index()) as c:self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],3)

    def test_mining_statistics_next_bits_and_distribution(self):
        result=self.explorer.run('mining_analysis',24)
        self.assertGreater(result['estimated_hashrate'],0);self.assertEqual(result['next_bits'],f'{self.two.header.bits:08x}')
        self.assertEqual(result['known_fees'],'1.00000000');self.assertTrue(result['payouts_are_not_miner_identities'])
        for limit in (0,1,2017):
            with self.assertRaises(ValueError):self.explorer.run('mining_analysis',limit)

    def test_pdf_receipt_exact_hash_and_amounts(self):
        txid=hash_to_display(self.tx.txid());data=self.explorer.run('receipt',txid,'en');raw=make_pdf(data)
        self.assertTrue(raw.startswith(b'%PDF-'));reader=PdfReader(io.BytesIO(raw));text=''.join(p.extract_text() for p in reader.pages)
        self.assertIn('49.00000000',text);self.assertIn(''.join(txid.split()),''.join(text.split()))
        self.assertIn('Not a signed payment',text)

    def test_localized_pdf_documents_and_unknown_language(self):
        for language in ('ko','ja','ar','hi','bn','ta','th','zh','zh-TW','zh-HK'):
            with self.subTest(language=language):
                raw=make_pdf(self.explorer.run('address_report',self.address,{},language));self.assertGreater(len(raw),5000)
                self.assertIn('50.00000000',''.join(p.extract_text() for p in PdfReader(io.BytesIO(raw)).pages))
        with self.assertRaises(ValueError):make_pdf(self.explorer.run('receipt',hash_to_display(self.tx.txid()),'xx'))

    def test_advanced_http_routes_validation_and_pdf_downloads(self):
        server=ExplorerHTTPServer(('127.0.0.1',0),Handler);server.explorer=self.explorer
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        txid=hash_to_display(self.tx.txid())
        cases=[('/api/fees',200),('/api/mining?limit=24',200),('/api/mining?limit=1',400),
            ('/api/transaction/'+txid+'/related',200),('/api/block/2/audit',200),
            ('/api/address/'+self.address+'/history?max_height=1',200),('/api/address/'+self.address+'/balance?at_height=3',400),
            ('/api/transactions?min_amount=49&max_amount=49',200),('/api/transactions?sort=bogus',400),
            ('/api/transactions?sort=fee&sort=rate',400),('/api/transaction/'+txid+'/receipt?lang=en',200),
            ('/api/address/'+self.address+'/report?lang=ko',200),('/api/report/transactions?lang=en',200),
            ('/api/transaction/'+txid+'/receipt?lang=en&snapshot='+'0'*64,409),
            ('/api/export/transactions.csv?min_amount=49&max_amount=49',200),('/advanced.js',200)]
        try:
            for path,status in cases:
                with self.subTest(path=path):
                    conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=15);conn.request('GET',path)
                    response=conn.getresponse();raw=response.read();self.assertEqual(response.status,status,raw[:500]);conn.close()
                    if status==200 and ('/receipt?' in path or '/report?' in path or '/report/transactions' in path):
                        self.assertTrue(raw.startswith(b'%PDF-'));self.assertEqual(response.getheader('Content-Type'),'application/pdf')
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
