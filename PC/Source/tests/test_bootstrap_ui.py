"""Users see missing source configuration separately from an active search."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from sumuww.app import SumuwwApp
from sumuww.i18n import LANGUAGES, tr
from tests.test_i18n import FakeService


class BootstrapUiTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='sumuww-bootstrap-ui-')
        directory=Path(self.temporary.name)
        self.root=tk.Tk();self.root.withdraw()
        self.service=FakeService(directory/'unused')
        self.app=SumuwwApp(self.root,self.service,language_path=directory/'language.json')
        self.app._started=True

    def tearDown(self):
        self.app._finish_close();self.temporary.cleanup()

    def apply(self,*,enabled=True,seeds=0,fallbacks=0,manual=0,cached=0):
        self.app._apply_status({'node':{'height':0,'peers':0,'mining_ready':False,
            'listen':{'host':'127.0.0.1','port':18444},'configured_peers':manual,
            'peer_discovery':{'candidates':cached},
            'bootstrap':{'enabled':enabled,'dns_seed_providers':seeds,'fallback_peers':fallbacks}},
            'wallet':{},'transactions':[]})
        self.root.update_idletasks()
        self.assertFalse(self.app._mining_allowed())
        self.assertEqual(0,self.service.start_calls)

    def test_missing_initial_sources_are_explained_in_all_languages(self):
        for code,_ in LANGUAGES:
            with self.subTest(language=code):
                self.app.set_language(code);self.apply()
                self.assertEqual(str(tr('No initial node discovery sources are configured.')),self.app.sync_text.get())

    def test_search_state_covers_seed_fallback_manual_and_saved_contacts(self):
        for contacts in ({'seeds':1},{'fallbacks':1},{'manual':1},{'cached':1}):
            with self.subTest(contacts=contacts):
                self.apply(**contacts)
                self.assertEqual(str(tr('Searching automatically for reachable SMW nodes…')),self.app.sync_text.get())

    def test_internet_opt_out_does_not_claim_automatic_public_search(self):
        self.apply(enabled=False,seeds=2)
        self.assertEqual(str(tr('Waiting for peers · Mining starts after synchronization')),self.app.sync_text.get())


if __name__=='__main__':unittest.main()
