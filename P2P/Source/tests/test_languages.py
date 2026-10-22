import json,tempfile,unittest,gc
from pathlib import Path
import tkinter as tk
from smw_trade.app import Application
from smw_trade.desktop import Desktop
from smw_trade.localization import Localizer
ROOT=Path(__file__).resolve().parents[1]
class LanguageTests(unittest.TestCase):
 def test_defaults_catalog_coverage_and_saved_choice(self):
  with tempfile.TemporaryDirectory() as folder:
   l=Localizer(folder);self.assertEqual(l.code,'en');self.assertEqual(len(l.languages),34)
   en=json.loads((l.folder/'en.json').read_text(encoding='utf8'))
   for code in l.languages:
    catalog=json.loads((l.folder/(code+'.json')).read_text(encoding='utf8'))
    self.assertEqual(set(en),set(catalog),code)
    self.assertTrue(all(v.strip() for v in catalog.values()),code)
    l.set(code);self.assertEqual(Localizer(folder).code,code)
   l.settings.write_text('{"language":"bad"}')
   self.assertEqual(Localizer(folder).code,'en')
 def test_all_native_language_switches_preserve_order_side_fields_and_records(self):
  with tempfile.TemporaryDirectory() as folder:
   app=Application(ROOT,Path(folder)/'data');root=tk.Tk();root.withdraw();ui=Desktop(app,window=root)
   try:
    ui.smw.set('12.00000001');ui.btc.set('0.0002');ui.port.set('18444')
    ui.side.set(ui.tr('Buy SMW'))
    before=app.store.listing()
    for code,name in ui.localization.languages.items():
     ui.language_choice.set(name);ui.change_language();root.update()
     self.assertEqual(ui.localization.code,code)
     self.assertEqual(ui.tabs.tab(0,'text'),ui.tr('Market'))
     self.assertEqual(ui.create_button.cget('text'),ui.tr('Publish test order'))
     self.assertEqual(ui.smw.get(),'12.00000001');self.assertEqual(ui.btc.get(),'0.0002')
     self.assertEqual(ui.side.get(),ui.tr('Buy SMW'))
     self.assertEqual(ui.port.get(),'18444');self.assertEqual(app.store.listing(),before)
    ui.create_button.invoke()
    import time
    deadline=time.monotonic()+10
    while ui.busy and time.monotonic()<deadline:root.update();time.sleep(.02)
    self.assertFalse(ui.busy)
    order=app.store.listing()[0];self.assertEqual(order['side'],'buy');self.assertEqual(order['smw'],'12.00000001')
   finally:
    ui.close()
    import time
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
     try:root.update();exists=root.winfo_exists()
     except tk.TclError:exists=False
     if not exists:break
     time.sleep(.02)
    app.close();del ui;del root;gc.collect()
