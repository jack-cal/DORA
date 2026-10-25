"""Release recheck: lock visibility, localized failures and real payment reviews."""
import time
import json
from unittest import TestCase
from unittest.mock import patch
import test_desktop as support
import run
from sumuww.chain import Chain
from sumuww.address import decode_address
from sumuww.keystore import create_hd_wallet

class ReleaseRecheck(TestCase):
    setUp = support.DesktopWalletTests.setUp
    tearDown = support.DesktopWalletTests.tearDown
    await_idle = support.DesktopWalletTests.await_idle
    create = support.DesktopWalletTests.create

    def test_reward_components_and_own_amount_in_all_languages(self):
        from sumuww.rewards import reward_amounts
        self.create()
        self.app.page='Activity';self.app.build();self.await_idle()
        row={'txid':'a'*64,'status':'confirmed','confirmations':2,'coinbase':True,
             'net_amount':20*100_000_000,'mining_reward':reward_amounts(5_000_100_000,101,100_000)}
        for language in self.app.languages:
            self.app.language=language;self.app.show_history({'transactions':[row]})
            text=self.app.history.get('1.0','end')
            for label in ('New issuance (block)','Transaction fees (block)','Total block reward'):
                self.assertIn(self.app.t(label),text,language)
            for amount in ('20.00000000 SMW','50.00000000 SMW','0.00100000 SMW','50.00100000 SMW'):
                self.assertIn(amount,text,language)

    def test_replacement_history_has_localized_status_and_replacement_id(self):
        self.create()
        self.app.page='Activity'; self.app.build(); self.await_idle()
        for language in self.app.languages:
            self.app.language=language
            for reason in ('conflict','ancestor_replaced'):
                self.app.show_history({'transactions':[{'txid':'a'*64,'status':'replaced','replaced_by':'b'*64,
                    'replacement_reason':reason,'confirmations':0,'net_amount':-1000}]})
                text=self.app.history.get('1.0','end')
                expected='Removed after parent replacement' if reason=='ancestor_replaced' else 'Replaced · not applied'
                self.assertIn(self.app.t(expected),text); self.assertIn('b'*64,text)

    def test_auto_lock_closes_recovery_text_window(self):
        self.create()
        self.app.show_phrase({'words': ' '.join(['disposable'] * 12)})
        dialog = self.app.pending_dialog
        self.root.update()
        run.runtime._last_activity = time.monotonic() - 1000
        self.app.refresh()
        self.await_idle()
        self.assertFalse(self.app.state['wallet']['unlocked'])
        self.assertIsNone(self.app.pending_dialog)
        self.assertFalse(dialog.winfo_exists())

    def test_wrong_password_uses_selected_language(self):
        self.create()
        self.app.call('lock', done=self.app.update)
        self.await_idle()
        self.app.language='ko';self.app.build()
        with patch.object(run.messagebox,'showerror') as error:
            self.app.call('unlock','incorrect-test-password')
            self.await_idle()
        error.assert_called_once()
        self.assertEqual(error.call_args.args[1],self.app.t('Check the password or backup file.'))

    def test_empty_wallet_disables_backup_and_phrase(self):
        self.app.buttons['Settings'][0].invoke()
        for key in ('Export encrypted backup','View recovery words'):
            self.assertEqual(str(self.app.buttons[key][0]['state']),'disabled',key)

    def test_auto_lock_timeout_survives_restart(self):
        self.app.set_timeout(60)
        self.await_idle()
        self.assertEqual(json.loads(self.app.preferences.read_text(encoding='utf-8'))['timeout'],60)
        self.app.close()
        run.runtime._timeout=900
        self.root=run.tk.Tk()
        self.app=run.WalletApp(self.root,self.temp.name,network='regtest',bootstrap=False)
        self.await_idle()
        self.assertEqual(run.runtime._timeout,60)

    def test_catching_up_is_not_shown_as_synchronized_when_mining_is_ready(self):
        self.app.state['node']={'peers':[{}],'height':8948,'sync_state':'updating','mining_ready':True}
        self.app.update_status()
        self.assertTrue(self.app.status_label['text'].endswith(self.app.t('Synchronizing')))
        self.app.state['node']['sync_state']='ready'
        self.app.update_status()
        self.assertTrue(self.app.status_label['text'].endswith(self.app.t('Synchronized')))

    def test_payment_review_and_cancellation_preserve_values_in_all_languages(self):
        self.create()
        recipient=create_hd_wallet(self.app.directory/'review-recipient.json',self.password,network='regtest')
        original=self.app.state['wallet']['address']
        with Chain(self.app.directory/'node.sqlite',network='regtest') as chain:
            chain.mine(decode_address(original,network='regtest'),101)
        self.app.refresh();self.await_idle()
        for code in self.app.languages:
            self.app.language=code;self.app.build()
            with patch.object(run.simpledialog,'askstring',side_effect=[recipient.address,'1.00000001']),patch.object(run,'FeeDialog',return_value=type('Quote',(),{'result':'0.00001000'})()),patch.object(run.messagebox,'askokcancel',return_value=False) as review:
                self.app.buttons['↑  Send'][0].invoke();self.await_idle()
            self.assertEqual(review.call_args.args[0],self.app.t('Confirm transfer'),code)
            self.assertIn(recipient.address,review.call_args.args[1],code)
            self.assertIn('1.00001001',review.call_args.args[1],code)
            self.assertEqual(self.app.state['wallet']['address'],original,code)
        with Chain(self.app.directory/'node.sqlite',network='regtest') as chain:
            self.assertEqual(len(chain.mempool_transactions()),0)
