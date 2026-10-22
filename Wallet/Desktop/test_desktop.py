"""Desktop UI exercises with disposable keys and isolated regtest only."""
import json
import gc
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import run
from sumuww.chain import Chain
from sumuww.address import decode_address
from sumuww.keystore import create_hd_wallet


class DesktopWalletTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = run.tk.Tk()
        self.app = run.WalletApp(self.root, self.temp.name, network='regtest', bootstrap=False)
        self.password = 'isolated-wallet-test-password'
        self.await_idle()

    def tearDown(self):
        self.app.close()
        self.app.pool.shutdown(wait=True)
        gc.collect()
        self.temp.cleanup()

    def await_idle(self):
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            self.root.update()
            if self.app.started and not self.app.busy and self.app.results.empty():
                return
            time.sleep(.02)
        self.fail('Wallet did not finish queued work')

    def create(self):
        with patch.object(run.simpledialog, 'askstring', side_effect=[self.password, self.password]), patch.object(self.app, 'show_phrase', side_effect=lambda value: self.app.refresh()):
            self.app.buttons['Create a wallet'][0].invoke()
            self.await_idle()
        self.assertTrue(self.app.state['wallet']['unlocked'])

    def test_language_catalog_and_actual_create_lock_unlock_buttons(self):
        self.assertEqual(len(self.app.languages), 34)
        self.assertEqual(self.app.language, 'en')
        with patch.object(self.app, 'call') as backend:
            self.app.buttons['Activity'][0].invoke()
            self.root.update()
            backend.assert_not_called()
            self.assertNotIn('Next page', self.app.buttons)
        self.app.buttons['Wallet'][0].invoke()
        self.create()
        address = self.app.state['wallet']['address']
        for index, code in enumerate(self.app.languages):
            self.app.language_choice.current(index)
            self.app.change_language()
            self.root.update()
            self.assertEqual(self.app.buttons['↑  Send'][0]['text'], self.app.t('↑  Send'))
            self.assertEqual(self.app.state['wallet']['address'], address)
        self.app.buttons['Lock'][0].invoke()
        self.await_idle()
        self.assertFalse(self.app.state['wallet']['unlocked'])
        with patch.object(run.simpledialog, 'askstring', return_value=self.password):
            self.app.buttons['Unlock wallet'][0].invoke()
            self.await_idle()
        self.assertTrue(self.app.state['wallet']['unlocked'])
        self.assertNotIn('Mining', self.app.buttons)

    def test_send_review_names_destination_and_cancel_does_not_spend(self):
        self.create()
        key = create_hd_wallet(Path(self.temp.name) / 'recipient.json', self.password, network='regtest')
        script = decode_address(self.app.state['wallet']['address'], network='regtest')
        with Chain(Path(self.temp.name) / 'node.sqlite', network='regtest') as chain:
            chain.mine(script, 101)
        self.app.refresh()
        self.await_idle()
        with patch.object(run.simpledialog, 'askstring', side_effect=[key.address, '2.50000000', '0.00001000']), patch.object(run.messagebox, 'askokcancel', return_value=False) as review:
            self.app.buttons['↑  Send'][0].invoke()
            self.await_idle()
            self.assertIn(key.address, review.call_args.args[1])
            self.assertIn('2.50001000', review.call_args.args[1])
        with Chain(Path(self.temp.name) / 'node.sqlite', network='regtest') as chain:
            self.assertEqual(len(chain.mempool_transactions()), 0)
        with patch.object(run.simpledialog, 'askstring', side_effect=[key.address, '2.50000000', '0.00001000']), patch.object(run.messagebox, 'askokcancel', return_value=True), patch.object(run.messagebox, 'showinfo'):
            self.app.buttons['↑  Send'][0].invoke()
            self.await_idle()
        with Chain(Path(self.temp.name) / 'node.sqlite', network='regtest') as chain:
            self.assertEqual(len(chain.mempool_transactions()), 1)

    def test_backup_cannot_overwrite_existing_wallet(self):
        self.create()
        target = Path(self.temp.name) / 'wallet.json'
        original = target.read_bytes()
        with patch.object(run.simpledialog, 'askstring', return_value=self.password), patch.object(run.filedialog, 'asksaveasfilename', return_value=str(target)), patch.object(run.messagebox, 'showerror') as error:
            self.app.backup()
            self.await_idle()
            error.assert_called_once()
        self.assertEqual(target.read_bytes(), original)
        self.assertNotIn(self.password, self.app.preferences.read_text() if self.app.preferences.exists() else '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
