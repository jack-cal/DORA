"""Real Tk phrase dialogs clear secrets and never change the clipboard."""
import tkinter as tk
import unittest
from unittest.mock import patch

from sumuww.app import _RecoveryPhraseDialog
from sumuww.hd import entropy_to_mnemonic
from sumuww.i18n import LANGUAGE_CODES, Translator, set_translator

PHRASE = entropy_to_mnemonic(bytes(32))  # Public standard fixture, never a real wallet.


class DialogHarness(_RecoveryPhraseDialog):
    def wait_window(self, window=None):
        self.update_idletasks()

    def destroy(self):
        self.phrase_at_destroy = self.phrase_text.get('1.0', 'end-1c')
        super().destroy()


class SeedDialogTests(unittest.TestCase):
    def setUp(self):
        set_translator(Translator('en'))
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.dialogs = []

    def tearDown(self):
        for dialog in self.dialogs:
            if dialog.winfo_exists():
                dialog.cancel()
        self.root.destroy()
        set_translator(Translator('en'))

    def dialog(self, **arguments):
        dialog = DialogHarness(self.root, **arguments)
        self.dialogs.append(dialog)
        return dialog

    def test_display_is_readonly_private_and_cleared_on_close(self):
        self.root.clipboard_clear()
        self.root.clipboard_append('unchanged fixture clipboard')
        dialog = self.dialog(phrase=PHRASE)
        self.assertEqual(PHRASE, dialog.phrase_text.get('1.0', 'end-1c'))
        self.assertEqual('disabled', dialog.phrase_text.cget('state'))
        self.assertIsNone(dialog._display_phrase)
        self.assertEqual('unchanged fixture clipboard', self.root.clipboard_get())
        dialog.ok()
        self.assertEqual('', dialog.phrase_at_destroy)
        self.assertIsNone(dialog.result)

    def test_recovery_validates_checksum_count_and_never_echoes_invalid_words(self):
        dialog = self.dialog()
        for phrase in ('abandon '*12, PHRASE.replace('art', 'abandon'), 'private unknown fixture words'):
            dialog.phrase_text.delete('1.0', tk.END)
            dialog.phrase_text.insert('1.0', phrase)
            with patch('sumuww.app.messagebox.showerror') as error:
                self.assertFalse(dialog.validate())
            self.assertNotIn(phrase.strip(), str(error.call_args))
        dialog.phrase_text.delete('1.0', tk.END)
        dialog.phrase_text.insert('1.0', PHRASE)
        self.assertTrue(dialog.validate())
        dialog.ok()
        self.assertEqual(PHRASE, dialog.result)
        self.assertEqual('', dialog.phrase_at_destroy)
        dialog.result = None

    def test_cancel_clears_input_without_retaining_a_result(self):
        dialog = self.dialog()
        dialog.phrase_text.insert('1.0', PHRASE)
        dialog.cancel()
        self.assertEqual('', dialog.phrase_at_destroy)
        self.assertIsNone(dialog.result)

    def test_each_ui_language_retains_the_same_english_recovery_words(self):
        for language in LANGUAGE_CODES:
            with self.subTest(language=language):
                set_translator(Translator(language))
                dialog = self.dialog(phrase=PHRASE)
                self.assertEqual(PHRASE, dialog.phrase_text.get('1.0', 'end-1c'))
                self.assertEqual(Translator(language).render('Recovery phrase'), dialog.title())
                dialog.cancel()
                self.assertEqual('', dialog.phrase_at_destroy)


if __name__ == '__main__':
    unittest.main()
