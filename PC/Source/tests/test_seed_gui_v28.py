"""Exercise asynchronous seed creation and recovery through the actual Tk UI."""
import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from sumuww.app import SumuwwApp, _RecoveryPhraseDialog
from sumuww.app_service import AppService
from sumuww.i18n import Translator, set_translator
from sumuww.profiles import REGTEST

PASSWORD = 'temporary-gui-seed-password'


class SeedGuiTests(unittest.TestCase):
    def test_create_display_lock_and_recover_do_not_retain_phrase_in_ui_state(self):
        set_translator(Translator('en'))
        with tempfile.TemporaryDirectory(prefix='sumuww-seed-gui-') as directory:
            folder = Path(directory)
            try:
                root = tk.Tk()
            except tk.TclError as error:
                self.skipTest(f'Tk display unavailable: {error}')
            root.withdraw()
            service = AppService(folder / 'node', network=REGTEST, peers=[])
            service.start().result(timeout=10)
            app = SumuwwApp(root, service, language_path=folder / 'ui-language.json')
            app._started = True
            phrase_holder, displayed = [], []
            class FixtureDialog(_RecoveryPhraseDialog):
                def body(dialog, master):
                    widget = super().body(master)
                    def finish():
                        if dialog.readonly:
                            phrase_holder[:] = [dialog.phrase_text.get('1.0', 'end-1c')]
                            displayed.append(True)
                        else:
                            dialog.phrase_text.insert('1.0', phrase_holder[0])
                        dialog.ok()
                    dialog.after(0, finish)
                    return widget
            def pump():
                end = time.monotonic() + 20
                while app._busy or app._pending or app._dialog_open:
                    root.update()
                    if time.monotonic() >= end:
                        raise AssertionError('Asynchronous seed UI deadline exceeded')
                    time.sleep(.01)
                root.update()
            try:
                wallet, restored = folder / 'seed.json', folder / 'restored.json'
                with patch.object(app, '_choose_file', return_value=wallet), \
                        patch.object(app, '_password', return_value=PASSWORD), \
                        patch('sumuww.app._RecoveryPhraseDialog', FixtureDialog), \
                        patch('sumuww.app.messagebox.showerror') as errors:
                    app._create_seed_wallet()
                    pump()
                    errors.assert_not_called()
                self.assertEqual([True], displayed)
                phrase = phrase_holder[0]
                self.assertEqual(24, len(phrase.split()))
                address = app.address_text.get()
                self.assertEqual('hd', app._wallet['kind'])
                self.assertNotIn(phrase, json.dumps(app._wallet))
                self.assertEqual('normal', str(app.seed_show_button.cget('state')))
                app._lock_wallet()
                pump()
                self.assertFalse(app._wallet['unlocked'])
                self.assertEqual('normal', str(app.seed_show_button.cget('state')))
                with patch.object(app, '_choose_file', return_value=restored), \
                        patch.object(app, '_password', return_value=PASSWORD + '-new'), \
                        patch('sumuww.app._RecoveryPhraseDialog', FixtureDialog), \
                        patch('sumuww.app.messagebox.showerror') as errors:
                    app._recover_seed_wallet()
                    pump()
                    errors.assert_not_called()
                self.assertEqual(address, app.address_text.get())
                self.assertEqual(str(restored), app._wallet['path'])
                self.assertNotIn(phrase, json.dumps(app._wallet))
                self.assertNotIn(phrase, app.footer_text.get())
                self.assertFalse(app._pending)
                phrase_holder.clear()
            finally:
                app._destroyed = True
                service.stop().result(timeout=15)
                root.destroy()
                set_translator(Translator('en'))


if __name__ == '__main__':
    unittest.main()
