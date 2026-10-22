import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sumuww.app import SumuwwApp
from sumuww.privacy_ui import load_hidden, save_hidden


class HelpTests(unittest.TestCase):
    def test_real_dialog_cancel_does_not_save_checked_box_but_run_does(self):
        import tkinter as tk
        from sumuww.app import _PrivacyHelpDialog
        root=tk.Tk();root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as folder, patch('sumuww.privacy_ui.help_path',return_value=Path(folder)/'help.json'):
                class Cancel(_PrivacyHelpDialog):
                    def body(self,master):
                        super().body(master)
                        self.hide_help.set(True)
                        self.after(100,self.cancel)
                self.assertIsNone(Cancel(root,'tor').result)
                self.assertEqual({},load_hidden())
                class Run(_PrivacyHelpDialog):
                    def body(self,master):
                        super().body(master)
                        self.hide_help.set(True)
                        self.after(100,self.ok)
                self.assertTrue(Run(root,'tor').result)
                self.assertTrue(load_hidden()['tor'])
        finally:root.destroy()

    def dispatch(self, hidden=False, accepted=True, selected='tor'):
        service=SimpleNamespace(configure_privacy=Mock())
        owner=SimpleNamespace(root=None,_connection_snapshot={'privacy':{'mode':'direct'}},service=service,
                              _dialog_action=lambda action:action(),_run_action=lambda action:action())
        with patch('sumuww.app._PrivacyDialog',return_value=SimpleNamespace(result={'mode':selected,'port':9050})), \
             patch('sumuww.privacy_ui.load_hidden',return_value={selected:hidden}), \
             patch('sumuww.app._PrivacyHelpDialog',return_value=SimpleNamespace(result=accepted)) as help_dialog:
            SumuwwApp._configure_privacy(owner)
        return service.configure_privacy,help_dialog

    def test_cancel_keeps_connection_unchanged(self):
        change,help_dialog=self.dispatch(accepted=False)
        change.assert_not_called(); help_dialog.assert_called_once()

    def test_help_repeats_until_suppressed(self):
        for _ in range(2):
            change,help_dialog=self.dispatch()
            change.assert_called_once(); help_dialog.assert_called_once()

    def test_checked_help_skips_dialog_and_runs_selection(self):
        change,help_dialog=self.dispatch(hidden=True)
        change.assert_called_once_with(mode='tor',port=9050); help_dialog.assert_not_called()

    def test_tor_preference_does_not_hide_i2p_help(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'privacy-help.json'
            save_hidden('tor',True,path)
            self.assertTrue(load_hidden(path)['tor'])
            self.assertFalse(load_hidden(path).get('i2p',False))
            save_hidden('i2p',True,path); save_hidden('tor',False,path)
            self.assertEqual({'tor':False,'i2p':True},load_hidden(path))

    def test_corrupt_help_preference_shows_help_again(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'privacy-help.json'; path.write_text('{bad json')
            self.assertEqual({},load_hidden(path))
