"""Localized monitor controls stay reachable and never query on language changes."""
from concurrent.futures import Future
from pathlib import Path
import sys,tempfile,time,tkinter as tk,unittest
from tkinter import ttk
from unittest.mock import Mock,patch

from sumuww.i18n import LANGUAGES,LANGUAGE_CODES,Translator,load_language,set_translator
from sumuww.node_manager import NodeManagerApp,NodeMonitor
from sumuww.vertical_text import VerticalLabel,VerticalTreeview


@unittest.skipUnless(sys.platform=='win32','Windows complex-script renderer')
class MonitorLocaleLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='sumuww-monitor-layout-')
        self.monitor=NodeMonitor(Path(self.temporary.name),network='regtest',peers=[])
        self.root=tk.Tk();self.root.withdraw()
        self.app=NodeManagerApp(self.root,self.monitor)
        self.callbacks=[]
        self.root.report_callback_exception=lambda *args:self.callbacks.append(args)

    def tearDown(self):
        self.monitor.close();self.root.update_idletasks();self.root.destroy();self.temporary.cleanup()
        set_translator(Translator('en'))

    def language(self,code):
        self.app.language.set(dict(LANGUAGES)[code]);self.app._change_language()
        self.root.update_idletasks()
        self.assertFalse(self.callbacks)

    def pump(self,condition,timeout=2):
        deadline=time.monotonic()+timeout
        while not condition():
            self.root.update();time.sleep(.005)
            if time.monotonic()>deadline:self.fail('Monitor UI callback deadline')
        self.assertFalse(self.callbacks)

    def results(self,count=1):
        return [{'endpoint':f'127.0.0.1:{18444+n}','status':'reachable',
                 'advertised_tip':'a'*64,'latency_ms':n+1,
                 'reason':'SUMUWW identity handshake passed','discovered_peers':[]}for n in range(count)]

    def test_every_language_switch_away_back_preserves_pending_state_and_fits_controls(self):
        self.root.deiconify()
        future=Future();self.app._future=future
        self.app.peers.set('127.0.0.1:18444');self.app.internet.set(True);self.app.lan.set(True)
        self.monitor.results=self.results()
        controls=tuple(self.app._control_widgets)
        with patch.object(self.monitor,'check')as query:
            for width in (960,1100,1440):
                self.root.geometry(f'{width}x600')
                for code in LANGUAGE_CODES:
                    for selected in (code,'en',code):
                        with self.subTest(width=width,language=selected):
                            self.language(selected)
                            self.assertEqual(selected,load_language(self.app._language_path))
                            self.assertEqual('127.0.0.1:18444',self.app.peers.get())
                            self.assertTrue(self.app.internet.get()and self.app.lan.get())
                            self.assertIs(future,self.app._future)
                            self.assertEqual(controls,tuple(self.app._control_widgets))
                            row=self.app.table.item(self.app.table.get_children()[0],'values')
                            self.assertEqual('127.0.0.1:18444',row[0]);self.assertEqual('a'*64,row[3])
                            for button in controls:
                                self.assertTrue(button.winfo_ismapped(),str(button.cget('text')))
                                self.assertGreaterEqual(button.winfo_width()+2,button.winfo_reqwidth())
                                self.assertGreaterEqual(button.winfo_height()+2,button.winfo_reqheight())
                                self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),
                                                     self.app._canvas.winfo_rootx()+self.app._canvas.winfo_width()+2)
                                host=button.grid_info()['in']
                                stacking=self.app._controls.winfo_children()
                                self.assertGreater(stacking.index(button),stacking.index(host))
            query.assert_not_called()

    def test_mongolian_uses_vertical_captions_and_table_and_can_scroll_to_last_content(self):
        self.monitor.results=self.results(8)
        self.root.geometry('960x540');self.root.deiconify();self.language('mn-Mong')
        self.assertIsInstance(self.app.table,VerticalTreeview)
        self.assertTrue(self.app.table._heading_images)
        for widget,_key in self.app._texts:
            self.assertIsNotNone(widget._vertical_image)
        self.assertIsNotNone(self.app._status_label._vertical_image)
        self.assertEqual('SUMUWW',self.root.title())
        self.app.table.yview_moveto(1);self.root.update_idletasks()
        self.assertTrue(self.app.table.bbox(self.app.table.get_children()[-1]))
        self.app._canvas.yview_moveto(1);self.root.update_idletasks()
        self.assertGreater(self.app._canvas.yview()[0],0)
        note=self.app._note_labels[-1]
        self.assertLessEqual(note.winfo_rooty()+note.winfo_height(),
                             self.app._canvas.winfo_rooty()+self.app._canvas.winfo_height()+2)
        self.language('en')
        self.assertFalse(self.app.table._heading_images)
        self.assertIsNone(self.app._status_label._vertical_image)
        for widget,_key in self.app._texts:self.assertIsNone(widget._vertical_image)

    def test_check_load_and_open_callbacks_recover_in_every_language(self):
        self.root.deiconify()
        for code in LANGUAGE_CODES:
            with self.subTest(language=code):
                self.language(code)
                self.app.peers.set('127.0.0.1:18444')
                self.monitor.results=self.results()
                done=Future();done.set_result(self.monitor.results)
                with patch.object(self.monitor,'check',return_value=done)as query:
                    self.app.check_button.invoke()
                    self.assertEqual('disabled',str(self.app.check_button.cget('state')))
                    self.pump(lambda:self.app._future is None)
                    query.assert_called_once()
                for control in (self.app.check_button,self.app.load_button,self.app.peer_entry):
                    self.assertEqual('normal',str(control.cget('state')))
                with patch.object(self.monitor,'load_saved',wraps=self.monitor.load_saved)as load:
                    self.app.load_button.invoke();load.assert_called_once()
                process=Mock();process.poll.return_value=None
                with patch('sumuww.node_manager.subprocess.Popen',return_value=process)as launch:
                    self.app.open_button.invoke();self.app.open_button.invoke();launch.assert_called_once()
                    process.poll.return_value=0
                    self.pump(lambda:self.app._sumuww_process is None)
                self.assertEqual('normal',str(self.app.open_button.cget('state')))
        self.assertFalse(list(Path(self.temporary.name).rglob('*.sqlite')))

    def test_resizing_does_not_change_permission_values_or_start_a_check(self):
        self.root.deiconify();self.language('ta')
        self.app.internet.set(True);self.app.lan.set(False)
        self.app.peers.set('127.0.0.1:18444')
        with patch.object(self.monitor,'check')as query:
            for width in (1440,960,1100,960):
                self.root.geometry(f'{width}x540');self.root.update_idletasks()
                self.assertTrue(self.app.internet.get());self.assertFalse(self.app.lan.get())
                self.assertEqual('127.0.0.1:18444',self.app.peers.get())
            query.assert_not_called()

    def test_alias_addresses_count_one_node_and_changed_inputs_clear_results(self):
        self.language('en')
        rows=self.results(2)
        for row in rows:row['peer_id']='1234567890abcdef'
        self.monitor.results=rows;self.app._show_results()
        self.assertIn('Responding addresses: 2',self.app.status.get())
        self.assertIn('Distinct nodes: 1',self.app.status.get())
        self.assertEqual(len(self.app.table.get_children()),1)
        for item in self.app.table.get_children():
            self.assertEqual(self.app.table.item(item,'values')[1],'1234567890abcdef')
            addresses=self.app.table.item(item,'values')[0]
            self.assertIn('127.0.0.1:18444',addresses);self.assertIn('127.0.0.1:18445',addresses)
        self.app.peers.set('127.0.0.1:18446')
        self.assertEqual(self.monitor.results,[]);self.assertFalse(self.app.table.get_children())

    def test_load_saved_never_retains_previous_query_results(self):
        self.monitor.results=self.results(2);self.app._show_results()
        self.app._load_saved()
        self.assertEqual(self.monitor.results,[]);self.assertFalse(self.app.table.get_children())


if __name__=='__main__':unittest.main()
