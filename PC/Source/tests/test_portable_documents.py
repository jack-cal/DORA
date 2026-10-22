"""Open localized documents from an isolated, PyInstaller-style PC bundle."""

from concurrent.futures import Future
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sumuww import app as app_module
from sumuww.i18n import LANGUAGE_CODES


DOCUMENTS = ('WHITEPAPER', 'SUMUWW_PROTOCOL_SPEC', 'README', 'NETWORK_RUNBOOK', 'RPC_API')


class PortableDocumentMenuTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.temporary = tempfile.TemporaryDirectory(prefix='sumuww-portable-docs-')
        self.directory = Path(self.temporary.name)
        self.bundle = self.directory / 'SUMUWW'
        self.bundle.mkdir()
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.temporary.cleanup()
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        service = SimpleNamespace(directory=self.directory / 'owned-profile', network='regtest',
                                  start=lambda: Future(), status=lambda: Future())
        # PyInstaller keeps the imported module under _internal, while the
        # released ZIP keeps localized HTML next to the executable in docs/.
        with patch.object(app_module, '__file__', str(self.bundle / '_internal' / 'dora' / 'app.py')), \
                patch.object(sys, 'executable', str(self.bundle / 'SUMUWW.exe')):
            self.app = app_module.SumuwwApp(self.root, service, language='en',
                                         language_path=self.directory / 'language.json')
        self.app._started = True

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app._finish_close()
        self.temporary.cleanup()

    def document(self, root, language, name):
        path = root / language / (name + '.html')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'<html lang="{language}"><title>Owned fixture</title></html>', encoding='utf-8')
        return path.resolve()

    def invoke_menu(self, index, expected):
        target = 'sumuww.app.os.startfile' if sys.platform == 'win32' else 'sumuww.app.webbrowser.open'
        with patch(target, create=True, return_value=True) as opener, \
                patch('sumuww.app.messagebox.showerror') as error:
            self.app._docs_menu.invoke(index)
        error.assert_not_called()
        opener.assert_called_once()
        actual = opener.call_args.args[0]
        self.assertEqual(str(expected) if sys.platform == 'win32' else expected.as_uri(), actual)

    def test_portable_outer_docs_open_all_five_menus_in_every_language(self):
        root = self.bundle / 'docs' / 'i18n'
        for language in LANGUAGE_CODES:
            self.app.translator.set_language(language)
            for index, name in enumerate(DOCUMENTS):
                with self.subTest(language=language, document=name):
                    self.invoke_menu(index, self.document(root, language, name))
        self.assertFalse((self.bundle / '_internal' / 'docs').exists())
        self.assertFalse((self.bundle / 'documents').exists())

    def test_current_outer_docs_take_priority_over_legacy_copies(self):
        self.document(self.bundle / 'documents' / 'docs' / 'i18n', 'en', 'README')
        current = self.document(self.bundle / 'docs' / 'i18n', 'en', 'README')
        self.invoke_menu(DOCUMENTS.index('README'), current)

    def test_legacy_documents_layout_still_opens(self):
        legacy = self.document(self.bundle / 'documents' / 'docs' / 'i18n', 'en', 'README')
        self.invoke_menu(DOCUMENTS.index('README'), legacy)


if __name__ == '__main__':
    unittest.main()
