import gc,tempfile,time,tkinter as tk,unittest
from pathlib import Path
from unittest.mock import Mock
from sumuww.network_monitor_ui import NetworkMonitorApp
from sumuww.i18n import LANGUAGES,Translator,set_translator


class NetworkMonitorUiTests(unittest.TestCase):
    def test_all_languages_show_grouped_network_response_and_updates_without_miner_status(self):
        with tempfile.TemporaryDirectory(prefix='sumuww-network-ui-') as temporary:
            root=tk.Tk();root.withdraw();survey=Mock();survey.stopped=True
            node={'peer_id':'0123456789abcdef','addresses':['[2001:4860::1]:18444','[2001:4860::2]:18444'],
                  'height':7642,'tip':'a'*64,'tip_pow_merkle_checked':True,'tip_updates':1,'seen':time.time()}
            value={'running':True,'nodes':[node],'candidates':3,'checking':0,'error':None}
            survey.snapshot.side_effect=lambda:value
            try:
                app=NetworkMonitorApp(root,Path(temporary),survey=survey)
                for code,name in LANGUAGES:
                    app.language.set(name);app._language();root.update_idletasks()
                    self.assertEqual(len(app.table.get_children()),1)
                    row=app.table.item(app.table.get_children()[0],'values')
                    self.assertEqual(row[0],node['peer_id']);self.assertEqual(row[2],'7642')
                    self.assertEqual(row[5],'1');self.assertIn(node['addresses'][1],row[1])
                    for key in ('SUMUWW Network Monitor','Direct network responses; discovered peers only. Mining status is not observable.',
                                'Responding nodes: {0} | Discovered addresses: {1} | Checking: {2}',
                                'Tip hash, PoW and Merkle checked','Last response','Tip updates'):
                        self.assertIn(key,app.translator.catalog(code))
                value['nodes']=[];app.refresh();self.assertFalse(app.table.get_children())
                app.request_refresh();survey.request_refresh.assert_called_once()
                self.assertEqual(survey.start.call_count,1)
                app._close();self.assertTrue(survey.stop.called)
            finally:
                root.update_idletasks();root.destroy();del app;del root;gc.collect();set_translator(Translator('en'))


if __name__=='__main__':unittest.main()
