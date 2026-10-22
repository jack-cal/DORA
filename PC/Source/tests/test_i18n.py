"""Catalog formatting, separate preferences and in-place Tk language changes."""

from concurrent.futures import Future
import json
from pathlib import Path
import string
import sys
import tempfile
import unittest
from unittest.mock import patch

from sumuww.i18n import (CATALOG_DIRECTORY, LANGUAGES, LANGUAGE_CODES, Translator,
                       load_language, save_language, set_translator, tr)


def fields(text):
    return sorted((name, specification, conversion)
                  for _, name, specification, conversion in string.Formatter().parse(text)
                  if name is not None)


class CatalogTests(unittest.TestCase):
    def test_all_supported_catalogs_have_complete_messages_and_exact_placeholders(self):
        original = json.loads((CATALOG_DIRECTORY / "en.json").read_text(encoding="utf-8"))
        self.assertEqual(34, len(LANGUAGES))
        self.assertGreaterEqual(len(original), 152)
        for language in [code for target in LANGUAGE_CODES for code in (target, "en", target)] + list(reversed(LANGUAGE_CODES)):
            with self.subTest(language=language):
                path = CATALOG_DIRECTORY / f"{language}.json"
                catalog = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(set(original), set(catalog))
                for key, value in catalog.items():
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip(), (language, key))
                    self.assertEqual(fields(key), fields(value), (language, key))

    def test_nested_messages_and_numeric_formats_refresh_without_changing_arguments(self):
        translator = Translator("en")
        set_translator(translator)
        detail = tr('Difficulty adjustment every {0:,} blocks', 2016)
        message = tr('Average target {0:,}s   ·   {1}   ·   Network {2}', 600, detail, "dora")
        english = message.render()
        self.assertIn("2,016", english)
        translator.set_language("ko")
        self.assertIn('\ub09c\uc774\ub3c4 \uc870\uc815 2,016\ube14\ub85d', message.render())
        self.assertNotEqual(english, message.render())
        self.assertEqual((600, detail, "dora"), message.arguments)

    def test_addresses_and_amounts_are_inserted_verbatim_in_every_language(self):
        key = 'Sign and send this transaction?\n\nRecipient address\n{0}\n\nAmount: {1} SMW\nFee: {2} SMW'
        address, amount, fee = "dora1qplainasciifixture", "1.25000000", "0.00100000"
        for language in [code for target in LANGUAGE_CODES for code in (target, "en", target)] + list(reversed(LANGUAGE_CODES)):
            with self.subTest(language=language):
                message = Translator(language).render(key, address, amount, fee)
                for value in (address, amount, fee):
                    self.assertEqual(1, message.count(value))
                self.assertFalse(any(character in message for character in "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"))


class LanguagePreferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sumuww-language-preference-")
        self.path = Path(self.temp.name) / "SUMUWW" / "ui-language.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_invalid_and_unknown_preferences_default_to_english(self):
        self.assertEqual("en", load_language(self.path))
        self.path.parent.mkdir()
        for document in ("{broken", "{}", "[]", "null", "x" * 5000,
                         json.dumps({"schema_version": True, "language": "ko"}),
                         json.dumps({"schema_version": 1, "language": "unknown"}),
                         json.dumps({"schema_version": 1, "language": ["ko"]})):
            with self.subTest(document=document[:35]):
                self.path.write_text(document, encoding="utf-8")
                self.assertEqual("en", load_language(self.path))

    def test_all_choices_persist_without_any_wallet_or_database_file(self):
        for language in LANGUAGE_CODES:
            save_language(language, self.path)
            self.assertEqual(language, load_language(self.path))
        self.assertEqual([self.path], list(self.path.parent.iterdir()))
        self.assertFalse(list(self.path.parent.rglob("*.sqlite")))

    def test_failed_atomic_replace_keeps_previous_complete_preference(self):
        save_language("en", self.path)
        before = self.path.read_bytes()
        with patch("sumuww.i18n.os.replace", side_effect=PermissionError("test failure")):
            with self.assertRaises(PermissionError):
                save_language("ko", self.path)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([self.path], list(self.path.parent.iterdir()))


class FakeService:
    def __init__(self, directory):
        from sumuww.profiles import SUMUWW
        self.directory, self.network = directory, SUMUWW
        self.fixture_key = object()
        self.start_calls = 0
        self.pending = Future()

    def start(self):
        self.start_calls += 1
        return self.pending

    def cancel_mining(self):
        future = Future()
        future.set_result(None)
        return future

    stop = cancel_mining


class UiLanguageSwitchTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from sumuww.app import SumuwwApp
        self.temp = tempfile.TemporaryDirectory(prefix="sumuww-ui-language-")
        self.directory = Path(self.temp.name)
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.temp.cleanup()
            self.skipTest(f"Tk display unavailable: {error}")
        self.root.withdraw()
        self.service = FakeService(self.directory / "unused")
        self.path = self.directory / "SUMUWW" / "ui-language.json"
        self.app = SumuwwApp(self.root, self.service, language_path=self.path)
        self.app._started = True
        self.status = {
            "node": {"height": 101, "peers": 1, "mining_ready": True,
                     "listen": {"host": "127.0.0.1", "port": 18444}},
            "wallet": {"address": "dora1qfixtureascii", "path": "fixture-wallet.json",
                       "unlocked": True, "total_smw": "50.00000000",
                       "spendable_smw": "50.00000000", "available_smw": "50.00000000",
                       "pending_smw": "0.00000000", "immature_smw": "0.00000000"},
            "transactions": [{"txid": "a" * 64, "confirmations": 2, "height": 100,
                              "coinbase": False, "net_amount": 5_000_000_000,
                              "status": "confirmed"}],
        }
        self.app._apply_status(self.status)

    def tearDown(self):
        if hasattr(self, "app"):
            self.app._finish_close()
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def test_default_english_and_switch_preserve_inputs_wallet_future_and_mining(self):
        self.assertEqual("en", self.app.translator.language)
        self.assertEqual("SUMUWW", self.root.title())
        values = ((self.app.send_address, "dora1qtypedaddress"), (self.app.send_amount, "1.25000000"),
                  (self.app.send_fee, "0.00100000"), (self.app.mine_count, "23"),
                  (self.app.peer_endpoint, "example.org:18444"))
        for variable, value in values:
            variable.set(value)
        wallet, key = dict(self.app._wallet), self.service.fixture_key
        future, callback = Future(), lambda result: None
        self.app._watch(future, callback)
        pending = list(self.app._pending)
        self.app._mining = self.app._mine_inflight = True
        self.app._mine_completed, self.app._mine_target = 1, 3
        self.app.mine_progress.configure(maximum=3, value=1)
        self.app.mine_text.set(tr('Mining · {0}/{1} blocks completed', 1, 3))
        self.app._message(tr('Computing proof of work. Use Stop to cancel the current search.'))
        for language in [code for target in LANGUAGE_CODES for code in (target, "en", target)] + list(reversed(LANGUAGE_CODES)):
            with self.subTest(language=language):
                self.assertTrue(self.app.set_language(language))
                self.assertEqual(language, load_language(self.path))
                self.assertEqual(wallet, self.app._wallet)
                self.assertIs(key, self.service.fixture_key)
                self.assertEqual(pending, self.app._pending)
                self.assertEqual(0, self.service.start_calls)
                self.assertTrue(self.app._mining and self.app._mine_inflight)
                self.assertEqual((1, 3), (self.app._mine_completed, self.app._mine_target))
                self.assertEqual(1.0, float(self.app.mine_progress["value"]))
                for variable, value in values:
                    self.assertEqual(value, variable.get())
                self.assertEqual(self.app.translator.render('New wallet'), self.app.create_button.cget("text"))
                self.assertIn(self.app.translator.render('Unlocked'), self.app.wallet_text.get())
                row = self.app.transaction_table.item(self.app.transaction_table.get_children()[0], "values")
                self.assertEqual(self.app.translator.render('{0:,} conf.', 2), row[2])
                self.assertEqual("+50.00000000", row[1])

    def test_dgw_cadence_label_matches_next_block_in_all_languages(self):
        from copy import deepcopy
        status = deepcopy(self.status)
        status['node'].update(dgw_activation_height=8064, dgw_interval_activation_height=9000,
                              dgw_retarget_interval=10, retarget_interval=2016, target_timespan=1209600,
                              no_retarget=False)
        for language in LANGUAGE_CODES:
            self.app.set_language(language)
            for height in (8998,8999,9000,9009,9010):
                status['node']['height']=height
                self.app._apply_status(status)
                expected=self.app.translator.render('Every block') if height<8999 else self.app.translator.render('Difficulty adjustment every {0:,} blocks',10)
                self.assertIn(expected,self.app.rules_text.get(),(language,height))
                upcoming=self.app.translator.render('From block {0:,}: every {1:,} blocks',9000,10)
                if height<8999:self.assertIn(upcoming,self.app.rules_text.get(),(language,height))
                else:self.assertNotIn(upcoming,self.app.rules_text.get(),(language,height))

    def test_modal_or_busy_blocks_language_change_and_existing_error_logic_is_localized(self):
        from sumuww.app import _error_message
        self.app._dialog_open = True
        self.assertFalse(self.app.set_language("ko"))
        self.app._dialog_open = False
        self.app._busy = True
        self.assertFalse(self.app.set_language("ko"))
        self.app._busy = False
        self.assertEqual("en", self.app.translator.language)
        self.assertFalse(self.path.exists())
        self.assertTrue(self.app.set_language("ko"))
        self.assertEqual(self.app.translator.render('Insufficient available confirmed funds. Check immature rewards and pending transfers.'),
                         str(_error_message(ValueError("insufficient mature funds"))))

    def test_docs_open_current_language_local_file_and_missing_file_is_localized(self):
        self.app._document_roots = [self.directory / "docs"]
        for language in LANGUAGE_CODES:
            document = self.directory / "docs" / language / "README.html"
            document.parent.mkdir(parents=True)
            document.write_text("<html><title>Fixture</title></html>", encoding="utf-8")
        target = "sumuww.app.os.startfile" if sys.platform == "win32" else "sumuww.app.webbrowser.open"
        with patch(target, create=True, return_value=True) as open_file:
            for language in LANGUAGE_CODES:
                self.app.set_language(language)
                self.app._open_document("README")
                self.assertIn(language, Path(open_file.call_args.args[0]).parts)
        with patch("sumuww.app.messagebox.showerror") as error:
            self.app._open_document("NETWORK_RUNBOOK")
            self.assertEqual(self.app.translator.render('Could not open the document. Check the distribution folder.'), str(error.call_args.args[1]))


if __name__ == "__main__":
    unittest.main()
