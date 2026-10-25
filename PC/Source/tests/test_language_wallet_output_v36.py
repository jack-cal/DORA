"""Language writers and reserved paths preserve owned encrypted wallet files."""

import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from sumuww import app, i18n
from sumuww.__main__ import _guard_paths
from sumuww.app_service import AppService, AppServiceError
from sumuww.keystore import create_hd_wallet, create_wallet, load_wallet
from sumuww.node_manager import NodeManagerApp
from sumuww.wallet_paths import NODE_PREFERENCE_NAMES


PASSWORD = 'owned-language-wallet-output-password'


class LanguageWalletOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory(prefix='sumuww-language-envelopes-v36-')
        cls.addClassCleanup(cls.fixtures.cleanup)
        cls.envelopes = {}
        for hd in (False, True):
            path = Path(cls.fixtures.name) / ('v2.json' if hd else 'v1.json')
            (create_hd_wallet if hd else create_wallet)(path, PASSWORD, network='regtest')
            cls.envelopes[hd] = path.read_bytes()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-language-output-v36-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / 'ui-language.json'

    def assert_preserved(self, raw, path=None):
        self.assertEqual(raw, (path or self.path).read_bytes())
        self.assertEqual([], list(self.folder.glob('*.tmp')))

    def test_explicit_v1_v2_wallets_are_preserved_and_remain_unlockable(self):
        for hd, raw in self.envelopes.items():
            with self.subTest(hd=hd):
                self.path.write_bytes(raw)
                with self.assertRaisesRegex(OSError, 'must not overwrite an encrypted wallet'):
                    i18n.save_language('ko', self.path)
                self.assert_preserved(raw)
                self.assertEqual(hd, load_wallet(self.path, PASSWORD, network='regtest').is_hd)

    def test_default_preference_path_is_protected_without_reading_user_directory(self):
        for hd, raw in self.envelopes.items():
            with self.subTest(hd=hd), patch.object(i18n, 'preference_path', return_value=self.path):
                self.path.write_bytes(raw)
                with self.assertRaises(OSError):
                    i18n.save_language('fr')
                self.assert_preserved(raw)

    def test_hardlinked_preference_keeps_both_wallet_names(self):
        raw = self.envelopes[False]
        wallet = self.folder / 'ordinary-wallet.json'
        wallet.write_bytes(raw)
        os.link(wallet, self.path)
        with self.assertRaises(OSError):
            i18n.save_language('ar', self.path)
        self.assert_preserved(raw)
        self.assert_preserved(raw, wallet)

    def test_wallet_appearing_after_temporary_serialization_is_preserved(self):
        raw = self.envelopes[True]
        actual_dump = i18n.json.dump
        def appear(value, output, **kwargs):
            actual_dump(value, output, **kwargs)
            self.path.write_bytes(raw)
        with patch.object(i18n.json, 'dump', side_effect=appear):
            with self.assertRaises(OSError):
                i18n.save_language('zh', self.path)
        self.assert_preserved(raw)

    def test_existing_envelope_rejects_before_temp_without_kdf_or_decryption(self):
        for hd, raw in self.envelopes.items():
            with self.subTest(hd=hd):
                self.path.write_bytes(raw)
                with (patch('sumuww.keystore._derive_key', side_effect=AssertionError('KDF used')),
                      patch.object(i18n.tempfile, 'NamedTemporaryFile', side_effect=AssertionError('Temporary output opened'))):
                    with self.assertRaises(OSError):
                        i18n.save_language('de', self.path)
                self.assert_preserved(raw)

    def test_node_monitor_language_callback_preserves_its_directory_wallet(self):
        raw = self.envelopes[True]
        self.path.write_bytes(raw)
        monitor_ui = SimpleNamespace(language=Mock(), _translator=i18n.Translator('en'),
            _language_path=self.path, _apply_language=Mock())
        monitor_ui.language.get.return_value = dict(i18n.LANGUAGES)['ko']
        with self.assertRaises(OSError):
            NodeManagerApp._change_language(monitor_ui)
        self.assert_preserved(raw)
        monitor_ui._apply_language.assert_not_called()

    def test_default_gui_uses_existing_oserror_handling_and_preserves_wallet(self):
        raw = self.envelopes[False]
        self.path.write_bytes(raw)
        # Headless widgets exercise the real GUI callback's persistence branch.
        gui = SimpleNamespace(_closing=False, _busy=False, _dialog_open=False,
            translator=i18n.Translator('en'), language_choice=Mock(), _language_path=None,
            _configure_fonts=Mock(), root=Mock(), _walk_widgets=lambda outer: (), _outer=None,
            _docs_menu_records=(), _docs_menu=Mock(), _history_dialog=None,
            _blocks_dialog=None, fee_preset=Mock(),
            _node_snapshot=None, _wallet=None, _mining=False, _mine_inflight=False,
            _message=Mock(), _sync_controls=Mock(), _reflow_wrapping=Mock(),
            _apply_mongolian_layout=Mock())
        gui.root._sumuww_local_vars = []
        with (patch.object(i18n, 'preference_path', return_value=self.path),
              patch.object(app, 'set_translator')):
            self.assertTrue(app.SumuwwApp.set_language(gui, 'ko'))
        self.assertEqual('ko', gui.translator.language)
        self.assertTrue(gui._message.call_args.kwargs['error'])
        # Earlier GUI tests may leave the active translator in another language.
        # Check the retained message identity, rather than its localized wording.
        self.assertEqual('Could not save the language setting. The next launch may start in English.',
                         gui._message.call_args.args[0].key)
        self.assert_preserved(raw)

    def test_cli_and_service_reserve_language_path_before_wallet_or_secret_read(self):
        self.assertIn('ui-language.json', NODE_PREFERENCE_NAMES)
        database = self.folder / 'node.sqlite'
        roles = ('wallet', 'backup', 'password_file', 'hex_file', 'phrase_file', 'phrase_output')
        for role in roles:
            args = SimpleNamespace(database=database, **{name: self.path if name == role else None for name in roles})
            with self.subTest(role=role), self.assertRaises(ValueError):
                _guard_paths(args)
        service = object.__new__(AppService)
        service.database, service._bootstrap_manifest = database, None
        with self.assertRaises(AppServiceError):
            service._guard_paths(self.path)
        self.assertEqual([], list(self.folder.iterdir()))

    def test_all_eleven_languages_and_ordinary_malformed_preference_repair_work(self):
        sibling = self.folder / 'unrelated.json'
        sibling.write_bytes(b'owned sibling untouched')
        self.path.write_bytes(b'{malformed ordinary preference')
        for language in i18n.LANGUAGE_CODES:
            with self.subTest(language=language):
                i18n.save_language(language, self.path)
                self.assertEqual(language, i18n.load_language(self.path))
                self.assertEqual({'schema_version': 1, 'language': language}, json.loads(self.path.read_bytes()))
        self.assertEqual(34, len(i18n.LANGUAGE_CODES))
        self.assertEqual(b'owned sibling untouched', sibling.read_bytes())
        self.assertEqual([], list(self.folder.glob('*.tmp')))

    def test_unknown_language_keeps_valueerror_api_and_existing_bytes(self):
        raw = self.envelopes[False]
        self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'Unknown UI language'):
            i18n.save_language('unknown', self.path)
        self.assert_preserved(raw)


if __name__ == '__main__':
    unittest.main()
