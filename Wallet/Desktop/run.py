"""Standalone Windows wallet; uses the existing SUMUWW validation service."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import queue
import sys

ROOT = Path(__file__).resolve().parent
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(ROOT.parents[1] / 'PC/Source'))
from sumuww.windows_tk import prepare_tk
prepare_tk()
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from sumuww.brand import apply_window_icon, artwork
from sumuww.vertical_text import VerticalLabel, VerticalButton
from sumuww.primitives import format_amount
import wallet_runtime as runtime

VERSION = '1.0.1'


class WalletApp:
    def __init__(self, root, directory, *, network='dora', bootstrap=True):
        self.root, self.directory = root, Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.preferences = self.directory / 'wallet-ui.json'
        self.languages = json.loads((ROOT / 'locales/languages.json').read_text(encoding='utf-8'))
        try:
            saved = json.loads(self.preferences.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            saved = {}
        self.language = saved.get('language', 'en')
        if self.language not in self.languages:
            self.language = 'en'
        self.timeout = saved.get('timeout', 300)
        if self.timeout not in (60, 300, 900):
            self.timeout = 300
        self.catalogs = {code: json.loads((ROOT / f'locales/{code}.json').read_text(encoding='utf-8')) for code in self.languages}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='wallet-ui')
        self.results = queue.Queue()
        self.busy = False
        self.closed = False
        self.started = False
        self.state = {}
        self.buttons = {}
        self.page = 'Wallet'
        self.offset = 0
        self.pending_dialog = None
        self.root.title(f'SUMUWW Wallet {VERSION}')
        self.root.geometry('900x720')
        self.root.minsize(760, 620)
        self.root.configure(bg='#f4f7fb')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TFrame', background='#f4f7fb')
        style.configure('TLabel', background='#f4f7fb', foreground='#172b4c', font=('Segoe UI', 11))
        style.configure('TButton', padding=(12, 9), font=('Segoe UI', 10))
        style.configure('Title.TLabel', font=('Segoe UI', 22, 'bold'))
        style.configure('Balance.TLabel', font=('Segoe UI', 31, 'bold'))
        self.build()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.bind('<Unmap>', self.on_unmap, add='+')
        self.root.bind('<Map>', self.on_map, add='+')
        self.root.after(40, self.drain)
        self.root.after(4000, self.poll)
        self.submit(lambda: runtime.start(self.directory, mobile=False, network=network, bootstrap=bootstrap), self.did_start)

    def t(self, source):
        return self.catalogs[self.language].get(source, source)

    def label(self, parent, **kwargs):
        label = VerticalLabel(parent, **kwargs)
        label._vertical_max_width = int(kwargs.get('wraplength', 680))
        label.refresh_vertical()
        return label

    def save_preferences(self):
        temporary = self.preferences.with_suffix('.tmp')
        temporary.write_text(json.dumps({'language': self.language, 'timeout': self.timeout}), encoding='utf-8')
        os.replace(temporary, self.preferences)

    def change_language(self, event=None):
        self.language = list(self.languages)[self.language_choice.current()]
        self.save_preferences()
        self.build()

    def build(self):
        for widget in self.root.winfo_children():
            if not isinstance(widget, tk.Toplevel):
                widget.destroy()
        self.buttons = {}
        apply_window_icon(self.root, self.language)
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill='both', expand=True)
        top = ttk.Frame(frame)
        top.pack(fill='x')
        try:
            self.logo = tk.PhotoImage(file=str(artwork(self.language)))
            factor = max(1, self.logo.width() // 190)
            self.logo = self.logo.subsample(factor)
            self.label(top, image=self.logo).pack(side='left')
        except tk.TclError:
            self.label(top, text='SUMUWW', style='Title.TLabel').pack(side='left')
        self.language_choice = ttk.Combobox(top, values=list(self.languages.values()), state='readonly', width=22)
        self.language_choice.current(list(self.languages).index(self.language))
        self.language_choice.pack(side='right')
        self.language_choice.bind('<<ComboboxSelected>>', self.change_language)
        self.label(top, text=self.t('Language')).pack(side='right', padx=8)
        nav = ttk.Frame(frame)
        nav.pack(fill='x', pady=(22, 16))
        for page in ('Wallet', 'Activity', 'Settings'):
            self.button(nav, page, lambda p=page: self.navigate(p), side='left')
        self.button(nav, 'Lock', lambda: self.call('lock', done=self.update), side='right')
        self.status_label = self.label(frame, text=self.t('Starting your wallet…'), wraplength=800)
        self.status_label.pack(fill='x', pady=(0, 12))
        area = ttk.Frame(frame)
        area.pack(fill='both', expand=True)
        self.body_canvas = tk.Canvas(area, background='#f4f7fb', highlightthickness=0)
        scrollbar = ttk.Scrollbar(area, orient='vertical', command=self.body_canvas.yview)
        scrollbar.pack(side='right', fill='y')
        self.body_canvas.pack(side='left', fill='both', expand=True)
        self.body_canvas.configure(yscrollcommand=scrollbar.set)
        self.body = ttk.Frame(self.body_canvas)
        body_window = self.body_canvas.create_window((0, 0), window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda e: self.body_canvas.configure(scrollregion=self.body_canvas.bbox('all')))
        self.body_canvas.bind('<Configure>', lambda e: self.body_canvas.itemconfigure(body_window, width=e.width))
        self.root.bind('<MouseWheel>', lambda e: self.body_canvas.yview_scroll(-int(e.delta / 120), 'units'))
        self.label(frame, text=f'SUMUWW Wallet {VERSION} · Core 0.57.34', foreground='#6f7e98').pack(anchor='w', pady=(16, 0))
        self.render()
        self.update_status()
        self.set_busy(self.busy)

    def button(self, parent, key, callback, **pack):
        button = VerticalButton(parent, text=self.t(key), command=callback)
        button.pack(padx=4, pady=4, **(pack or {'fill': 'x'}))
        self.buttons.setdefault(key, []).append(button)
        return button

    def navigate(self, page):
        if self.busy:
            return
        self.page = page
        self.render()

    def render(self):
        for child in self.body.winfo_children():
            child.destroy()
        self.buttons = {key: [b for b in values if b.winfo_exists()] for key, values in self.buttons.items()}
        if self.page == 'Wallet':
            self.label(self.body, text=self.t('Your SUMUWW wallet'), style='Title.TLabel').pack(anchor='w')
            self.label(self.body, text=self.t('Receive and send SMW.')).pack(anchor='w', pady=(6, 20))
            wallet = self.state.get('wallet') or {}
            if not self.state.get('wallet_exists'):
                self.button(self.body, 'Create a wallet', lambda: self.create('create'))
                self.button(self.body, 'Restore recovery words', lambda: self.create('recover'))
                self.button(self.body, 'Import encrypted backup', self.restore)
            elif not wallet.get('unlocked'):
                self.button(self.body, 'Unlock wallet', self.unlock)
            else:
                self.label(self.body, text=self.t('Available balance')).pack(anchor='w')
                self.label(self.body, text=wallet.get('available_dora', '0.00000000') + ' SMW', style='Balance.TLabel').pack(anchor='w', pady=(8, 12))
                for key, label in (('pending_dora', 'Pending'), ('immature_dora', 'Immature mining rewards')):
                    self.label(self.body, text=f'{self.t(label)}: {wallet.get(key, "0.00000000")} SMW').pack(anchor='w', pady=3)
                self.button(self.body, '↓  Receive', self.receive)
                self.button(self.body, '↑  Send', self.send)
                address = ttk.Entry(self.body, width=70)
                address.insert(0, wallet.get('address', ''))
                address.configure(state='readonly')
                address.pack(fill='x', pady=16)
        elif self.page == 'Activity':
            self.label(self.body, text=self.t('Recent activity'), style='Title.TLabel').pack(anchor='w', pady=(0, 16))
            if not (self.state.get('wallet') or {}).get('unlocked'):
                prompt = 'Open your wallet first.' if self.state.get('wallet_exists') else 'Create or restore a wallet.'
                self.label(self.body, text=self.t(prompt), wraplength=760).pack(anchor='w')
                self.set_busy(self.busy)
                return
            self.history = tk.Text(self.body, height=16, wrap='word', font=('Segoe UI', 10), relief='flat', padx=12, pady=12)
            self.history.pack(fill='both', expand=True)
            self.history.configure(state='disabled')
            controls = ttk.Frame(self.body)
            controls.pack(fill='x')
            self.button(controls, 'Previous page', lambda: self.history_page(-50), side='left')
            self.button(controls, 'Next page', lambda: self.history_page(50), side='left')
            if self.started and not self.busy:
                self.call('history', str(self.offset), done=self.show_history)
        else:
            self.label(self.body, text=self.t('Wallet management'), style='Title.TLabel').pack(anchor='w', pady=(0, 12))
            self.button(self.body, 'Export encrypted backup', self.backup)
            self.button(self.body, 'View recovery words', self.phrase)
            self.button(self.body, 'Add peer', self.add_peer)
            self.label(self.body, text=self.t('Auto-lock')).pack(anchor='w', pady=(16, 3))
            timeout = ttk.Combobox(self.body, state='readonly', values=[self.t(x) for x in ('1 minute', '5 minutes', '15 minutes')])
            timeout.current({60: 0, 300: 1, 900: 2}.get(runtime._timeout, 1))
            timeout.pack(anchor='w')
            timeout.bind('<<ComboboxSelected>>', lambda e: self.set_timeout((60, 300, 900)[timeout.current()]))
        self.set_busy(self.busy)

    def set_busy(self, value):
        self.busy = value
        for key, buttons in self.buttons.items():
            for button in buttons:
                if button.winfo_exists():
                    unavailable = key in ('Export encrypted backup', 'View recovery words') and not self.state.get('wallet_exists')
                    unavailable |= key == 'Lock' and not (self.state.get('wallet') or {}).get('unlocked')
                    button.configure(state='disabled' if value or not self.started or unavailable else 'normal')

    def set_timeout(self, seconds):
        def saved(ignored):
            self.timeout = seconds
            self.save_preferences()
            self.refresh()
        self.call('timeout', str(seconds), done=saved)

    def friendly(self, message):
        lower = message.lower()
        rules = (
            ('password' in lower and 'at least 12' in lower, 'Enter a password of at least 12 characters.'),
            (any(s in lower for s in ('authentication', 'password or', 'decrypt')), 'Check the password or backup file.'),
            ('different network' in lower or 'address' in lower, 'Check the complete SUMUWW receiving address.'),
            ('insufficient' in lower, 'Insufficient available balance for the amount and fee.'),
            ('unlock' in lower, 'Unlock the wallet and try again.'),
            ('mnemonic' in lower or 'recovery word' in lower, 'Check the recovery words and their order.'),
            ('amount' in lower, 'Check the amount. Up to eight decimal places are supported.'),
            ('quote' in lower, 'The transfer review expired. Review it again.'),
        )
        return next((self.t(label) for matches, label in rules if matches), message)

    def submit(self, function, done=None):
        if self.busy or self.closed:
            return
        self.set_busy(True)
        def worker():
            try:
                self.results.put((done, function(), None))
            except Exception as error:
                self.results.put((done, None, str(error)))
        self.pool.submit(worker)

    def call(self, method, *args, done=None):
        def action():
            result = json.loads(runtime.call(method, *args))
            if not result['ok']:
                raise ValueError(result['error'])
            return result['data']
        self.submit(action, done or self.refresh)

    def drain(self):
        if self.closed:
            return
        try:
            while True:
                done, value, error = self.results.get_nowait()
                self.set_busy(False)
                if error:
                    messagebox.showerror(self.t('Check'), self.friendly(error), parent=self.root)
                elif done:
                    done(value)
        except queue.Empty:
            pass
        self.root.after(40, self.drain)

    def did_start(self, value):
        self.started = True
        self.state = value
        if not (value.get('wallet') or {}).get('unlocked'):
            self.clear_secret()
        self.call('timeout', str(self.timeout), done=lambda _: self.call('foreground', 'true', done=self.refresh))

    def refresh(self, ignored=None):
        if self.started and not self.busy:
            self.call('status', done=self.update)

    def update(self, value):
        if 'node' not in value:
            return self.refresh()
        previous = ((self.state.get('wallet') or {}).get('unlocked'), self.state.get('wallet_exists'))
        self.state = value
        if not (value.get('wallet') or {}).get('unlocked'):
            self.clear_secret()
        self.update_status()
        current = ((value.get('wallet') or {}).get('unlocked'), value.get('wallet_exists'))
        if self.page == 'Wallet' or previous != current:
            self.render()

    def update_status(self):
        node = self.state.get('node') or {}
        peers = node.get('peers', [])
        count = len(peers) if isinstance(peers, list) else peers if isinstance(peers, int) else 0
        sync = node.get('sync_state')
        if sync is None:
            label = 'Synchronized' if node.get('mining_ready') else 'Synchronizing' if count else 'Waiting for peers'
        else:
            label = 'Synchronized' if sync == 'ready' else 'Synchronizing' if sync in ('syncing', 'updating') else 'Waiting for peers'
        prefix = self.t('Peers: {0} · Block: {1} · ').replace('{0}', str(count)).replace('{1}', str(node.get('height', 0)))
        self.status_label.configure(text=prefix + self.t(label))

    def poll(self):
        if self.closed:
            return
        self.refresh()
        self.root.after(4000, self.poll)

    def password(self):
        return simpledialog.askstring(self.t('Wallet password'), self.t('Wallet password'), show='*', parent=self.root)

    def unlock(self):
        password = self.password()
        if password:
            self.call('unlock', password, done=self.refresh)

    def create(self, method):
        password = self.password()
        if not password:
            return
        confirmation = simpledialog.askstring(self.t('Confirm password'), self.t('Confirm password'), show='*', parent=self.root)
        if len(password) < 12 or password != confirmation:
            return messagebox.showerror(self.t('Check'), self.t('Use a matching password of at least 12 characters.'), parent=self.root)
        if method == 'recover':
            words = simpledialog.askstring(self.t('Recovery words'), self.t('Recovery words in order'), show='*', parent=self.root)
            if words:
                self.call(method, password, words, done=self.refresh)
        else:
            self.call(method, password, done=lambda value: self.call('phrase', password, done=self.show_phrase))

    def restore(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[('Encrypted wallet', '*.json'), ('All files', '*.*')])
        if not path:
            return
        try:
            with open(path, 'rb') as stream:
                raw = stream.read(runtime.keystore.MAX_WALLET_BYTES + 1)
            if len(raw) > runtime.keystore.MAX_WALLET_BYTES:
                raise ValueError(self.t('The file is unreadable or too large.'))
        except (OSError, ValueError) as error:
            return messagebox.showerror(self.t('Check file'), str(error), parent=self.root)
        password = self.password()
        if password:
            self.call('restore', password, base64.b64encode(raw).decode('ascii'), done=self.refresh)

    def backup(self):
        password = self.password()
        if password:
            self.call('backup', password, done=self.save_backup)

    def save_backup(self, value):
        path = filedialog.asksaveasfilename(parent=self.root, initialfile='SUMUWW-encrypted-backup.json', defaultextension='.json')
        if path:
            try:
                # Never overwrite an existing wallet, database or backup.
                with open(path, 'xb') as stream:
                    stream.write(base64.b64decode(value['encrypted'], validate=True))
                messagebox.showinfo(self.t('Wallet'), self.t('Encrypted backup saved'), parent=self.root)
            except (OSError, ValueError):
                messagebox.showerror(self.t('Check file'), self.t('Backup could not be saved'), parent=self.root)

    def phrase(self):
        password = self.password()
        if password:
            self.call('phrase', password, done=self.show_phrase)

    def show_phrase(self, value):
        self.clear_secret()
        window = tk.Toplevel(self.root)
        self.pending_dialog = window
        window.title(self.t('Recovery words'))
        window.transient(self.root)
        window.grab_set()
        self.label(window, text=self.t('Record the words in order and store them securely.'), wraplength=520).pack(padx=20, pady=16)
        secret = tk.Text(window, width=56, height=9)
        words = value['words'].split()
        secret.insert('1.0', '\n'.join('   '.join(f'{j+1}. {words[j]}' for j in range(i, min(i+3, len(words)))) for i in range(0, len(words), 3)))
        secret.configure(state='disabled')
        secret.pack(padx=20, pady=10)
        def dismiss():
            self.clear_secret()
            self.refresh()
        VerticalButton(window, text=self.t('Close'), command=dismiss).pack(pady=16)
        window.protocol('WM_DELETE_WINDOW', dismiss)
        # Keep recovery text out of Windows screen captures where supported.
        if sys.platform == 'win32':
            import ctypes
            window.update_idletasks()
            handle = ctypes.windll.user32.GetParent(window.winfo_id())
            ctypes.windll.user32.SetWindowDisplayAffinity(handle, 0x11)

    def clear_secret(self):
        window, self.pending_dialog = self.pending_dialog, None
        if window is not None and window.winfo_exists():
            for child in window.winfo_children():
                if isinstance(child, tk.Text):
                    child.configure(state='normal')
                    child.delete('1.0', 'end')
            window.destroy()

    def receive(self):
        address = (self.state.get('wallet') or {}).get('address')
        if address and messagebox.askokcancel(self.t('Receive SMW'), address + '\n\n' + self.t('Copy address'), parent=self.root):
            self.root.clipboard_clear()
            self.root.clipboard_append(address)

    def send(self):
        recipient = simpledialog.askstring(self.t('Send SMW'), self.t('Recipient'), parent=self.root)
        if not recipient:
            return
        amount = simpledialog.askstring(self.t('Send SMW'), self.t('Amount (SMW)'), parent=self.root)
        if not amount:
            return
        fee = simpledialog.askstring(self.t('Send SMW'), self.t('Fee (leave empty to estimate)'), parent=self.root)
        if fee is not None:
            self.call('prepare', recipient.strip(), amount, fee, done=lambda quote: self.review(dict(quote, recipient=recipient.strip())))

    def review(self, quote):
        text = '\n\n'.join(self.t(label) + ': ' + str(quote.get(key, '')) for label, key in (
            ('Recipient', 'recipient'), ('Amount', 'amount_dora'), ('Network fee', 'fee_dora'), ('Total', 'total_dora')))
        if messagebox.askokcancel(self.t('Confirm transfer'), text, parent=self.root):
            self.call('submit', quote['quote_id'], done=self.sent)
        else:
            self.refresh()

    def sent(self, result):
        if result.get('outcome') == 'accepted':
            text = self.t('Transaction submitted. Confirmation follows inclusion in a block.\n\nTransaction ID\n') + result.get('txid', '')
        elif result.get('outcome') == 'rejected':
            text = self.friendly(result.get('error', ''))
        else:
            text = self.t('Transfer outcome is unknown. Check activity before sending again.')
        messagebox.showinfo(self.t('Transfer result'), text, parent=self.root)
        self.refresh()

    def add_peer(self):
        peer = simpledialog.askstring(self.t('Add peer'), self.t('Peer address (host:port)'), parent=self.root)
        if peer:
            self.call('peer', peer, done=self.refresh)

    def history_page(self, delta):
        self.offset = max(0, self.offset + delta)
        self.call('history', str(self.offset), done=self.show_history)

    def show_history(self, value):
        if self.page != 'Activity':
            return
        lines = []
        for tx in value.get('transactions', []):
            lines.append(str(tx.get('txid', '')))
            lines.append(self.t('{0} confirmations').replace('{0}', str(tx.get('confirmations', 0))))
            units = tx.get('net_amount', 0)
            amount = ('-' if units < 0 else '') + format_amount(abs(units))
            lines.append(self.t('Amount') + ': ' + amount + ' SMW\n')
        self.history.configure(state='normal')
        self.history.delete('1.0', 'end')
        self.history.insert('1.0', '\n'.join(lines) or self.t('No transactions yet.'))
        self.history.configure(state='disabled')

    def on_unmap(self, event):
        if event.widget == self.root and self.started and self.root.state() == 'iconic':
            # Queue behind in-flight work; never bypass a transfer's single-use quote.
            self.pool.submit(lambda: runtime.call('foreground', 'false'))
            self.clear_secret()

    def on_map(self, event):
        if event.widget == self.root and self.started:
            self.pool.submit(lambda: runtime.call('foreground', 'true'))

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.clear_secret()
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.pool.submit(runtime.stop)
        # Finish wallet-owned work before releasing Tcl objects on the UI thread.
        self.pool.shutdown(wait=True)
        self.logo = None
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description='SUMUWW ordinary wallet, without mining controls')
    parser.add_argument('--version', action='version', version='SUMUWW Wallet ' + VERSION)
    parser.add_argument('--directory', type=Path, default=Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'SUMUWW/Wallet-PC')
    parser.add_argument('--network', choices=('dora', 'regtest'), default='dora')
    parser.add_argument('--no-bootstrap', action='store_true')
    parser.add_argument('--self-check', type=Path, help='Write a new report after disposable wallet/crypto checks')
    args = parser.parse_args()
    if args.self_check is not None:
        from tempfile import TemporaryDirectory
        def call(method, *values):
            result = json.loads(runtime.call(method, *values))
            if not result['ok']:
                raise RuntimeError(result['error'])
            return result['data']
        with TemporaryDirectory(prefix='sumuww-wallet-check-') as directory:
            try:
                runtime.start(Path(directory) / 'first', mobile=False, network='regtest', bootstrap=False)
                call('foreground', 'true')
                password = 'disposable-self-check-password'
                address = call('create', password)['address']
                encrypted = call('backup', password)['encrypted']
                call('lock')
                assert not call('status')['wallet']['unlocked']
                runtime.stop()
                runtime.start(Path(directory) / 'second', mobile=False, network='regtest', bootstrap=False)
                call('foreground', 'true')
                assert call('restore', password, encrypted)['address'] == address
                assert not json.loads(runtime.call('mine'))['ok']
                catalogs = list((ROOT / 'locales').glob('*.json'))
                assert len(json.loads((ROOT / 'locales/languages.json').read_text(encoding='utf-8'))) == 34
                report = {'status': 'passed', 'version': VERSION, 'checks': [
                    'encrypted wallet creation', 'backup authentication', 'lock',
                    'restore same address', 'mining command unavailable', '34 language catalogs']}
                with args.self_check.open('x', encoding='utf-8') as output:
                    json.dump(report, output, indent=2)
            finally:
                runtime.stop()
        return
    root = tk.Tk()
    WalletApp(root, args.directory, network=args.network, bootstrap=not args.no_bootstrap)
    root.mainloop()


if __name__ == '__main__':
    main()
