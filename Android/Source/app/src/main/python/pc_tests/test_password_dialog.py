"""Real Tk password visibility and literal encrypted-wallet round trips."""

from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from sumuww.app import _PasswordDialog
from sumuww.i18n import Translator, set_translator
from sumuww.keystore import WalletAuthenticationError, create_wallet, load_wallet


LITERAL_PASSWORD = "  Sumuww Pass \uD55C\uAE00 Aa e\u0301  "


class DialogHarness(_PasswordDialog):
    """Keep a real dialog open for assertions without its modal wait."""

    def wait_window(self, window=None):
        self.update_idletasks()

    def destroy(self):
        self.values_at_destroy = tuple(entry.get() for entry in
                                       (self.password_entry, self.confirm_entry)
                                       if entry is not None)
        super().destroy()


class PasswordDialogTests(unittest.TestCase):
    def setUp(self):
        set_translator(Translator("en"))
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        self.root.withdraw()
        self.dialogs = []

    def tearDown(self):
        if hasattr(self, "root"):
            for dialog in self.dialogs:
                if dialog.winfo_exists():
                    dialog.cancel()
            self.root.destroy()

    def dialog(self, creating=False):
        dialog = DialogHarness(self.root, creating=creating)
        self.dialogs.append(dialog)
        return dialog

    @staticmethod
    def fill(dialog, password, confirmation=None):
        for entry, value in ((dialog.password_entry, password),
                             (dialog.confirm_entry, password if confirmation is None else confirmation)):
            if entry is not None:
                entry.delete(0, tk.END)
                entry.insert(0, value)

    def test_new_and_open_dialogs_start_masked_with_visibility_unchecked(self):
        for creating in (False, True):
            with self.subTest(creating=creating):
                dialog = self.dialog(creating)
                self.assertFalse(dialog.show_password.get())
                self.assertEqual("\u25CF", dialog.password_entry.cget("show"))
                if creating:
                    self.assertEqual("\u25CF", dialog.confirm_entry.cget("show"))
                else:
                    self.assertIsNone(dialog.confirm_entry)
                dialog.cancel()

    def test_creation_checkbox_reveals_and_remasks_both_fields_without_text_changes(self):
        dialog = self.dialog(True)
        self.fill(dialog, LITERAL_PASSWORD)
        for mask in ("", "\u25CF", "", "\u25CF"):
            dialog.visibility_button.invoke()
            self.assertEqual(mask == "", dialog.show_password.get())
            for entry in (dialog.password_entry, dialog.confirm_entry):
                self.assertEqual(mask, entry.cget("show"))
                self.assertEqual(LITERAL_PASSWORD, entry.get())

    def test_open_checkbox_preserves_unicode_case_and_spaces(self):
        dialog = self.dialog()
        self.fill(dialog, LITERAL_PASSWORD)
        dialog.visibility_button.invoke()
        self.assertEqual("", dialog.password_entry.cget("show"))
        self.assertEqual(LITERAL_PASSWORD, dialog.password_entry.get())
        dialog.visibility_button.invoke()
        self.assertEqual("\u25CF", dialog.password_entry.cget("show"))
        self.assertEqual(LITERAL_PASSWORD, dialog.password_entry.get())

    def test_cancel_clears_fields_and_next_dialog_does_not_reuse_visibility_or_input(self):
        first = self.dialog(True)
        self.fill(first, LITERAL_PASSWORD)
        first.visibility_button.invoke()
        first.cancel()
        self.assertIsNone(first.result)
        self.assertEqual(("", ""), first.values_at_destroy)
        next_dialog = self.dialog(True)
        self.assertFalse(next_dialog.show_password.get())
        self.assertEqual("\u25CF", next_dialog.password_entry.cget("show"))
        self.assertEqual("\u25CF", next_dialog.confirm_entry.cget("show"))
        self.assertEqual("", next_dialog.password_entry.get())
        self.assertEqual("", next_dialog.confirm_entry.get())

    def test_creation_rejects_short_or_mismatched_password_when_revealed(self):
        dialog = self.dialog(True)
        dialog.visibility_button.invoke()
        for password, confirmation in (("short", "short"),
                                       (LITERAL_PASSWORD, LITERAL_PASSWORD.swapcase())):
            with self.subTest(password_length=len(password)):
                self.fill(dialog, password, confirmation)
                with patch("sumuww.app.messagebox.showerror") as show_error:
                    self.assertFalse(dialog.validate())
                show_error.assert_called_once()
                self.assertEqual(password, dialog.password_entry.get())

    def test_open_password_keeps_utf8_length_guards_while_revealed(self):
        dialog = self.dialog()
        dialog.visibility_button.invoke()
        for password in ("", "\u6F22" * 400):
            self.fill(dialog, password)
            with patch("sumuww.app.messagebox.showerror") as show_error:
                self.assertFalse(dialog.validate())
            show_error.assert_called_once()
        self.fill(dialog, "x" * 1024)
        self.assertTrue(dialog.validate())

    def test_confirm_returns_literal_password_and_clears_dialog_entries(self):
        dialog = self.dialog(True)
        self.fill(dialog, LITERAL_PASSWORD)
        dialog.visibility_button.invoke()
        dialog.ok()
        self.assertEqual(LITERAL_PASSWORD, dialog.result)
        self.assertEqual(("", ""), dialog.values_at_destroy)

    def test_confirmed_password_reopens_same_encrypted_wallet_and_wrong_case_fails(self):
        creation = self.dialog(True)
        self.fill(creation, LITERAL_PASSWORD)
        creation.visibility_button.invoke()
        creation.ok()
        with tempfile.TemporaryDirectory(prefix="sumuww-password-roundtrip-") as directory:
            path = Path(directory) / "synthetic-wallet.json"
            original = create_wallet(path, creation.result, network="dora")
            encrypted = path.read_bytes()
            self.assertNotIn(LITERAL_PASSWORD.encode("utf-8"), encrypted)
            opening = self.dialog()
            self.fill(opening, LITERAL_PASSWORD)
            opening.visibility_button.invoke()
            opening.visibility_button.invoke()
            opening.ok()
            loaded = load_wallet(path, opening.result, network="dora")
            self.assertEqual(original.address, loaded.address)
            self.assertEqual(original.pubkey, loaded.pubkey)
            with self.assertRaises(WalletAuthenticationError):
                load_wallet(path, LITERAL_PASSWORD.swapcase(), network="dora")
            self.assertEqual(encrypted, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
