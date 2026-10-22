"""Real Tk auto mode does not require typed own addresses or display wildcard."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from sumuww.app import SumuwwApp, _ConnectionDialog
from sumuww.i18n import LANGUAGES, set_translator, Translator, tr
from tests.test_i18n import FakeService


class AutoAddressUiTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='sumuww-auto-address-ui-')
        directory=Path(self.temporary.name)
        self.root=tk.Tk();self.root.withdraw()
        self.service=FakeService(directory/'unused')
        self.app=SumuwwApp(self.root,self.service,language_path=directory/'language.json')
        self.app._started=True

    def tearDown(self):
        self.app._finish_close();self.temporary.cleanup();set_translator(Translator('en'))

    def dialog(self,callback,**overrides):
        state={'listen':'127.0.0.1:0','peers':[],'allow_internet':True,
               'allow_lan':False,'auto_address':True,'own_addresses':['192.168.1.7:18444']}
        state.update(overrides)
        errors=[]
        class Fixture(_ConnectionDialog):
            def buttonbox(dialog):
                def perform():
                    try:callback(dialog)
                    except Exception as error:errors.append(error)
                    finally:dialog.destroy()
                dialog.after(0,perform)
        result=Fixture(self.root,state)
        if errors:raise errors[0]
        return result

    def test_auto_mode_accepts_empty_own_address_and_disables_manual_fields(self):
        def check(dialog):
            self.assertEqual('disabled',str(dialog.listen_entry.cget('state')))
            self.assertEqual('disabled',str(dialog.public_contact_entry.cget('state')))
            dialog.listen.set('');dialog.public_contact.set('')
            with patch('sumuww.app.messagebox.showerror') as error:
                self.assertTrue(dialog.validate());error.assert_not_called()
            dialog.apply()
            self.assertTrue(dialog.result['auto_address'])
            self.assertEqual('',dialog.result['advertise'])
        self.dialog(check)

    def test_manual_override_restores_entries_and_checks_address(self):
        def check(dialog):
            dialog.auto_address.set(False);dialog._address_mode()
            self.assertEqual('normal',str(dialog.listen_entry.cget('state')))
            self.assertEqual('normal',str(dialog.public_contact_entry.cget('state')))
            dialog.listen.set('')
            with patch('sumuww.app.messagebox.showerror') as error:
                self.assertFalse(dialog.validate());error.assert_called_once()
            dialog.listen.set('127.0.0.1:22000');dialog.apply()
            self.assertFalse(dialog.result['auto_address'])
            self.assertEqual('127.0.0.1:22000',dialog.result['listen'])
        self.dialog(check)

    def test_main_window_uses_actual_addresses_and_translates_auto_state(self):
        for language,_ in LANGUAGES:
            with self.subTest(language=language):
                self.app.set_language(language)
                self.app._apply_status({'node':{'height':0,'peers':0,
                    'listen':{'host':'0.0.0.0','port':18444},
                    'own_addresses':['192.168.1.7:18444'],'mining_ready':False},
                    'connection':{'listen':'127.0.0.1:0','auto_address':True,
                                  'own_addresses':['192.168.1.7:18444']},
                    'wallet':{},'transactions':[]})
                self.assertIn('192.168.1.7:18444',self.app.node_text.get())
                self.assertNotIn('0.0.0.0',self.app.node_text.get())
                self.assertEqual(str(tr('Own node address is managed automatically.')),self.app.own_mode_text.get())
                self.assertFalse(self.app._mining_allowed())

    def test_no_adapter_address_does_not_display_wildcard_as_contact(self):
        self.app._apply_status({'node':{'height':0,'peers':0,
            'listen':{'host':'0.0.0.0','port':18444},'own_addresses':[],
            'mining_ready':False},'wallet':{},'transactions':[]})
        self.assertNotIn('0.0.0.0',self.app.node_text.get())
        self.assertIn(str(tr('No usable network address found.')),self.app.node_text.get())


if __name__=='__main__':unittest.main()
