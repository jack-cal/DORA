from concurrent.futures import Future
from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from sumuww.app import SumuwwApp
from sumuww.i18n import LANGUAGES,Translator,set_translator
from tests.test_app_history_v31 import HistoryFixtureService

class BlockBrowserUiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=tk.Tk();self.root.withdraw()
        self.service=HistoryFixtureService(Path(self.temp.name)/'unused')
        self.service.status_value['wallet']=None
        def query(offset=0,limit=50,height=None):
            if height is not None:offset=103-height
            rows=[{'height':h,'hash':f'{h:064x}','timestamp':1792677600-h*600,
                   'producer_id':'11'*32,'origin':'local' if h%2 else 'other'} for h in range(103-offset,max(-1,103-offset-limit),-1)]
            future=Future();future.set_result({'blocks':rows,'offset':offset,'total':104,'height':103,
                'stored_proofs':0,'lottery_jobs':{'total':54,'not_selected':45,'awaiting_lottery':0,'selected_pending':9,'selected_complete':0}});return future
        self.service.block_history=query
        def transactions(digest,offset=0,limit=50):
            future=Future();future.set_result({'block_hash':digest,'height':int(digest,16),'confirmations':1,
                'total':51,'offset':offset,'transactions':[
                    {'txid':f'{i:064x}','coinbase':i==0,'output_total':5000000000,
                     'inputs':[{'txid':'a'*64,'index':0}],
                     'outputs':[{'index':0,'value':5000000000,'address':'sumuww1qfixture','script':'0014'}]}
                    for i in range(offset,min(51,offset+limit))]});return future
        self.service.block_transactions=transactions
        self.app=SumuwwApp(self.root,self.service,language='en',language_path=Path(self.temp.name)/'language.json')
        self.app._started=True;self.app._apply_status(self.service.status_value)
        self.app.blocks_button.invoke();self.browser=self.app._blocks_dialog
    def tearDown(self):
        import gc
        if self.app._blocks_dialog:self.app._blocks_dialog.close()
        self.app._finish_close();self.browser=None;self.app=None;self.root=None;gc.collect()
        self.temp.cleanup();set_translator(Translator('en'))
    def test_all_languages_and_separate_mining_screen(self):
        for language,_ in LANGUAGES:
            self.app.set_language(language);self.root.update_idletasks()
            self.assertEqual(50,len(self.browser.table.get_children()))
            self.assertIn(str(self.app.translator.render('All history')),self.browser.title())
            for label in ('Local lottery jobs','Not selected','Selected pending','Selected complete'):
                self.assertIn(str(self.app.translator.render(label)),self.browser.state.get())
            self.assertFalse(hasattr(self.app,'network_blocks_table'))
        self.assertEqual(0,self.service.mine_calls)
    def test_previous_next_search_refresh_and_invalid_input(self):
        self.app._mine_completed=7
        self.browser.next.invoke();self.assertEqual(50,self.browser.offset)
        self.browser.next.invoke();self.assertEqual(4,len(self.browser.rows))
        self.assertEqual(0,self.browser.rows[-1]['height'])
        self.assertIn('disabled',self.browser.next.state())
        self.browser.previous.invoke();self.assertEqual(50,self.browser.offset)
        self.browser.query.set('0');self.browser.search_button.invoke()
        self.assertEqual([0],[r['height'] for r in self.browser.rows])
        self.browser.refresh.invoke();self.assertEqual(0,self.browser.offset)
        self.browser.query.set('-1');self.browser.search_button.invoke()
        self.assertIn('0–103',self.browser.state.get())
        self.assertEqual(7,self.app._mine_completed)

    def test_bottom_all_history_without_wallet_and_complete_transaction_pages(self):
        self.assertIn('disabled',self.app.history_button.state())
        self.assertNotIn('disabled',self.app.all_history_button.state())
        self.browser.close();self.app.all_history_button.invoke();self.browser=self.app._blocks_dialog
        key=self.browser.rows[0]['hash']
        self.browser.table.selection_set(key);self.browser.select_block()
        self.assertEqual(50,len(self.browser.transactions.get_children()))
        self.browser.transactions.focus('tx-0');self.browser.expand_transaction()
        self.assertEqual(1,len(self.browser.transactions.get_children('tx-0')))
        self.browser.tx_next.invoke()
        self.assertEqual(1,len(self.browser.transactions.get_children()))
        self.assertEqual(50,self.browser.detail['offset'])
        self.browser.next.invoke()
        self.assertIsNone(self.browser.detail)
        self.assertEqual(0,self.service.mine_calls)

    def test_block_reward_breakdown_and_outputs_expand_together(self):
        from sumuww.rewards import reward_amounts
        key=self.browser.rows[0]['hash']
        data=self.service.block_transactions(key).result()
        data['transactions'][0]['mining_reward']=reward_amounts(5_000_100_000,103,100_000)
        self.browser.detail=data;self.browser.render_transactions()
        self.assertFalse(self.browser.transactions.item('tx-0','open'))
        self.browser.transactions.focus('tx-0');self.browser.expand_transaction()
        children=self.browser.transactions.get_children('tx-0')
        self.assertEqual(4,len(children))
        values=[self.browser.transactions.item(child,'values')[0] for child in children]
        self.assertEqual(['50.00000000 SMW','0.00100000 SMW','50.00100000 SMW','50.00000000'],values)

    def test_late_transaction_response_cannot_replace_new_selection(self):
        pending=[]
        def request(*args):
            future=Future();pending.append(future);return future
        self.service.block_transactions=request
        self.browser.load_transactions(self.browser.rows[0]['hash'],0)
        first=self.browser.detail_generation
        self.browser.load_transactions(self.browser.rows[1]['hash'],0)
        pending[0].set_result({'bad':'old data'})
        self.browser.poll_transactions(pending[0],first)
        self.assertIsNone(self.browser.detail)
        self.browser.refresh.invoke()
        self.assertFalse(self.browser.detail_busy)
