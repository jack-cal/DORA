import unittest
from pathlib import Path
from tests import test_i18n
from sumuww.brand import artwork
from sumuww.i18n import LANGUAGE_CODES, load_language


class LocaleBrandTests(unittest.TestCase):
    setUp = test_i18n.UiLanguageSwitchTests.setUp
    tearDown = test_i18n.UiLanguageSwitchTests.tearDown

    def test_live_language_switch_refreshes_logo_and_preserves_wallet_and_inputs(self):
        wallet = dict(self.app._wallet)
        self.app.send_amount.set('1.25')
        self.app._mining = self.app._mine_inflight = True
        for code in ('en', 'ko', 'ar', 'en', 'ar', 'ko'):
            with self.subTest(language=code):
                self.assertTrue(self.app.set_language(code))
                self.root.update_idletasks()
                logo_path = self.root.tk.call(str(self.app._logo), 'cget', '-file')
                self.assertEqual(artwork(code, scale=self.app._layout_scale).resolve(), Path(logo_path).resolve())
                self.assertEqual(str(self.app._logo), str(self.app._logo_label.cget('image')[0]))
                if __import__('sys').platform == 'win32':
                    self.assertEqual(str(artwork(code, 'ico').resolve()), self.root._sumuww_native_icon_identity[0])
                else:
                    window_path = self.root.tk.call(str(self.root._sumuww_language_icon), 'cget', '-file')
                    self.assertEqual(artwork(code, 'window').resolve(), Path(window_path).resolve())
                self.assertEqual(code, load_language(self.path))
                self.assertEqual(wallet, self.app._wallet)
                self.assertEqual('1.25', self.app.send_amount.get())
                self.assertTrue(self.app._mining and self.app._mine_inflight)

    def test_other_languages_restore_original_artwork(self):
        original = artwork('en')
        for code in LANGUAGE_CODES:
            self.assertTrue(artwork(code).is_file())
            if code not in ('ko', 'ar'):
                self.assertEqual(original, artwork(code))
        self.assertNotEqual(artwork('ko'), artwork('ar'))

    def test_arabic_readability_and_larger_native_resolution_logo_restore_on_switch(self):
        from tkinter import font as tkfont
        self.assertTrue(self.app.set_language('ar'))
        font=tkfont.Font(root=self.root,font=self.app._style.lookup('TLabel','font'))
        self.assertEqual('Tahoma',font.actual('family'))
        self.assertGreaterEqual(font.actual('size'),13)
        self.assertGreaterEqual(int(self.app._style.lookup('Treeview','rowheight')),32)
        self.assertGreaterEqual(self.app._logo.width(),180)
        self.assertGreaterEqual(self.app._logo.height(),104)
        for scale in (1,1.25,1.5,2):
            image=__import__('tkinter').PhotoImage(master=self.root,file=str(artwork('ar',scale=scale)))
            self.assertEqual(round(180*scale),image.width())
        self.assertTrue(self.app.set_language('en'))
        font=tkfont.Font(root=self.root,font=self.app._style.lookup('TLabel','font'))
        self.assertEqual(10,font.actual('size'))
        self.assertEqual('#647086',self.app._style.lookup('Muted.TLabel','foreground'))
