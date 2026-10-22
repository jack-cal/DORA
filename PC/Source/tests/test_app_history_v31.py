"""Independent actual Tk tests for read-only, paginated wallet history."""
from concurrent.futures import Future
import copy
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from sumuww.app import SumuwwApp
from sumuww.profiles import SUMUWW


def resolved(value):
    future = Future()
    future.set_result(value)
    return future


class HistoryFixtureService:
    """Only history replies are deliberately delayed; no real storage/network."""
    def __init__(self, directory):
        self.directory = directory
        self.network = SUMUWW
        self.history_requests = []
        self.cancel_calls = 0
        self.mine_calls = 0
        self.status_value = {
            'node': {'height': 123, 'peers': 1, 'mining_ready': True,
                     'listen': {'host': '127.0.0.1', 'port': 18444}},
            'wallet': {'address': 'dora1qownedhistoryfixture', 'path': 'owned-wallet.json',
                       'unlocked': False, 'kind': 'single_key', 'total_smw': '0',
                       'available_smw': '0', 'immature_smw': '0', 'pending_smw': '0'},
            'transactions': [], 'mining': {'state': 'idle', 'reserved': False}}

    def start(self):
        return self.status()

    def status(self):
        return resolved(copy.deepcopy(self.status_value))

    def stop(self):
        return resolved({'stopped': True})

    def cancel_mining(self):
        self.cancel_calls += 1
        return resolved({})

    def mine_one(self):
        self.mine_calls += 1
        return Future()

    def transaction_history(self, offset=0, limit=50):
        future = Future()
        self.history_requests.append({'future': future, 'offset': offset, 'limit': limit,
                                      'address': self.status_value['wallet']['address']})
        return future

    def answer(self, index=-1, *, total=123, confirmations=1, height=123, address=None):
        request = self.history_requests[index]
        start = request['offset']
        stop = min(total, start + request['limit'])
        rows = [{'txid': f'{number:064x}', 'confirmations': 0 if number == 1 else confirmations,
                 'height': None if number == 1 else height - confirmations + 1,
                 'coinbase': number % 3 == 0,
                 'net_amount': (-1 if number % 3 == 2 else 1) * 100_000_000,
                 'status': 'pending' if number == 1 else 'confirmed'}
                for number in range(start + 1, stop + 1)]
        value = {'transactions': rows, 'total': total, 'offset': start,
                 'limit': request['limit'], 'height': height, 'tip': f'{height:064x}',
                 'address': address or request['address']}
        request['future'].set_result(value)
        return value


class HistoryUiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sumuww-owned-history-ui-')
        self.directory = Path(self.temp.name)
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.temp.cleanup()
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.service = HistoryFixtureService(self.directory / 'unused')
        self.app = SumuwwApp(self.root, self.service, language='en',
                           language_path=self.directory / 'owned-language.json')
        self.app._started = True
        self.app._apply_status(copy.deepcopy(self.service.status_value))
        self.callback_errors = []
        self.root.report_callback_exception = lambda *error: self.callback_errors.append(error)

    def tearDown(self):
        self.app._finish_close()
        self.temp.cleanup()

    def pump(self, condition=lambda: True, timeout=2):
        deadline = time.monotonic() + timeout
        while True:
            self.root.update()
            if condition():
                return
            if time.monotonic() >= deadline:
                self.fail('History UI fixture deadline exceeded')
            time.sleep(.005)

    def open(self):
        self.app._open_history()
        dialog = self.app._history_dialog
        self.assertIsNotNone(dialog)
        dialog.withdraw()
        self.pump(lambda: bool(self.service.history_requests))
        return dialog

    def reply(self, dialog, **options):
        value = self.service.answer(**options)
        self.pump(lambda: dialog.total == value['total'] and
                  len(dialog.table.get_children()) == len(value['transactions']))
        # Exact row counts alone may match an older refresh, so let the dialog's
        # own Future poll complete before reading content or navigation state.
        deadline = time.monotonic() + .25
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(.005)
        return value

    def values(self, dialog):
        return [tuple(dialog.table.item(item, 'values')) for item in dialog.table.get_children()]

    def test_locked_wallet_opens_default_page_and_renders_transaction_types(self):
        self.assertFalse(self.app._wallet['unlocked'])
        self.assertEqual('normal', str(self.app.history_button.cget('state')))
        dialog = self.open()
        self.assertEqual((0, 50), (self.service.history_requests[0]['offset'], self.service.history_requests[0]['limit']))
        self.reply(dialog)
        self.assertEqual((0, 123, 50), (dialog.offset, dialog.total, len(dialog.transactions)))
        self.assertEqual('disabled', str(dialog.previous_button.cget('state')))
        self.assertEqual('normal', str(dialog.next_button.cget('state')))
        rows = self.values(dialog)
        self.assertIn(f'{1:064x}', rows[0])
        self.assertIn('Pending', rows[0])
        self.assertTrue(any('Send' in row for row in rows))
        self.assertTrue(any('Incoming' in row for row in rows))
        self.assertTrue(any('Mining reward' in row for row in rows))
        self.assertEqual(0, self.service.mine_calls)
        self.assertEqual(0, self.service.cancel_calls)

    def test_previous_next_traverse_beyond_recent_and_partial_final_page(self):
        dialog = self.open(); self.reply(dialog)
        for offset, count, next_state in ((50, 50, 'normal'), (100, 23, 'disabled')):
            before = len(self.service.history_requests)
            dialog.next_button.invoke()
            self.pump(lambda: len(self.service.history_requests) > before)
            self.assertEqual(offset, self.service.history_requests[-1]['offset'])
            self.reply(dialog)
            self.assertEqual(offset, dialog.offset)
            self.assertEqual(count, len(self.values(dialog)))
            self.assertIn(f'{offset+1:064x}', self.values(dialog)[0])
            self.assertEqual(next_state, str(dialog.next_button.cget('state')))
            self.assertEqual('normal', str(dialog.previous_button.cget('state')))
        for offset in (50, 0):
            before = len(self.service.history_requests)
            dialog.previous_button.invoke()
            self.pump(lambda: len(self.service.history_requests) > before)
            self.reply(dialog)
            self.assertEqual(offset, dialog.offset)
        self.assertEqual('disabled', str(dialog.previous_button.cget('state')))

    def test_refresh_current_page_updates_confirmations_without_changing_recent_limit(self):
        self.service.status_value['transactions'] = [
            {'txid': f'{number:064x}', 'confirmations': 1, 'coinbase': True,
             'net_amount': 100_000_000, 'status': 'confirmed'} for number in range(20)]
        self.app._apply_status(copy.deepcopy(self.service.status_value))
        self.assertEqual(10, len(self.app.transaction_table.get_children()))
        dialog = self.open(); self.reply(dialog)
        dialog.next_button.invoke(); self.pump(lambda: len(self.service.history_requests) == 2)
        self.reply(dialog, confirmations=2)
        before = len(self.service.history_requests)
        dialog.refresh_button.invoke(); self.pump(lambda: len(self.service.history_requests) > before)
        self.assertEqual(50, self.service.history_requests[-1]['offset'])
        self.reply(dialog, confirmations=7, height=129)
        self.assertEqual(50, dialog.offset)
        self.assertIn('7 conf.', self.values(dialog)[0])
        self.assertEqual(10, len(self.app.transaction_table.get_children()))

    def test_total_shrink_requeries_a_valid_final_page(self):
        dialog = self.open(); self.reply(dialog)
        for expected in (50, 100):
            before = len(self.service.history_requests)
            dialog.next_button.invoke()
            self.pump(lambda: len(self.service.history_requests) > before)
            self.reply(dialog)
            self.assertEqual(expected, dialog.offset)
        before = len(self.service.history_requests)
        dialog.refresh_button.invoke()
        self.pump(lambda: len(self.service.history_requests) > before)
        self.service.answer(total=30)
        self.pump(lambda: len(self.service.history_requests) > before + 1)
        self.assertEqual(0, self.service.history_requests[-1]['offset'])
        self.reply(dialog, total=30)
        self.assertEqual((0, 30), (dialog.offset, dialog.total))
        self.assertEqual(30, len(self.values(dialog)))
        self.assertEqual('disabled', str(dialog.previous_button.cget('state')))
        self.assertEqual('disabled', str(dialog.next_button.cget('state')))

    def test_empty_history_has_no_rows_or_navigation(self):
        dialog = self.open(); self.reply(dialog, total=0)
        self.assertFalse(dialog.table.get_children())
        self.assertEqual('disabled', str(dialog.previous_button.cget('state')))
        self.assertEqual('disabled', str(dialog.next_button.cget('state')))

    def test_loading_disables_controls_and_reopening_uses_existing_dialog(self):
        dialog = self.open()
        self.assertEqual('disabled', str(dialog.previous_button.cget('state')))
        self.assertEqual('disabled', str(dialog.next_button.cget('state')))
        self.assertEqual('disabled', str(dialog.refresh_button.cget('state')))
        self.app._open_history()
        self.assertIs(dialog, self.app._history_dialog)
        self.assertEqual(1, len(self.service.history_requests))
        self.reply(dialog)
        self.assertEqual('normal', str(dialog.refresh_button.cget('state')))

    def test_failed_read_allows_refresh_retry_without_losing_wallet_or_mining(self):
        dialog = self.open()
        self.service.history_requests[0]['future'].set_exception(RuntimeError('owned fixture temporary read error'))
        self.pump(lambda: str(dialog.refresh_button.cget('state')) == 'normal')
        self.assertIn('Refresh', dialog.state_text.get())
        self.assertFalse(dialog.table.get_children())
        self.assertEqual('dora1qownedhistoryfixture', self.app._wallet['address'])
        dialog.refresh_button.invoke()
        self.pump(lambda: len(self.service.history_requests) == 2)
        self.reply(dialog, total=3)
        self.assertEqual(3, len(dialog.table.get_children()))
        self.assertEqual(0, self.service.cancel_calls)
        self.assertEqual(0, self.service.mine_calls)

    def test_dialog_close_drops_delayed_result_without_tk_callback_error(self):
        dialog = self.open()
        dialog.close()
        self.assertIsNone(self.app._history_dialog)
        request = self.service.history_requests[0]
        if not request['future'].done():
            self.service.answer(0)
        self.pump()
        time.sleep(.15); self.root.update()
        self.assertFalse(dialog.winfo_exists())
        self.assertFalse(self.callback_errors)

    def test_wallet_change_closes_old_dialog_and_discards_its_late_reply(self):
        dialog = self.open()
        old_request = self.service.history_requests[0]
        self.service.status_value['wallet']['address'] = 'dora1qnewownedhistorywallet'
        self.service.status_value['wallet']['path'] = 'owned-second-wallet.json'
        self.app._wallet_epoch += 1
        self.app._apply_status(copy.deepcopy(self.service.status_value))
        self.assertIsNone(self.app._history_dialog)
        self.assertFalse(dialog.winfo_exists())
        if not old_request['future'].done():
            self.service.answer(0)
        self.pump()
        new_dialog = self.open(); self.reply(new_dialog, total=3)
        self.assertEqual('dora1qnewownedhistorywallet', new_dialog._wallet_address)
        self.assertEqual(3, len(new_dialog.table.get_children()))
        self.assertFalse(self.callback_errors)

    def test_payload_for_another_wallet_never_renders_rows(self):
        dialog = self.open()
        self.service.answer(address='dora1qunrelatedhistorywallet')
        deadline = time.monotonic() + .3
        while time.monotonic() < deadline:
            self.root.update(); time.sleep(.005)
        if dialog.winfo_exists():
            self.assertFalse(dialog.table.get_children())
        self.assertEqual('dora1qownedhistoryfixture', self.app._wallet['address'])
        self.assertFalse(self.callback_errors)

    def test_history_open_refresh_close_does_not_change_mining_or_send_fields(self):
        self.app._mining = self.app._mine_inflight = True
        self.app._mine_target, self.app._mine_completed = 100, 17
        self.app.send_address.set('dora1qunsentsendfield')
        self.app.send_amount.set('1.25000000')
        self.app.send_fee.set('0.00100000')
        self.service.status_value['mining'] = {'state': 'running', 'reserved': True}
        self.app._apply_status(copy.deepcopy(self.service.status_value))
        self.assertEqual('normal', str(self.app.history_button.cget('state')))
        dialog = self.open(); self.reply(dialog)
        dialog.refresh_button.invoke(); self.pump(lambda: len(self.service.history_requests) == 2)
        self.reply(dialog)
        dialog.close()
        self.assertTrue(self.app._mining and self.app._mine_inflight)
        self.assertEqual((100, 17), (self.app._mine_target, self.app._mine_completed))
        self.assertEqual(('dora1qunsentsendfield', '1.25000000', '0.00100000'),
                         (self.app.send_address.get(), self.app.send_amount.get(), self.app.send_fee.get()))
        self.assertEqual(0, self.service.mine_calls)
        self.assertEqual(0, self.service.cancel_calls)


if __name__ == '__main__':
    unittest.main()
