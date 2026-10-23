from concurrent.futures import Future
from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from sumuww.app import SumuwwApp
from sumuww.i18n import LANGUAGES,Translator,set_translator
from test_app_history_v31 import HistoryFixtureService

class BlockBrowserUiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=tk.Tk();self.root.withdraw()
        self.service=HistoryFixtureService(Path(self.temp.name)/'unused')
        self.service.status_value['wallet']=None
        def query(offset=0,limit=50,height=None):
            if height is not None:offset=103-height
            rows=[{'height':h,'hash':f'{h:064x}','timestamp':1792677600-h*600,
                   'producer_id':'11'*32,'origin':'local' if h%2 else 'other'} for h in range(103-offset,max(-1,103-offset-limit),-1)]
            future=Future();future.set_result({'blocks':rows,'offset':offset,'total':104,'height':103});return future
        self.service.block_history=query
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
            self.assertIn(str(self.app.translator.render('All blocks')),self.browser.title())
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
