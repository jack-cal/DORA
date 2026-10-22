"""Tkinter wallet UI; node/key work belongs exclusively to AppService.

Every service operation returns a Future. Tk's after loop reads completed
futures on the Tk thread; no worker callback reads or changes a Tk widget.
Importing this module does not start a window or a node.
"""
from __future__ import annotations
import argparse
import os
import sys
import webbrowser
from concurrent.futures import Future
from pathlib import Path
from .windows_tk import prepare_tk
prepare_tk()
import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog, ttk
from .vertical_dialogs import messagebox, simpledialog
import weakref
from .vertical_text import (VerticalLabel, VerticalButton, VerticalCheckbutton,
                            VerticalMenubutton, VerticalTreeview, contains_mongolian, render_vertical_ppm)

from .i18n import (LANGUAGES, LocalizedText, Translator, get_translator,
                   load_language, save_language, set_translator, tr)


def _font_family(language=None):
    language = language or get_translator().language
    return {'ko': 'Malgun Gothic', 'zh': 'Microsoft YaHei', 'hi': 'Nirmala UI',
            'ar': 'Tahoma', 'ur': 'Arial', 'bn': 'Nirmala UI', 'ta': 'Nirmala UI',
            'th': 'Leelawadee UI', 'ja': 'Yu Gothic UI', 'zh-TW': 'Microsoft JhengHei',
            'zh-HK': 'Microsoft JhengHei'}.get(language, 'Segoe UI')


class LocalizedStringVar(tk.StringVar):
    """Preserve user input verbatim and retain messages for a language refresh."""

    def __init__(self, master=None, value=None, name=None):
        self._localized_message = None
        super().__init__(master, name=name)
        if value is not None:
            self.set(value)
        root = master._root() if master is not None else tk._default_root
        if root is not None:
            root.__dict__.setdefault('_sumuww_local_vars', []).append(weakref.ref(self))

    def set(self, value):
        self._localized_message = value if isinstance(value, LocalizedText) else None
        super().set(value.render() if isinstance(value, LocalizedText) else value)

    def refresh(self):
        if self._localized_message is not None:
            super().set(self._localized_message.render())


def _localized_widget(factory, *args, **options):
    text = options.get('text')
    widget = factory(*args, **options)
    if isinstance(text, LocalizedText):
        widget._localized_text = text
    return widget


def _label(*args, **options):
    numeric = options.get('style') == 'Balance.TLabel'
    rtl = get_translator().language in ('ar', 'ur') and not numeric
    options.setdefault('anchor', 'e' if rtl else 'w')
    options.setdefault('justify', 'right' if rtl else 'left')
    if len(str(options.get('text', ''))) > 80:
        options.setdefault('wraplength', 880)
    widget = _localized_widget(VerticalLabel, *args, **options)
    widget._base_wraplength = options.get('wraplength', 0)
    return widget


def _button(*args, **options):
    return _localized_widget(VerticalButton, *args, **options)


def _checkbutton(*args, **options):
    return _localized_widget(VerticalCheckbutton, *args, **options)


def _heading(table, column, **options):
    text = options.get('text')
    if isinstance(text, LocalizedText):
        table.__dict__.setdefault('_localized_headings', {})[column] = text
    return table.heading(column, **options)

class _PasswordDialog(simpledialog.Dialog):
    """Short-lived masked inputs; clear the widgets before destroying them."""

    def __init__(self, parent, *, creating=False):
        self.creating = creating
        self.password_entry = None
        self.confirm_entry = None
        super().__init__(parent, tr('New wallet password') if creating else tr('Wallet password'))

    def body(self, master):
        master.columnconfigure(0, weight=1)
        self.show_password = tk.BooleanVar(master, value=False)
        _label(master, text=tr('Password'), padding=(0, 0, 0, 6)).grid(row=0, column=0, sticky='w')
        self.password_entry = ttk.Entry(master, show='●', width=36)
        self.password_entry.grid(row=1, column=0, sticky='ew')
        if self.creating:
            _label(master, text=tr('Confirm password'), padding=(0, 10, 0, 6)).grid(row=2, column=0, sticky='w')
            self.confirm_entry = ttk.Entry(master, show='●', width=36)
            self.confirm_entry.grid(row=3, column=0, sticky='ew')
            _label(master, text=tr('Enter at least 12 characters. You also need this password to restore a backup.'), wraplength=330, padding=(0, 10, 0, 0)).grid(row=5, column=0, sticky='w')
        self.visibility_button = _checkbutton(master, text=tr('Show password'), variable=self.show_password,
                                             command=self._toggle_password)
        self.visibility_button.grid(row=4 if self.creating else 2, column=0, sticky='w', pady=(8, 0))
        return self.password_entry

    def _toggle_password(self):
        mask = '' if self.show_password.get() else '●'
        for entry in (self.password_entry, self.confirm_entry):
            if entry is not None:
                entry.configure(show=mask)

    def buttonbox(self):
        box = ttk.Frame(self, padding=10)
        _button(box, text=tr('Confirm'), command=self.ok, width=10).pack(side='left', padx=5)
        _button(box, text=tr('Cancel'), command=self.cancel, width=10).pack(side='left', padx=5)
        self.bind('<Return>', self.ok)
        self.bind('<Escape>', self.cancel)
        box.pack()

    def validate(self):
        password = self.password_entry.get()
        try:
            valid_size = 1 <= len(password.encode('utf-8')) <= 1024
        except UnicodeError:
            valid_size = False
        if not valid_size:
            messagebox.showerror(tr('Confirm password'), tr('The password must be 1–1,024 bytes in UTF-8.'), parent=self)
            return False
        if self.creating and len(password) < 12:
            messagebox.showerror(tr('Confirm password'), tr('A new wallet password must be at least 12 characters.'), parent=self)
            return False
        if self.creating and password != self.confirm_entry.get():
            messagebox.showerror(tr('Confirm password'), tr('The passwords do not match.'), parent=self)
            return False
        return True

    def apply(self):
        self.result = self.password_entry.get()
        self._clear()

    def _clear(self):
        for entry in (self.password_entry, self.confirm_entry):
            if entry is not None:
                try:
                    entry.delete(0, tk.END)
                except tk.TclError:
                    pass

    def cancel(self, event=None):
        self._clear()
        super().cancel(event)

class _RecoveryPhraseDialog(simpledialog.Dialog):
    """Explicit, short-lived phrase display/input; never copy it automatically."""

    def __init__(self, parent, *, phrase=None):
        self._display_phrase = phrase
        self.readonly = phrase is not None
        self.phrase_text = None
        super().__init__(parent, tr('Recovery phrase') if self.readonly else tr('Recover from phrase'))
        self._display_phrase = None

    def body(self, master):
        master.columnconfigure(0, weight=1)
        _label(master, text=tr('Keep these 24 English words private and in order. Anyone with them can spend this wallet. The wallet password is separate.'),
               wraplength=470).grid(row=0, column=0, sticky='w', pady=(0, 10))
        self.phrase_text = tk.Text(master, width=55, height=5, wrap='word',
                                   font=(_font_family(), 11), undo=False)
        self.phrase_text.grid(row=1, column=0, sticky='ew')
        if self.readonly:
            self.phrase_text.insert('1.0', self._display_phrase)
            self._display_phrase = None
            self.phrase_text.configure(state='disabled')
        else:
            _label(master, text=tr('Enter the 24 English recovery words. Recovery creates a new encrypted file with the password you choose.'),
                   wraplength=470).grid(row=2, column=0, sticky='w', pady=(10, 0))
        return self.phrase_text

    def buttonbox(self):
        box = ttk.Frame(self, padding=10)
        _button(box, text=tr('Close') if self.readonly else tr('Confirm'), command=self.ok).pack(side='left', padx=5)
        if not self.readonly:
            _button(box, text=tr('Cancel'), command=self.cancel).pack(side='left', padx=5)
        self.bind('<Escape>', self.cancel)
        box.pack()

    def validate(self):
        if self.readonly:
            return True
        from .hd import mnemonic_to_entropy
        phrase = self.phrase_text.get('1.0', 'end-1c')
        try:
            if len(phrase) > 1024 or len(phrase.split()) != 24:
                raise ValueError('Invalid recovery phrase')
            if len(mnemonic_to_entropy(phrase)) != 32:
                raise ValueError('Invalid recovery phrase')
        except ValueError:
            messagebox.showerror(tr('Recovery phrase'), tr('Enter a valid 24-word English recovery phrase.'), parent=self)
            return False
        return True

    def apply(self):
        self.result = None if self.readonly else ' '.join(self.phrase_text.get('1.0', 'end-1c').split())
        self._clear()

    def _clear(self):
        self._display_phrase = None
        if self.phrase_text is not None:
            try:
                self.phrase_text.configure(state='normal')
                self.phrase_text.delete('1.0', tk.END)
            except tk.TclError:
                pass

    def cancel(self, event=None):
        self._clear()
        super().cancel(event)


class _ConnectionDialog(simpledialog.Dialog):
    """Edit a snapshot; status polling never changes inputs during editing."""

    def __init__(self, parent, connection):
        self.connection = dict(connection)
        super().__init__(parent, tr('Connection settings'))

    def body(self, master):
        master.columnconfigure(0, weight=1)
        self.allow_internet = tk.BooleanVar(master, value=bool(self.connection.get('allow_internet')))
        self.allow_lan = tk.BooleanVar(master, value=bool(self.connection.get('allow_lan')))
        _checkbutton(master, text=tr('Allow internet connections'), variable=self.allow_internet).grid(row=0, column=0, sticky='w')
        _checkbutton(master, text=tr('Allow local network (LAN) connections'), variable=self.allow_lan).grid(row=1, column=0, sticky='w', pady=(4, 8))
        self.auto_address = tk.BooleanVar(master, value=bool(self.connection.get('auto_address', False)))
        self.auto_address_button = _checkbutton(master, text=tr('Set my node address automatically'), variable=self.auto_address, command=self._address_mode)
        self.auto_address_button.grid(row=2, column=0, sticky='w')
        _label(master, text=tr('Automatic mode selects local addresses and the listening port. No address registration is required.'), style='Muted.TLabel', wraplength=480).grid(row=3, column=0, sticky='w', pady=(4, 8))
        addresses = self.connection.get('own_addresses') or []
        actual = ', '.join(str(value) for value in addresses[:4]) or tr('No usable network address found.')
        _label(master, text=tr('Local node addresses: {0}', actual), style='Muted.TLabel', wraplength=480).grid(row=4, column=0, sticky='w')
        _label(master, text=tr('External access is not verified.'), style='Muted.TLabel', wraplength=480).grid(row=5, column=0, sticky='w', pady=(4, 8))
        _label(master, text=tr('Listening address · IPv4:port')).grid(row=6, column=0, sticky='w', pady=(0, 4))
        self.listen = LocalizedStringVar(master, value=self.connection.get('listen') or '127.0.0.1:0')
        self.listen_entry = ttk.Entry(master, textvariable=self.listen, width=55)
        self.listen_entry.grid(row=7, column=0, sticky='ew')
        _label(master, text=tr('Port 0 selects a port automatically. The actual address appears in the wallet.'), style='Muted.TLabel', wraplength=480).grid(row=8, column=0, sticky='w', pady=(4, 10))
        _label(master, text=tr('Public contact address (optional)')).grid(row=9, column=0, sticky='w', pady=(0, 4))
        self.public_contact = tk.StringVar(master, value=self.connection.get('public_contact') or '')
        self.public_contact_entry = ttk.Entry(master, textvariable=self.public_contact, width=55)
        self.public_contact_entry.grid(row=10, column=0, sticky='ew')
        _label(master, text=tr('Public IPv4:port for other nodes to reach this listener. Leave empty unless inbound access is configured.'), style='Muted.TLabel', wraplength=480).grid(row=11, column=0, sticky='w', pady=(4, 10))
        _label(master, text=tr('Saved peers · IP or domain:port, one per line')).grid(row=12, column=0, sticky='w', pady=(0, 4))
        self.peers = tk.Text(master, width=55, height=6, font=(_font_family(), 10), wrap='none', relief='solid', borderwidth=1)
        self.peers.grid(row=13, column=0, sticky='ew')
        self.peers.insert('1.0', '\n'.join(self.connection.get('peers') or []))
        _label(master, text=tr('Automatic discovery uses reachable peers. You can also add an IP or domain:port manually. Applying connection settings restarts connections and keeps your wallet and chain history.'), style='Muted.TLabel', wraplength=480).grid(row=14, column=0, sticky='w', pady=(10, 0))
        self._address_mode()
        return self.auto_address_button if self.auto_address.get() else self.listen_entry

    def _address_mode(self):
        state = 'disabled' if self.auto_address.get() else 'normal'
        self.listen_entry.configure(state=state)
        self.public_contact_entry.configure(state=state)

    def buttonbox(self):
        box = ttk.Frame(self, padding=10)
        _button(box, text=tr('Apply · Restart connections'), command=self.ok).pack(side='left', padx=5)
        _button(box, text=tr('Cancel'), command=self.cancel, width=10).pack(side='left', padx=5)
        self.bind('<Escape>', self.cancel)
        box.pack()

    def validate(self):
        if not self.auto_address.get() and not self.listen.get().strip():
            messagebox.showerror(tr('Connection settings'), tr('Enter a listening address. Example: 127.0.0.1:0'), parent=self)
            return False
        return True

    def apply(self):
        peers = list(dict.fromkeys((line.strip() for line in self.peers.get('1.0', 'end-1c').splitlines() if line.strip())))
        self.result = {'listen': self.listen.get().strip() or '127.0.0.1:0', 'peers': peers, 'allow_internet': self.allow_internet.get(), 'allow_lan': self.allow_lan.get(), 'advertise': '' if self.auto_address.get() else self.public_contact.get().strip(), 'auto_address': self.auto_address.get()}


class _PrivacyDialog(simpledialog.Dialog):
    def __init__(self, parent, options):
        self.options = options
        super().__init__(parent, tr('IP protection'))

    def body(self, master):
        self.mode = tk.StringVar(master, value=self.options.get('mode', 'direct'))
        picker = ttk.Combobox(master, textvariable=self.mode, values=('direct', 'tor', 'i2p'), state='readonly')
        picker.pack(fill='x')
        picker.bind('<<ComboboxSelected>>', lambda _: self.ok())
        if self.options.get('i2p_address'):
            _label(master, text='I2P').pack(anchor='w')
            address = tk.StringVar(master, value=self.options['i2p_address']+':18444')
            ttk.Entry(master, textvariable=address, state='readonly', width=65).pack(fill='x')

    def buttonbox(self):
        box = ttk.Frame(self, padding=10)
        _button(box, text=tr('Apply'), command=self.ok, width=12).pack(side='left', padx=5)
        _button(box, text=tr('Cancel'), command=self.cancel, width=12).pack(side='left', padx=5)
        box.pack()
        self.bind('<Return>', self.ok)
        self.bind('<Escape>', self.cancel)

    def validate(self):
        try:
            from .privacy import settings
            self.result = settings(self.mode.get())
            return True
        except ValueError as error:
            messagebox.showerror(tr('IP protection'), str(error), parent=self)
            return False

    def apply(self):
        pass


class _PrivacyHelpDialog(simpledialog.Dialog):
    def __init__(self, parent, mode):
        self.mode = mode
        super().__init__(parent, tr('IP protection')+' · '+mode.upper())

    def body(self, master):
        from .privacy import NOTICE_DIRECT, NOTICE_TOR, NOTICE_I2P
        key = {'direct': NOTICE_DIRECT, 'tor': NOTICE_TOR, 'i2p': NOTICE_I2P}[self.mode]
        _label(master, text=tr(key), wraplength=500, justify='left').pack(fill='x', pady=14)
        self.hide_help = tk.BooleanVar(master, value=False)
        _checkbutton(master, text=tr('Do not show this help again.'), variable=self.hide_help).pack(anchor='w', pady=(0, 10))

    def buttonbox(self):
        box = ttk.Frame(self, padding=10)
        _button(box, text=tr('Run'), command=self.ok, width=12).pack(side='left', padx=5)
        _button(box, text=tr('Cancel'), command=self.cancel, width=12).pack(side='left', padx=5)
        box.pack()
        self.bind('<Escape>', self.cancel)

    def apply(self):
        from .privacy_ui import save_hidden
        try:
            save_hidden(self.mode, self.hide_help.get())
        except (OSError, ValueError):
            # A help preference failure must never change network mode silently.
            pass
        self.result = True


class _RpcDialog(simpledialog.Dialog):
    """Only localhost is offered; no secret is loaded into a Tk widget."""

    def __init__(self, parent, settings):
        self.settings = dict(settings)
        super().__init__(parent, tr('RPC/API settings'))

    def body(self, master):
        master.columnconfigure(0, weight=1)
        self.enabled = tk.BooleanVar(master, value=bool(self.settings.get('configured_enabled')))
        _checkbutton(master, text=tr('Enable local RPC/API'), variable=self.enabled).grid(row=0, column=0, sticky='w')
        _label(master, text=tr('RPC port · 0 selects automatically')).grid(row=1, column=0, sticky='w', pady=(10, 4))
        self.port = tk.StringVar(master, value=str(self.settings.get('port', 18443)))
        self.port_entry = ttk.Entry(master, textvariable=self.port, width=12)
        self.port_entry.grid(row=2, column=0, sticky='w')
        _label(master, text=tr('Current RPC/API: {0}', self.settings.get('endpoint') or tr('off')),
               wraplength=540, style='Muted.TLabel').grid(row=3, column=0, sticky='ew', pady=(10, 6))
        _label(master, text=tr('Authentication token file')).grid(row=4, column=0, sticky='w')
        token_path = self.settings.get('token_file') or ''
        self.token_path = tk.StringVar(master, value=token_path)
        ttk.Entry(master, textvariable=self.token_path, state='readonly', width=65).grid(row=5, column=0, sticky='ew', pady=(4, 6))
        _button(master, text=tr('Open token folder'), command=self._open_token_folder).grid(row=6, column=0, sticky='w')
        _label(master, text=tr('Only programs on this computer can connect using the authentication token. The API provides queries and signed transaction submission; it does not expose wallet private keys or sign payments.'),
               wraplength=540, style='Muted.TLabel').grid(row=7, column=0, sticky='ew', pady=(10, 0))
        _label(master, text=tr('Applying changes only RPC/API settings. Your wallet and mining state are kept, and settings are reused next time.'),
               wraplength=540, style='Muted.TLabel').grid(row=8, column=0, sticky='ew', pady=(6, 0))
        return self.port_entry

    def buttonbox(self):
        box = ttk.Frame(self, padding=10)
        _button(box, text=tr('Apply'), command=self.ok, width=10).pack(side='left', padx=5)
        _button(box, text=tr('Cancel'), command=self.cancel, width=10).pack(side='left', padx=5)
        self.bind('<Escape>', self.cancel)
        box.pack()

    def validate(self):
        value = self.port.get().strip()
        if not value.isascii() or not value.isdigit() or not 0 <= int(value) <= 65535:
            messagebox.showerror(tr('RPC/API settings'), tr('Enter an integer RPC port from 0 to 65,535.'), parent=self)
            return False
        return True

    def apply(self):
        self.result = {'enabled': self.enabled.get(), 'port': int(self.port.get().strip())}

    def _open_token_folder(self):
        path = Path(self.settings.get('token_file') or '')
        try:
            if not path.is_absolute() or not path.parent.is_dir():
                raise OSError()
            if sys.platform == 'win32':
                os.startfile(str(path.parent))
            elif not webbrowser.open(path.parent.as_uri()):
                raise OSError()
        except OSError:
            messagebox.showerror(tr('RPC/API settings'), tr('Could not open the token folder. Check the node data folder.'), parent=self)

def _error_message(error: BaseException) -> str:
    """Translate known failures without displaying arbitrary backend contents."""
    description = str(error).lower()
    if 'local mempool resource limit' in description:
        return tr('This node\'s pending transaction pool is full. Your transfer was not queued. Try again after pending transactions are confirmed.')
    if 'connect and synchronize' in description:
        return tr('You can start SMW mining after synchronizing with connected nodes.')
    if 'cancel' in description:
        return tr('Mining stopped.')
    if isinstance(error, FileNotFoundError):
        return tr('File not found. Select the wallet or backup file again.')
    if isinstance(error, PermissionError):
        return tr('Check file permissions. Another program may be using the file.')
    if 'file or network operation failed' in description:
        return tr('File access or node connection failed. Check folder permissions and connection addresses.')
    if 'password or encrypted' in description or 'authentication' in type(error).__name__.lower():
        return tr('The password is incorrect or the wallet file has changed.')
    if 'already exists' in description:
        return tr('A file with this name already exists. Choose a new filename.')
    if 'insufficient' in description:
        return tr('Insufficient available confirmed funds. Check immature rewards and pending transfers.')
    if 'payment quote' in description:
        return tr('Payment confirmation expired or the wallet state changed. Review again.')
    if 'rpc' in description:
        return tr('Could not apply RPC/API settings. Check the port and token file.')
    if 'locked' in description or 'unlock' in description:
        return tr('Open and unlock the wallet, then try again.')
    if 'wallet' in description and ('select' in description or 'open' in description or 'loaded' in description):
        return tr('Create a wallet or open an existing one first.')
    if 'profile' in description or 'genesis' in description or 'different network' in description or ('unknown development network' in description) or ('wallet version, network' in description):
        return tr('The address, wallet, and data folder do not match the selected development network.')
    if 'address' in description or 'checksum' in description or 'witness' in description:
        return tr('The recipient address is invalid or belongs to another development network.')
    if 'amount' in description or 'decimal' in description or 'fee' in description:
        return tr('Enter a positive amount and a fee of 0 or more. Up to 8 decimal places are allowed.')
    if any((word in description for word in ('endpoint', 'ipv4', 'ipv6', 'hostname', 'dns', 'port', 'loopback', 'listen', 'bind', 'internet', 'peer', 'lan'))):
        return tr('Check the listening and peer addresses (IP·domain:port), and internet and LAN permissions.')
    if 'password' in description:
        return tr('Check the password format. New wallets require at least 12 characters.')
    if 'nonce' in description or 'mining' in description:
        return tr('The mining search for this block did not finish. Check the status, then restart.')
    if 'database' in description or 'sqlite' in description or 'directory' in description:
        return tr('Check the data folder. Other wallet windows must use separate folders.')
    return tr('The operation could not finish. Check your entries and file paths, then try again.')

class _HistoryDialog(tk.Toplevel):
    """Read public wallet history without interrupting node or mining work."""

    PAGE_SIZE = 50

    def __init__(self, owner):
        super().__init__(owner.root)
        self.owner = owner
        self._wallet_address = owner._wallet['address']
        self._closed = False
        self._request = 0
        self._timer = None
        self._busy = False
        self.offset = 0
        self.total = 0
        self.height = 0
        self.transactions = []
        self.title(tr('Full history') + ' · SUMUWW')
        self.transient(owner.root)
        self.geometry('1080x520')
        self.minsize(820, 380)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Escape>', lambda event: self.close())
        body = ttk.Frame(self, padding=14)
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        _label(body, text=tr('Wallet address: {0}', self._wallet_address),
               wraplength=980).grid(row=0, column=0, columnspan=2, sticky='ew')
        _label(body, text=tr('Current chain · mining rewards, incoming payments and sends'),
               wraplength=980).grid(row=1, column=0, columnspan=2, sticky='ew', pady=(4, 10))
        self.table = VerticalTreeview(body, columns=('kind', 'amount', 'confirmations', 'height', 'txid'),
                                  show='headings', height=13, selectmode='browse')
        for name, caption, width, anchor in (
                ('kind', tr('Transaction'), 130, 'w'),
                ('amount', tr('Change SMW'), 150, 'e'),
                ('confirmations', tr('Confirm'), 100, 'center'),
                ('height', tr('Block height'), 100, 'center'),
                ('txid', tr('Transaction ID'), 490, 'w')):
            _heading(self.table, name, text=caption)
            self.table.column(name, width=width, minwidth=width, anchor=anchor, stretch=name == 'txid')
        self.table.grid(row=2, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(body, orient='vertical', command=self.table.yview)
        vertical.grid(row=2, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(body, orient='horizontal', command=self.table.xview)
        horizontal.grid(row=3, column=0, sticky='ew')
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.state_text = LocalizedStringVar(self)
        _label(body, textvariable=self.state_text, wraplength=980).grid(
            row=4, column=0, columnspan=2, sticky='ew', pady=(10, 8))
        controls = ttk.Frame(body)
        controls.grid(row=5, column=0, columnspan=2, sticky='ew')
        self.previous_button = _button(controls, text=tr('Previous'),
                                        command=lambda: self.reload(max(0, self.offset - self.PAGE_SIZE)))
        self.previous_button.pack(side='left')
        self.next_button = _button(controls, text=tr('Next'),
                                    command=lambda: self.reload(self.offset + self.PAGE_SIZE))
        self.next_button.pack(side='left', padx=(8, 0))
        self.refresh_button = _button(controls, text=tr('Refresh'), command=self.reload)
        self.refresh_button.pack(side='left', padx=(8, 0))
        _button(controls, text=tr('Close'), command=self.close).pack(side='right')
        self.reload(0)

    def _same_wallet(self):
        wallet = self.owner._wallet
        return not self.owner._closing and bool(wallet) and wallet.get('address') == self._wallet_address

    def _controls(self):
        self.previous_button.configure(state='normal' if not self._busy and self.offset > 0 else 'disabled')
        self.next_button.configure(state='normal' if not self._busy and self.offset + self.PAGE_SIZE < self.total else 'disabled')
        self.refresh_button.configure(state='disabled' if self._busy else 'normal')

    def reload(self, offset=None):
        if self._closed or self._busy:
            return
        if not self._same_wallet():
            self.close()
            return
        requested_offset = self.offset if offset is None else offset
        self._request += 1
        request = self._request
        self._busy = True
        self.state_text.set(tr('Loading history…'))
        self._controls()
        try:
            future = self.owner.service.transaction_history(offset=requested_offset, limit=self.PAGE_SIZE)
        except Exception as error:
            self._failed(error)
            return
        self._poll(future, request)

    def _poll(self, future, request):
        self._timer = None
        if self._closed or request != self._request:
            return
        if not self._same_wallet():
            self.close()
            return
        if not future.done():
            self._timer = self.after(60, lambda: self._poll(future, request))
            return
        try:
            result = future.result()
            if result.get('address') != self._wallet_address:
                self.close()
                return
            self.total = result['total']
            self.offset = result['offset']
            self.height = result['height']
            self.transactions = list(result['transactions'])
        except Exception as error:
            self._failed(error)
            return
        self._busy = False
        if not self.total:
            self.offset = 0
        if self.total and self.offset >= self.total:
            # A chain change can remove entries while the last page is open.
            self.reload(((self.total - 1) // self.PAGE_SIZE) * self.PAGE_SIZE)
            return
        self._render()
        self._controls()

    def _render(self):
        from .primitives import format_amount
        children = self.table.get_children()
        if children:
            self.table.delete(*children)
        for transaction in self.transactions:
            amount = transaction.get('net_amount', 0)
            if type(amount) is not int:
                continue
            amount_text = ('−' if amount < 0 else '+' if amount > 0 else '') + format_amount(abs(amount))
            kind = tr('Mining reward') if transaction.get('coinbase') else tr('Send') if amount < 0 else tr('Incoming') if amount > 0 else tr('Transaction')
            pending = transaction.get('status') == 'pending'
            confirmations = tr('Pending') if pending else tr('{0:,} conf.', transaction.get('confirmations', 0))
            height = tr('Pending') if pending else transaction.get('height', '')
            self.table.insert('', 'end', values=(kind, amount_text, confirmations, height, transaction.get('txid', '')))
        if self.total:
            self.state_text.set(tr('Transactions {0:,}–{1:,} of {2:,} · Chain height {3:,}',
                                   self.offset + 1, self.offset + len(self.transactions), self.total, self.height))
        else:
            self.state_text.set(tr('No transactions for this wallet.'))

    def _failed(self, error):
        self._busy = False
        self.state_text.set(tr('History could not be loaded. Use Refresh to try again.') + ' ' + _error_message(error))
        self._controls()

    def refresh_language(self):
        if self._closed:
            return
        self.title(tr('Full history') + ' · SUMUWW')
        for widget in self.owner._walk_widgets(self):
            message = getattr(widget, '_localized_text', None)
            if message is not None:
                widget.configure(text=message.render())
            if isinstance(widget, ttk.Label):
                rtl = get_translator().language in ('ar', 'ur')
                widget.configure(anchor='e' if rtl else 'w', justify='right' if rtl else 'left')
            for column, message in getattr(widget, '_localized_headings', {}).items():
                widget.heading(column, text=message.render())
        if not self._busy:
            self._render()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._request += 1
        if self._timer is not None:
            try:
                self.after_cancel(self._timer)
            except tk.TclError:
                pass
            self._timer = None
        if self.owner._history_dialog is self:
            self.owner._history_dialog = None
        self.destroy()


class SumuwwApp:
    """A real wallet screen with a Future-returning service injected by caller."""

    def __init__(self, root: tk.Tk, service, *, language=None, language_path=None):
        self.root = root
        self.service = service
        self._language_path = language_path
        self.translator = Translator(language or load_language(language_path))
        set_translator(self.translator)
        self.root._sumuww_translator = self.translator
        source_root = Path(__file__).resolve().parent.parent
        self._document_roots = [source_root / 'docs' / 'i18n',
                                Path(sys.executable).resolve().parent / 'docs' / 'i18n',
                                Path(sys.executable).resolve().parent / 'documents' / 'docs' / 'i18n']
        self.directory = Path(getattr(service, 'directory', Path.cwd() / 'data' / 'local'))
        profile = getattr(service, 'network', 'dora')
        self.network_name = getattr(profile, 'name', str(profile))
        self._started = False
        self._busy = False
        self._dialog_open = False
        self._closing = False
        self._destroyed = False
        self._status_inflight = False
        self._status_error_shown = False
        self._wallet_epoch = 0
        self._node_snapshot = {}
        self._transactions_snapshot = []
        self._history_dialog = None
        self._update_dialog = None
        self._connection_snapshot = None
        self._rpc_snapshot = None
        self._wallet = None
        self._pending = []
        self._mining = False
        self._mining_waiting = False
        self._mine_inflight = False
        self._mine_target = 0
        self._mine_completed = 0
        self._stop_requested = False
        self._logo = None
        self._build()
        self.root.protocol('WM_DELETE_WINDOW', self._close)
        self.root.after(40, self._pump)
        self.root.after(10, self._start)
        self.root.after(1000, self._poll_status)

    def _build(self):
        self.root.title(tr('SUMUWW'))
        self._layout_scale = max(1.0, round(self.root.winfo_fpixels('1i') / 96, 2))
        available_width = max(320, self.root.winfo_screenwidth() - 48)
        available_height = max(240, self.root.winfo_screenheight() - 80)
        self.root.geometry(f'{min(round(1000 * self._layout_scale), available_width)}x'
                           f'{min(round(900 * self._layout_scale), available_height)}')
        self.root.minsize(min(round(940 * self._layout_scale), available_width),
                          min(round(700 * self._layout_scale), available_height))
        self._minimum_content_width = round(926 * self._layout_scale)
        self.root.configure(background='#f3f5f9')
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('TFrame', background='#f3f5f9')
        style.configure('TLabel', background='#f3f5f9', foreground='#243047', font=('Malgun Gothic', 10))
        style.configure('TButton', font=('Malgun Gothic', 10), padding=(9, 4))
        style.configure('TEntry', padding=5, font=('Malgun Gothic', 10))
        style.configure('Card.TFrame', background='white')
        style.configure('Card.TLabel', background='white')
        style.configure('CardTitle.TLabel', background='white', font=('Malgun Gothic', 11, 'bold'))
        style.configure('Muted.TLabel', foreground='#647086', font=('Malgun Gothic', 9))
        style.configure('CardMuted.TLabel', background='white', foreground='#647086', font=('Malgun Gothic', 9))
        style.configure('Treeview', font=('Malgun Gothic', 9), rowheight=round(23 * self._layout_scale))
        style.configure('Treeview.Heading', font=('Malgun Gothic', 9))
        style.configure('Title.TLabel', font=('Malgun Gothic', 18, 'bold'))
        style.configure('Balance.TLabel', background='white', foreground='#183e70', font=('Malgun Gothic', 14, 'bold'))
        style.configure('Accent.TButton', background='#245cb0', foreground='white', borderwidth=0)
        style.map('Accent.TButton', background=[('disabled', '#dfe5ee'), ('active', '#194887')], foreground=[('disabled', '#8792a2')])
        self._style = style
        self._configure_fonts()
        shell = ttk.Frame(self.root)
        shell.pack(fill='both', expand=True)
        shell.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)
        self._canvas = tk.Canvas(shell, background='#f3f5f9', highlightthickness=0)
        vertical = ttk.Scrollbar(shell, orient='vertical', command=self._canvas.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        self._canvas.grid(row=0, column=0, sticky='nsew')
        self._horizontal_scroll = ttk.Scrollbar(shell, orient='horizontal', command=self._canvas.xview)
        self._horizontal_scroll.grid(row=1, column=0, sticky='ew')
        self._horizontal_scroll.grid_remove()
        self._canvas.configure(yscrollcommand=vertical.set, xscrollcommand=self._horizontal_scroll.set)
        outer = ttk.Frame(self._canvas, padding=(22, 12, 22, 10))
        self._outer = outer
        self._outer_window = self._canvas.create_window((0, 0), window=outer, anchor='nw')
        outer.bind('<Configure>', lambda event: self._canvas.configure(scrollregion=self._canvas.bbox('all')))
        self._canvas.bind('<Configure>', self._resize_content)
        self._canvas.bind('<MouseWheel>', self._scroll_content)
        outer.columnconfigure(0, weight=1)
        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky='ew', pady=(0, 6))
        assets = Path(__file__).resolve().parent.parent / 'assets'
        try:
            # Release assets are antialiased at their display size; Tk keeps
            # their transparent pixels and original proportions unchanged.
            from .brand import artwork
            self._logo = tk.PhotoImage(master=self.root, file=str(artwork(self.translator.language, scale=self._layout_scale)))
            self._logo_label = _label(header, image=self._logo)
            self._logo_label.pack(side='left', padx=(0, 15))
        except (OSError, tk.TclError):
            pass
        from .brand import apply_window_icon
        apply_window_icon(self.root, self.translator.language)
        titles = ttk.Frame(header)
        self._titles = titles
        titles.pack(side='left')
        _label(titles, text=tr('SUMUWW'), style='Title.TLabel').pack(anchor='w')
        _label(titles, text=tr('Private-key wallet · Send · Mine'), style='Muted.TLabel', wraplength=340).pack(anchor='w', pady=(2, 0))
        header_right = ttk.Frame(header)
        header_right.pack(side='right', anchor='n')
        language_row = ttk.Frame(header_right)
        language_row.pack(anchor='e')
        _label(language_row, text=tr('Language'), style='Muted.TLabel').pack(side='left', padx=(0, 8))
        self.language_choice = LocalizedStringVar(value=dict(LANGUAGES)[self.translator.language])
        self.language_combo = ttk.Combobox(language_row, textvariable=self.language_choice,
                                         values=[label for _, label in LANGUAGES], state='readonly', width=21)
        self.language_combo.pack(side='left')
        self.language_combo.bind('<<ComboboxSelected>>', self._language_selected)
        self.docs_button = _localized_widget(VerticalMenubutton, language_row, text=tr('Documents'))
        self.docs_button.pack(side='left', padx=(8, 0))
        self._docs_menu = tk.Menu(self.docs_button, tearoff=False)
        self._docs_menu_records = []
        self._docs_menu_images = {}
        for caption, name in (('Whitepaper', 'WHITEPAPER'), ('Protocol specification', 'SUMUWW_PROTOCOL_SPEC'),
                              ('User guide', 'README'), ('Operations guide', 'NETWORK_RUNBOOK'),
                              ('RPC/API guide', 'RPC_API')):
            text = tr(caption)
            self._docs_menu.add_command(label=text, command=lambda name=name: self._open_document(name))
            self._docs_menu_records.append((len(self._docs_menu_records), text))
            if contains_mongolian(text):
                index = len(self._docs_menu_records) - 1
                ppm, _, _ = render_vertical_ppm(str(text), inline=180)
                image = tk.PhotoImage(master=self.root, data=ppm, format='PPM')
                self._docs_menu_images[index] = image
                self._docs_menu.entryconfigure(index, image=image, compound='none')
        self.docs_button.configure(menu=self._docs_menu)
        from . import __version__
        update_row = ttk.Frame(header_right)
        update_row.pack(anchor='e', pady=(5, 0))
        _label(update_row, text='v'+__version__, style='Muted.TLabel').pack(side='left', padx=(0, 8))
        self.update_button = _button(update_row, text=tr('Check for updates'), command=self._check_updates)
        self.update_button.pack(side='left', padx=(0, 6))
        _button(update_row, text='GitHub', command=self._open_github).pack(side='left')
        _label(header_right, text=tr('Network: {0}', tr('SUMUWW') if self.network_name == 'dora' else self.network_name), style='Muted.TLabel').pack(anchor='e', pady=(5, 0))
        node_card = ttk.Frame(outer, style='Card.TFrame', padding=(14, 6))
        node_card.grid(row=1, column=0, sticky='ew', pady=(0, 6))
        self.node_text = LocalizedStringVar(value=tr('Starting the node…'))
        self.rules_text = LocalizedStringVar(value=tr('Reading block rules…'))
        self.sync_text = LocalizedStringVar(value=tr('Checking node connections and synchronization…'))
        _label(node_card, textvariable=self.node_text, style='CardTitle.TLabel', wraplength=870).pack(fill='x')
        _label(node_card, textvariable=self.rules_text, style='CardMuted.TLabel', wraplength=870).pack(fill='x', pady=(3, 0))
        _label(node_card, textvariable=self.sync_text, style='CardMuted.TLabel', wraplength=870).pack(fill='x', pady=(3, 0))
        wallet_card = ttk.Frame(outer, style='Card.TFrame', padding=(14, 6))
        wallet_card.grid(row=2, column=0, sticky='ew', pady=(0, 6))
        wallet_card.columnconfigure(0, weight=1)
        wallet_top = ttk.Frame(wallet_card, style='Card.TFrame')
        wallet_top.grid(row=0, column=0, sticky='ew')
        _label(wallet_top, text=tr('My wallet'), style='CardTitle.TLabel').pack(side='left')
        self.wallet_text = LocalizedStringVar(value=tr('Create a wallet or open an existing one.'))
        _label(wallet_top, textvariable=self.wallet_text, style='CardMuted.TLabel', wraplength=660).pack(side='right')
        controls = ttk.Frame(wallet_card, style='Card.TFrame')
        controls.grid(row=1, column=0, sticky='ew', pady=(7, 7))
        self._wallet_controls = controls
        self.create_button = _button(controls, text=tr('New wallet'), command=self._create_wallet, style='Accent.TButton')
        self.open_button = _button(controls, text=tr('Open wallet'), command=self._open_wallet)
        self.lock_button = _button(controls, text=tr('Lock'), command=self._lock_wallet)
        self.backup_button = _button(controls, text=tr('Back up'), command=self._backup_wallet)
        self.restore_button = _button(controls, text=tr('Restore'), command=self._restore_wallet)
        self.seed_create_button = _button(controls, text=tr('Seed wallet'), command=self._create_seed_wallet)
        self.seed_show_button = _button(controls, text=tr('Recovery phrase'), command=self._show_seed_wallet)
        self.seed_recover_button = _button(controls, text=tr('Recover from phrase'), command=self._recover_seed_wallet)
        self._wallet_buttons = (self.create_button, self.open_button, self.lock_button, self.backup_button,
                                self.restore_button, self.seed_create_button, self.seed_show_button,
                                self.seed_recover_button)
        for column, button in enumerate(self._wallet_buttons):
            button.grid(row=0, column=column, padx=(0, 7), sticky='w')
        address_row = ttk.Frame(wallet_card, style='Card.TFrame')
        address_row.grid(row=2, column=0, sticky='ew')
        address_row.columnconfigure(1, weight=1)
        _label(address_row, text=tr('Receive address'), style='Card.TLabel', wraplength=150).grid(row=0, column=0, padx=(0, 12))
        self.address_text = LocalizedStringVar(value='')
        self.address_entry = ttk.Entry(address_row, textvariable=self.address_text, state='readonly')
        self.address_entry.grid(row=0, column=1, sticky='ew')
        self.copy_button = _button(address_row, text=tr('Copy address'), command=self._copy_address)
        self.copy_button.grid(row=0, column=2, padx=(8, 0))
        balance_card = ttk.Frame(outer, style='Card.TFrame', padding=(14, 6))
        balance_card.grid(row=3, column=0, sticky='ew', pady=(0, 6))
        self.balance_texts = {}
        for column, (key, caption) in enumerate((('total_smw', tr('Confirmed balance')), ('available_smw', tr('Available')), ('immature_smw', tr('Immature rewards')), ('pending_smw', tr('Pending change')))):
            balance_card.columnconfigure(column, weight=1, uniform='balance')
            frame = ttk.Frame(balance_card, style='Card.TFrame')
            frame.grid(row=0, column=column, sticky='ew', padx=(0 if column == 0 else 12, 0))
            _label(frame, text=caption, style='CardMuted.TLabel', wraplength=205).pack(anchor='w')
            variable = LocalizedStringVar(value='—')
            self.balance_texts[key] = variable
            _label(frame, textvariable=variable, style='Balance.TLabel').pack(anchor='w', pady=(3, 0))
        _label(balance_card, text=tr('SMW units · Available: mature balance excluding pending spends · Pending change: incoming (+), outgoing and fees (−)'), style='CardMuted.TLabel').grid(row=1, column=0, columnspan=4, sticky='w', pady=(6, 0))
        send_card = ttk.Frame(outer, style='Card.TFrame', padding=(14, 6))
        send_card.grid(row=4, column=0, sticky='ew', pady=(0, 6))
        send_card.columnconfigure(0, weight=1)
        _label(send_card, text=tr('Send'), style='CardTitle.TLabel').grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.send_address = LocalizedStringVar()
        self.send_amount = LocalizedStringVar()
        self.send_fee = LocalizedStringVar(value='0.001')
        self.manual_fee = tk.BooleanVar(value=False)
        self.fee_mode_text = LocalizedStringVar(value=tr('Automatic · exact fee shown at confirmation'))
        for column, caption in enumerate((tr('Recipient address'), tr('Amount SMW'), tr('Fee SMW'))):
            _label(send_card, text=caption, style='CardMuted.TLabel', wraplength=440 if column == 0 else 140).grid(row=1, column=column, sticky='w', padx=(0 if column == 0 else 9, 0))
        self.send_to_entry = ttk.Entry(send_card, textvariable=self.send_address)
        self.amount_entry = ttk.Entry(send_card, textvariable=self.send_amount, width=13)
        self.fee_entry = ttk.Entry(send_card, textvariable=self.send_fee, width=13)
        for column, entry in enumerate((self.send_to_entry, self.amount_entry, self.fee_entry)):
            entry.grid(row=2, column=column, sticky='ew', padx=(0 if column == 0 else 9, 0))
        self.send_button = _button(send_card, text=tr('Confirm transfer'), command=self._send, style='Accent.TButton')
        self.send_button.grid(row=2, column=3, padx=(10, 0))
        self.manual_fee_button = _checkbutton(send_card, text=tr('Advanced: set fee manually'), variable=self.manual_fee,
                                             command=self._sync_controls)
        self.manual_fee_button.grid(row=3, column=0, columnspan=2, sticky='w', pady=(5, 0))
        _label(send_card, textvariable=self.fee_mode_text, style='CardMuted.TLabel',
               wraplength=350).grid(row=3, column=2, columnspan=2, sticky='w', padx=(9, 0), pady=(5, 0))
        _label(send_card, text=tr('Transactions affect the confirmed balance after inclusion in a block.'), style='CardMuted.TLabel', wraplength=870).grid(row=4, column=0, columnspan=4, sticky='w', pady=(6, 0))
        lower = ttk.Frame(outer)
        lower.grid(row=5, column=0, sticky='ew', pady=(0, 6))
        lower.columnconfigure(0, weight=1, uniform='tool')
        lower.columnconfigure(1, weight=1, uniform='tool')
        mining_card = ttk.Frame(lower, style='Card.TFrame', padding=(14, 6))
        mining_card.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        _label(mining_card, text=tr('Mining'), style='CardTitle.TLabel').pack(anchor='w')
        mining_controls = ttk.Frame(mining_card, style='Card.TFrame')
        mining_controls.pack(fill='x', pady=(6, 6))
        _label(mining_controls, text=tr('Blocks'), style='Card.TLabel').pack(side='left', padx=(0, 7))
        self.mine_count = LocalizedStringVar(value='1')
        self.mine_count_entry = ttk.Spinbox(mining_controls, from_=1, to=10000, textvariable=self.mine_count, width=7)
        self.mine_count_entry.pack(side='left', padx=(0, 8))
        mining_actions = ttk.Frame(mining_card, style='Card.TFrame')
        mining_actions.pack(fill='x', pady=(0, 6))
        self.mine_start_button = _button(mining_actions, text=tr('Start mining'), command=self._start_mining)
        self.mine_start_button.pack(side='left', padx=(0, 6))
        self.mine_stop_button = _button(mining_actions, text=tr('Stop'), command=self._stop_mining)
        self.mine_stop_button.pack(side='left')
        self.hardware_button = _button(mining_card, text=tr('Mining device'), command=self._configure_mining_hardware)
        self.hardware_button.pack(anchor='w', pady=(2, 6))
        self.mine_progress = ttk.Progressbar(mining_card, mode='determinate', maximum=1)
        self.mine_progress.pack(fill='x')
        self.mine_text = LocalizedStringVar(value=tr('Pending'))
        _label(mining_card, textvariable=self.mine_text, style='CardMuted.TLabel').pack(anchor='w', pady=(4, 3))
        _label(mining_card, text=tr('Your first mining reward becomes usable after 100 blocks of chain progress. Mining time varies with the work required.'), wraplength=405, style='CardMuted.TLabel').pack(anchor='w')
        peers_card = ttk.Frame(lower, style='Card.TFrame', padding=(14, 6))
        peers_card.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        peer_heading = ttk.Frame(peers_card, style='Card.TFrame')
        peer_heading.pack(fill='x')
        _label(peer_heading, text=tr('Node connections'), style='CardTitle.TLabel', wraplength=200).pack(side='left')
        self.settings_button = _button(peer_heading, text=tr('Connection settings'), command=self._configure_network)
        _button(peer_heading, text=tr('IP protection'), command=self._configure_privacy).pack(side='right', padx=4)
        self.settings_button.pack(side='right')
        peer_row = ttk.Frame(peers_card, style='Card.TFrame')
        peer_row.pack(fill='x', pady=(6, 6))
        self.peer_endpoint = LocalizedStringVar()
        self.peer_entry = ttk.Entry(peer_row, textvariable=self.peer_endpoint)
        self.peer_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))
        self.peer_button = _button(peer_row, text=tr('Add peer'), command=self._add_peer)
        self.peer_button.pack(side='left')
        self.connection_text = LocalizedStringVar(value=tr('Reading connection settings…'))
        _label(peers_card, textvariable=self.connection_text, style='CardMuted.TLabel', wraplength=405).pack(fill='x', pady=(2, 4))
        self.own_mode_text = LocalizedStringVar(value='')
        _label(peers_card, textvariable=self.own_mode_text, style='CardMuted.TLabel', wraplength=405).pack(fill='x', pady=(0, 4))
        _label(peers_card, text=tr('Add a peer IP·domain:port. Saved peers and connection settings are kept for the next launch.'), wraplength=405, style='CardMuted.TLabel').pack(anchor='w')
        rpc_row = ttk.Frame(peers_card, style='Card.TFrame')
        rpc_row.pack(fill='x', pady=(8, 0))
        self.rpc_text = LocalizedStringVar(value=tr('RPC/API off'))
        _label(rpc_row, textvariable=self.rpc_text, style='CardMuted.TLabel', wraplength=240).pack(side='left', fill='x', expand=True)
        self.rpc_button = _button(rpc_row, text=tr('RPC/API settings'), command=self._configure_rpc)
        self.rpc_button.pack(side='right')
        history_card = ttk.Frame(outer, style='Card.TFrame', padding=(14, 5))
        history_card.grid(row=6, column=0, sticky='ew', pady=(0, 6))
        history_card.columnconfigure(0, weight=1)
        history_heading = ttk.Frame(history_card, style='Card.TFrame')
        history_heading.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 5))
        _label(history_heading, text=tr('Recent transactions · Confirmations'), style='CardTitle.TLabel', wraplength=410).pack(side='left')
        history_actions = ttk.Frame(history_heading, style='Card.TFrame')
        history_actions.pack(side='right')
        self.history_button = _button(history_actions, text=tr('Full history'), command=self._open_history)
        self.history_button.pack(side='right', padx=(10, 0))
        _label(history_actions, text=tr('Last 10 · Confirmations follow the current chain'), style='CardMuted.TLabel', wraplength=250).pack(side='right')
        self.transaction_table = VerticalTreeview(history_card, columns=('kind', 'amount', 'confirmations', 'txid'), show='headings', height=3, selectmode='browse')
        for name, caption, width, anchor in (('kind', tr('Transaction'), 140, 'w'), ('amount', tr('Change SMW'), 150, 'e'), ('confirmations', tr('Confirm'), 110, 'center'), ('txid', tr('Transaction ID'), 410, 'w')):
            _heading(self.transaction_table, name, text=caption)
            self.transaction_table.column(name, width=width, minwidth=width, anchor=anchor, stretch=name == 'txid')
        self.transaction_table.grid(row=1, column=0, sticky='ew')
        history_scrollbar = ttk.Scrollbar(history_card, orient='vertical', command=self.transaction_table.yview)
        history_scrollbar.grid(row=1, column=1, sticky='ns')
        self.transaction_table.configure(yscrollcommand=history_scrollbar.set)
        self.footer_text = LocalizedStringVar(value=tr('Starting the node…'))
        self.footer = _label(outer, textvariable=self.footer_text, wraplength=920)
        self.footer.grid(row=7, column=0, sticky='ew')
        self._mongolian_panels = dict(titles=titles, header_right=header_right, language_row=language_row, node=node_card,
            wallet=wallet_card, wallet_top=wallet_top, controls=controls, address=address_row,
            balance=balance_card, send=send_card, mining=mining_card, peers=peers_card,
            mining_controls=mining_controls, mining_actions=mining_actions, peer_heading=peer_heading,
            peer_row=peer_row, rpc_row=rpc_row)
        self._mongolian_geometry = {}
        self._apply_mongolian_layout()
        for widget in self._walk_widgets(outer):
            if isinstance(widget, (ttk.Frame, ttk.Label, ttk.Button)):
                widget.bind('<MouseWheel>', self._scroll_content, add='+')
        self._sync_controls()

    def _apply_mongolian_layout(self):
        """Compact columns for this script; restore every other language's layout."""
        active = self.translator.language == 'mn-Mong'
        original = self._mongolian_geometry
        if not active:
            if original:
                for widget in original:
                    widget.pack_forget(); widget.grid_forget()
                for widget, (manager, options) in original.items():
                    getattr(widget, manager)(**options)
                original.clear()
                for panel, columns in self._mongolian_columns.items():
                    for column, options in columns.items(): panel.columnconfigure(column, **options)
                self.transaction_table.configure(height=3)
                for frame in self._mongolian_panels['balance'].winfo_children():
                    if isinstance(frame,ttk.Frame):frame.rowconfigure(0,minsize=0)
            return
        if original:
            return
        def remember(widget):
            if widget not in original:
                manager = widget.winfo_manager()
                original[widget] = manager, getattr(widget, manager + '_info')()
            widget.pack_forget(); widget.grid_forget()
        def pack_row(parent):
            children = parent.winfo_children()
            for widget in children: remember(widget)
            for widget in children: widget.pack(side='left', anchor='n', padx=(0, 12))
        p = self._mongolian_panels
        self._mongolian_columns = {p[name]: {col:p[name].columnconfigure(col) for col in range(5)}
                                   for name in ('wallet','send','mining','peers')}
        pack_row(p['titles']); pack_row(p['header_right']); pack_row(p['node']); pack_row(p['wallet_top'])
        # Keep each caption beside its value; a vertical caption above a number
        # leaves a tall empty band across the entire four-column card.
        for frame in p['balance'].winfo_children():
            if isinstance(frame,ttk.Frame):
                for widget in frame.winfo_children():remember(widget)
                for column,widget in enumerate(frame.winfo_children()):
                    widget.grid(row=0,column=column,sticky='w',padx=(0,8),pady=(0,4))
                frame.rowconfigure(0,minsize=0)
        note = p['balance'].winfo_children()[-1]
        note._vertical_compact=True;note._vertical_inline=55;note.refresh_vertical()
        remember(note); note.grid(row=1, column=0, columnspan=4, sticky='w', pady=(8,0))
        for widget, row, col, span in ((p['wallet_top'],0,0,1),(p['address'],0,1,1),(p['controls'],1,0,2)):
            remember(widget); widget.grid(row=row,column=col,columnspan=span,sticky='nw' if widget is p['wallet_top'] else 'ew',padx=(0,12),pady=4)
        p['wallet'].columnconfigure(0,weight=0,minsize=0)
        p['wallet'].columnconfigure(1,weight=1)
        # Put captions beside their numeric fields rather than creating tall empty rows.
        children = p['send'].winfo_children()
        for widget in children: remember(widget)
        labels = [w for w in children if isinstance(w, ttk.Label)]
        labels[0].grid(row=0,column=0,rowspan=2,sticky='nw',padx=(0,12))
        for col, label in enumerate(labels[1:4],1): label.grid(row=0,column=col,sticky='w',padx=6)
        for col, entry in enumerate((self.send_to_entry,self.amount_entry,self.fee_entry),1):
            entry.grid(row=1,column=col,sticky='ew',padx=6,pady=6)
        self.send_button.grid(row=0,column=4,rowspan=2,sticky='n',padx=6)
        self.manual_fee_button.grid(row=2,column=1,sticky='nw',padx=6,pady=(8,0))
        labels[4].grid(row=2,column=2,columnspan=2,sticky='nw',padx=6,pady=(8,0))
        labels[5].grid(row=2,column=4,sticky='nw',padx=6,pady=(8,0))
        p['send'].columnconfigure(0,weight=0)
        p['send'].columnconfigure(1,weight=1)
        # Status paragraphs share a row of columns instead of stacking full-width images.
        for name in ('mining','peers'):
            children=p[name].winfo_children()
            for widget in children: remember(widget)
            if name=='mining':
                placements=[(0,0,1),(0,1,1),(1,1,1),(0,2,1),(2,1,2),(3,0,1),(3,1,2)]
            else:
                placements=[(0,0,3),(1,0,3),(2,0,1),(2,1,1),(2,2,1),(3,0,3)]
            for widget,(row,col,span) in zip(children,placements):
                widget.grid(row=row,column=col,columnspan=span,sticky='nw' if isinstance(widget,ttk.Label) else 'ew',padx=4,pady=5)
            for col in range(3): p[name].columnconfigure(col,weight=1)
        self.transaction_table.configure(height=1)

    def _configure_fonts(self):
        family = _font_family(self.translator.language)
        arabic = self.translator.language == 'ar'
        for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont'):
            try:
                tkfont.nametofont(name, root=self.root).configure(family=family, size=13 if arabic else 10)
            except tk.TclError:
                pass
        for name, size, bold in (('TLabel', 10, False), ('TButton', 10, False),
                                 ('TEntry', 10, False), ('TCombobox', 10, False),
                                 ('TMenubutton', 10, False), ('TCheckbutton', 10, False),
                                 ('CardTitle.TLabel', 11, True), ('Muted.TLabel', 9, False),
                                 ('CardMuted.TLabel', 9, False), ('Treeview', 9, False),
                                 ('Treeview.Heading', 9, False), ('Title.TLabel', 18, True),
                                 ('Balance.TLabel', 14, True)):
            if arabic:
                size += 3 if size < 14 else 2
            font = (family, size, 'bold') if bold else (family, size)
            self._style.configure(name, font=font)
        self._style.configure('Treeview', rowheight=round((32 if arabic else 23) * self._layout_scale))
        self._style.configure('Muted.TLabel', foreground='#475569' if arabic else '#647086')
        self._style.configure('CardMuted.TLabel', foreground='#475569' if arabic else '#647086')

    @staticmethod
    def _walk_widgets(parent):
        for child in parent.winfo_children():
            yield child
            yield from SumuwwApp._walk_widgets(child)

    def _resize_content(self, event):
        width = max(event.width, self._minimum_content_width)
        self._canvas.itemconfigure(self._outer_window, width=width)
        if width > event.width:
            self._horizontal_scroll.grid()
        else:
            self._horizontal_scroll.grid_remove()
            self._canvas.xview_moveto(0)
        self.root.after_idle(self._reflow_wrapping)

    def _reflow_wrapping(self):
        if self._destroyed:
            return
        for widget in self._walk_widgets(self._outer):
            maximum = getattr(widget, '_base_wraplength', 0)
            if maximum:
                width = widget.master.winfo_width()
                if width > 1:
                    bound = maximum if widget.master == self._titles else min(maximum, max(120, width - 28))
                    widget.configure(wraplength=bound)
        if self.translator.language == 'mn-Mong':
            p = self._mongolian_panels
            bounded = [(w,max(140,(p['node'].winfo_width()-72)//3)) for w in p['node'].winfo_children()]
            mining=p['mining'].winfo_children();peers=p['peers'].winfo_children()
            bounded += [(mining[5],75),(mining[6],max(220,p['mining'].winfo_width()-125)),
                        (peers[2],100),(peers[4],max(200,p['peers'].winfo_width()-165))]
            for widget,bound in bounded:
                widget._vertical_max_width=bound
                widget.refresh_vertical()
        control_width = self._wallet_controls.winfo_width()
        if control_width > 1:
            if self.translator.language == 'mn-Mong':
                columns = max(1, min(8, control_width // max(button.winfo_reqwidth() + 7 for button in self._wallet_buttons)))
            else:
                columns = 5 if sum(button.winfo_reqwidth() + 7 for button in self._wallet_buttons) <= control_width else 3
            for index, button in enumerate(self._wallet_buttons):
                button.grid_configure(row=index // columns, column=index % columns)
        self._canvas.configure(scrollregion=self._canvas.bbox('all'))

    def _scroll_content(self, event):
        self._canvas.yview_scroll(-int(event.delta / 120), 'units')
        return 'break'

    def _language_selected(self, event=None):
        selection = self.language_choice.get()
        language = next((code for code, label in LANGUAGES if label == selection), None)
        if language is None:
            return
        self.set_language(language)

    def _refresh_brand(self):
        from .brand import artwork, apply_window_icon
        try:
            logo = tk.PhotoImage(master=self.root, file=str(artwork(self.translator.language, scale=self._layout_scale)))
            self._logo_label.configure(image=logo)
            self._logo = logo
        except (OSError, tk.TclError):
            pass
        apply_window_icon(self.root, self.translator.language)

    def set_language(self, language):
        if self._closing or self._busy or self._dialog_open:
            self.language_choice.set(dict(LANGUAGES)[self.translator.language])
            return False
        self.translator.set_language(language)
        set_translator(self.translator)
        self.language_choice.set(dict(LANGUAGES)[language])
        saved = True
        try:
            save_language(language, self._language_path)
        except OSError:
            saved = False
        self._configure_fonts()
        if hasattr(self, '_logo_label'):
            self._refresh_brand()
        references = []
        for reference in self.root.__dict__.get('_sumuww_local_vars', []):
            variable = reference()
            if variable is not None:
                references.append(reference)
                try:
                    variable.refresh()
                except tk.TclError:
                    pass
        self.root._sumuww_local_vars = references
        for widget in self._walk_widgets(self._outer):
            message = getattr(widget, '_localized_text', None)
            if message is not None:
                widget.configure(text=message.render())
            if isinstance(widget, ttk.Label):
                if not widget.cget('image'):
                    rtl = language in ('ar', 'ur') and widget.cget('style') != 'Balance.TLabel'
                    widget.configure(anchor='e' if rtl else 'w', justify='right' if rtl else 'left')
                    widget.configure(wraplength=getattr(widget, '_base_wraplength', 0))
            for column, message in getattr(widget, '_localized_headings', {}).items():
                widget.heading(column, text=message.render())
        for index, message in self._docs_menu_records:
            self._docs_menu.entryconfigure(index, label=message.render(), image='')
            if contains_mongolian(message.render()):
                ppm, _, _ = render_vertical_ppm(message.render(), inline=180)
                image = tk.PhotoImage(master=self.root, data=ppm, format='PPM')
                self._docs_menu_images[index] = image
                self._docs_menu.entryconfigure(index, image=image, compound='none')
            else:
                self._docs_menu_images.pop(index, None)
        self._docs_menu.configure(font=(_font_family(), 13 if self.translator.language == 'ar' else 10))
        if self._history_dialog is not None:
            self._history_dialog.refresh_language()
        self._apply_mongolian_layout()
        if self._node_snapshot or self._wallet is not None:
            self._apply_status({'node': self._node_snapshot, 'wallet': self._wallet,
                                'connection': self._connection_snapshot,
                                'rpc': self._rpc_snapshot,
                                'transactions': self._transactions_snapshot})
        if not saved:
            self._message(tr('Could not save the language setting. The next launch may start in English.'), error=True)
        elif not (self._mining or self._mine_inflight):
            self._message(tr('Language changed.'))
        self._sync_controls()
        self.root.after_idle(self._reflow_wrapping)
        return True

    def _open_document(self, name):
        if name not in ('WHITEPAPER', 'SUMUWW_PROTOCOL_SPEC', 'README', 'NETWORK_RUNBOOK', 'RPC_API'):
            return
        candidates = [root / self.translator.language / (name + '.html') for root in self._document_roots]
        document = next((path for path in candidates if path.is_file()), None)
        try:
            if document is None:
                raise FileNotFoundError()
            if sys.platform == 'win32':
                os.startfile(str(document.resolve()))
            elif not webbrowser.open(document.resolve().as_uri()):
                raise OSError()
        except OSError:
            messagebox.showerror(tr('Documents'), tr('Could not open the document. Check the distribution folder.'), parent=self.root)

    def _open_github(self, url=None):
        from .updates import RELEASES_URL, release_url
        try:
            if not webbrowser.open(release_url(url or RELEASES_URL)):raise OSError()
        except (OSError, ValueError):
            messagebox.showerror(tr('Check for updates'), tr('Could not open the download page.'), parent=self.root)

    def _check_updates(self):
        if self._closing:return
        if self._update_dialog is not None and self._update_dialog.winfo_exists():
            self._update_dialog.lift();return
        from . import __version__
        from . import updates
        import threading
        dialog=tk.Toplevel(self.root);self._update_dialog=dialog
        dialog.title(tr('Check for updates'));dialog.transient(self.root)
        box=ttk.Frame(dialog,padding=20);box.pack(fill='both',expand=True)
        _label(box,text='SUMUWW '+__version__).pack(anchor='w')
        message=LocalizedStringVar(dialog,value=tr('Checking for updates…'))
        dialog._update_message=message
        _label(box,textvariable=message,wraplength=480).pack(anchor='w',pady=12)
        target={'url':updates.RELEASES_URL}
        _button(box,text=tr('Open download page'),command=lambda:self._open_github(target['url'])).pack(side='left',padx=(0,10))
        _button(box,text=tr('Close'),command=dialog.destroy).pack(side='right')
        def gone(event):
            if event.widget is dialog and self._update_dialog is dialog:
                self._update_dialog=None
                dialog._update_message=None
        dialog.bind('<Destroy>',gone)
        future=Future()
        def query():
            try:future.set_result(updates.check(__version__))
            except Exception:future.set_exception(RuntimeError('Update lookup failed'))
        def usable():return not self._closing and self._update_dialog is dialog and dialog.winfo_exists()
        def done(result):
            if not usable():return
            target['url']=result['url']
            message.set(str(tr('An update is available.' if result['available'] else 'No newer release is available.'))+'\nGitHub '+result['version'])
        def failed(error):
            if usable():message.set(tr('Could not check for updates. Open GitHub to check directly.'))
        self._watch(future,done,failed)
        threading.Thread(target=query,name='sumuww-update-check',daemon=True).start()

    def _message(self, text: str, *, error=False):
        if self._destroyed:
            return
        self.footer_text.set(text)
        self.footer.configure(foreground='#ad3434' if error else '#38516c')

    def _watch(self, future, success, failure=None):
        self._pending.append((future, success, failure))

    def _pump(self):
        if self._destroyed:
            return
        ready, waiting = ([], [])
        for entry in self._pending:
            (ready if entry[0].done() else waiting).append(entry)
        self._pending = waiting
        for future, success, failure in ready:
            if self._destroyed:
                return
            try:
                result = future.result()
            except Exception as error:
                if failure is not None:
                    failure(error)
            else:
                if success is not None:
                    success(result)
        if not self._destroyed:
            self.root.after(40, self._pump)

    def _start(self):
        if self._closing:
            return
        try:
            future = self.service.start()
        except Exception as error:
            self._startup_failed(error)
            return
        self._watch(future, self._startup_done, self._startup_failed)

    def _startup_done(self, result):
        if self._closing:
            return
        self._started = True
        self._message(tr('The node is ready. Create a wallet or open an existing one.'))
        if isinstance(result, dict) and 'node' in result:
            self._apply_status(result)
        self._sync_controls()
        self._request_status()

    def _startup_failed(self, error):
        self.node_text.set(tr('Node startup failed'))
        self.rules_text.set(tr('Use a separate data folder for each window.'))
        self._message(tr('Could not start the node. ') + _error_message(error), error=True)
        self._sync_controls()
        if not self._closing:
            messagebox.showerror(tr('Start SMW node'), tr('Could not start the node.\n') + _error_message(error) + tr('\nClose this window and check the launch settings.'), parent=self.root)

    def _poll_status(self):
        if self._destroyed or self._closing:
            return
        self._request_status()
        self.root.after(1000, self._poll_status)

    def _request_status(self):
        if not self._started or self._status_inflight or self._closing:
            return
        self._status_inflight = True
        try:
            future = self.service.status()
        except Exception as error:
            self._status_failed(error)
            return
        epoch = self._wallet_epoch
        self._watch(future, lambda result: self._status_done(result, epoch), self._status_failed)

    def _status_done(self, result, epoch=None):
        self._status_inflight = False
        self._status_error_shown = False
        if not self._closing:
            if epoch is None or epoch == self._wallet_epoch:
                self._apply_status(result)
            else:
                self._request_status()

    def _status_failed(self, error):
        self._status_inflight = False
        if not self._closing and (not self._status_error_shown):
            self._message(tr('Could not read the status. ') + _error_message(error), error=True)
            self._status_error_shown = True

    def _apply_status(self, status):
        if not isinstance(status, dict):
            return
        node = status.get('node') or {}
        self._node_snapshot = node
        self._hardware_mode = ((status.get("mining") or {}).get("hardware") or {}).get("mode", "cpu")
        listen = node.get('listen') or {}
        if isinstance(listen, dict):
            endpoint = f"{listen.get('host', '—')}:{listen.get('port', '—')}"
        else:
            endpoint = str(listen)
        own = node.get('own_addresses') or []
        if own:
            endpoint = ', '.join(str(value) for value in own[:3])
        elif endpoint.startswith('0.0.0.0:'):
            endpoint = tr('No usable network address found.')
        peers = node.get('peers', 0)
        if isinstance(peers, (list, tuple, dict)):
            peers = len(peers)
        self.node_text.set(tr('Block height {0}   ·   Connected nodes {1}   ·   Address {2}', node.get('height', '—'), peers, endpoint))
        if self.network_name != 'dora':
            self.sync_text.set(tr('Test network · Offline mining is available.'))
        elif node.get('listener_active') is False:
            self.sync_text.set(tr('Node listener unavailable · Restoring connections…'))
        elif self._mining_allowed():
            self.sync_text.set(tr('Connected · Validating new blocks · Mining on validated chain')
                               if node.get('live_block_updates') else
                               tr('Synchronized with connected nodes · Mining ready'))
        elif peers:
            self.sync_text.set(tr('Synchronizing with connected nodes · Mining waiting'))
        else:
            initial = node.get('bootstrap') or {}
            known = node.get('configured_peers', 0) + (node.get('peer_discovery') or {}).get('candidates', 0)
            lan = node.get('lan_discovery') or {}
            dht = node.get('dht_discovery') or {}
            if dht.get('state') == 'active':
                remaining = dht.get('next_query_seconds')
                if (not dht.get('round_in_progress') and type(remaining) is int
                        and remaining > 0):
                    self.sync_text.set(tr('No connected nodes · Next automatic search in {0}s', remaining))
                else:
                    self.sync_text.set(tr('Searching the distributed network for SMW nodes…'))
            elif dht.get('state') == 'unavailable':
                self.sync_text.set(tr('Distributed node search is unavailable. Retrying…'))
            elif lan.get('state') == 'active':
                self.sync_text.set(tr('Searching for SMW nodes on your local network…'))
            elif lan.get('state') == 'no_lan_interface' and not known and not (
                    initial.get('dns_seed_providers') or initial.get('fallback_peers')):
                self.sync_text.set(tr('No local network interface or initial node discovery source is available.'))
            elif initial.get('enabled') and not (initial.get('dns_seed_providers') or initial.get('fallback_peers') or known):
                self.sync_text.set(tr('No initial node discovery sources are configured.'))
            elif initial.get('enabled'):
                self.sync_text.set(tr('Searching automatically for reachable SMW nodes…'))
            else:
                self.sync_text.set(tr('Waiting for peers · Mining starts after synchronization'))
        connection = status.get('connection')
        if isinstance(connection, dict):
            self._set_connection(connection)
        rpc = status.get('rpc')
        if isinstance(rpc, dict):
            self._set_rpc(rpc)
        if self._connection_snapshot is not None:
            enabled = bool(self._connection_snapshot.get('allow_internet'))
            self.connection_text.set(tr('Internet {0}   ·   Connected nodes {1}   ·   Saved peers {2}', tr('enabled') if enabled else tr('off'), peers, len(self._connection_snapshot.get('peers') or [])))
            self.own_mode_text.set(tr('Own node address is managed automatically.') if self._connection_snapshot.get('auto_address') else '')
        interval = node.get('retarget_interval')
        timespan = node.get('target_timespan')
        profile = getattr(self.service, 'network', None)
        interval = interval or getattr(profile, 'retarget_interval', None)
        timespan = timespan or getattr(profile, 'target_timespan', None)
        if type(interval) is int and interval > 0 and (type(timespan) is int):
            spacing = timespan // interval
            mode = tr('Fixed difficulty') if node.get('no_retarget', getattr(profile, 'no_retarget', False)) else tr('Difficulty adjustment every {0:,} blocks', interval)
            activation = node.get('asert_activation_height')
            if activation is not None:
                mode = ('ASERT · '+tr('Every block')) if node.get('height', 0)+1 >= activation else tr('ASERT from block {0:,}', activation)
            activation = node.get('dgw_activation_height')
            if activation is not None:
                mode = ('DGW v3 · '+tr('Every block')) if node.get('height', 0)+1 >= activation else tr('DGW v3 from block {0:,}', activation)
                cadence_height = node.get('dgw_interval_activation_height', getattr(profile, 'dgw_interval_activation_height', None))
                cadence = node.get('dgw_retarget_interval', getattr(profile, 'dgw_retarget_interval', 1))
                if cadence_height is not None and node.get('height', 0)+1 >= cadence_height and cadence > 1:
                    mode = 'DGW v3 · '+tr('Difficulty adjustment every {0:,} blocks', cadence)
            self.rules_text.set(tr('Average target {0:,}s   ·   {1}   ·   Network {2}', spacing, mode, tr('SUMUWW') if self.network_name == 'dora' else self.network_name))
        wallet = status.get('wallet')
        previous_address = self._wallet.get('address') if self._wallet else None
        self._wallet = None if not wallet else {name: wallet.get(name) for name in ('address', 'path', 'unlocked', 'total_smw', 'spendable_smw', 'available_smw', 'pending_smw', 'immature_smw')}
        if self._wallet is not None and 'kind' in wallet:
            self._wallet['kind'] = wallet['kind']
        if self._wallet:
            self.address_text.set(str(self._wallet.get('address') or ''))
            path_name = Path(self._wallet.get('path') or tr('Wallet')).name
            self.wallet_text.set(path_name + ' · ' + (tr('Unlocked') if self._wallet.get('unlocked') else tr('Locked')))
            for name, variable in self.balance_texts.items():
                value = self._wallet.get(name)
                variable.set(str(value) if value is not None else '—')
        else:
            self.address_text.set('')
            self.wallet_text.set(tr('Create a wallet or open an existing one.'))
            for variable in self.balance_texts.values():
                variable.set('—')
        if 'transactions' in status:
            self._transactions_snapshot = list(status.get('transactions') or [])[:10]
        elif not self._wallet or previous_address != self._wallet.get('address'):
            self._transactions_snapshot = []
        self._show_transactions()
        history_dialog = getattr(self, '_history_dialog', None)
        if history_dialog is not None and not history_dialog._same_wallet():
            history_dialog.close()
        if self._mining and not self._closing:
            mining = status.get('mining') or {}
            waiting = not self._mining_allowed() or mining.get('state') == 'waiting'
            if waiting:
                self._wait_for_mining_sync()
            elif self._mining_waiting:
                self._mining_waiting = False
                self.mine_text.set(tr('Mining · {0}/{1} blocks completed', self._mine_completed, self._mine_target))
                self._message(tr('Computing proof of work. Use Stop to cancel the current search.'))
                if not self._mine_inflight:
                    self.root.after(10, self._mine_next)
            if not waiting and mining.get('state') == 'running':
                waited = getattr(self, '_mine_network_wait_total', 0.0) + mining.get('network_wait_seconds', 0.0)
                self.mine_text.set(tr('Mining · {0}/{1} blocks completed · Network wait {2}s',
                                      self._mine_completed, self._mine_target, round(waited, 1)))
        elif not self._mining_allowed() and (not (self._mining or self._mine_inflight)):
            self.mine_text.set(tr('Mining waiting · Node connections and synchronization are required.'))
        elif self._mining_allowed() and getattr(self.mine_text._localized_message, 'key', None) == 'Mining waiting · Node connections and synchronization are required.':
            self.mine_text.set(tr('Pending'))
        self._sync_controls()

    def _mining_allowed(self):
        return self.network_name != 'dora' or self._node_snapshot.get('mining_ready') is True

    def _open_history(self):
        if not self._started or not self._wallet or self._closing or self._busy or self._dialog_open:
            return
        if self._history_dialog is not None:
            self._history_dialog.lift()
            return
        dialog = _HistoryDialog(self)
        # A synchronous rejected result can close the dialog during construction.
        if not dialog._closed:
            self._history_dialog = dialog

    def _show_transactions(self):
        from .primitives import format_amount
        children = self.transaction_table.get_children()
        if children:
            self.transaction_table.delete(*children)
        for transaction in self._transactions_snapshot:
            amount = transaction.get('net_amount', 0)
            if type(amount) is not int:
                continue
            amount_text = ('−' if amount < 0 else '+' if amount > 0 else '') + format_amount(abs(amount))
            kind = tr('Mining reward') if transaction.get('coinbase') else tr('Send') if amount < 0 else tr('Incoming') if amount > 0 else tr('Transaction')
            confirmation_text = tr('Pending') if transaction.get('status') == 'pending' else tr('{0:,} conf.', transaction.get('confirmations', 0))
            self.transaction_table.insert('', 'end', values=(kind, amount_text, confirmation_text, transaction.get('txid', '')))

    def _sync_controls(self):
        ready = self._started and (not (self._closing or self._busy or self._dialog_open or self._mining or self._mine_inflight))
        self.language_combo.configure(state='readonly' if not (self._closing or self._busy or self._dialog_open) else 'disabled')
        self.docs_button.configure(state='normal' if not (self._closing or self._dialog_open) else 'disabled')
        self.rpc_button.configure(state='normal' if self._rpc_can_act() else 'disabled')
        wallet = bool(self._wallet)
        self.history_button.configure(state='normal' if self._started and wallet and not (self._closing or self._busy or self._dialog_open) else 'disabled')
        unlocked = wallet and bool(self._wallet.get('unlocked'))
        for button in (self.create_button, self.open_button, self.restore_button, self.peer_button,
                       self.settings_button, self.seed_create_button, self.seed_recover_button):
            button.configure(state='normal' if ready else 'disabled')
        for button in (self.create_button, self.open_button, self.restore_button,
                       self.seed_create_button, self.seed_recover_button):
            button.configure(state='normal' if ready and not unlocked else 'disabled')
        self.seed_show_button.configure(state='normal' if ready and wallet and self._wallet.get('kind') == 'hd' else 'disabled')
        self.lock_button.configure(state='normal' if ready and unlocked else 'disabled')
        self.send_button.configure(state='normal' if ready and unlocked else 'disabled')
        for entry in (self.send_to_entry, self.amount_entry):
            entry.configure(state='normal' if ready else 'disabled')
        self.manual_fee_button.configure(state='normal' if ready else 'disabled')
        self.fee_entry.configure(state=('normal' if self.manual_fee.get() else 'readonly') if ready else 'disabled')
        self.fee_mode_text.set(tr('Manual · use the entered fee') if self.manual_fee.get()
                               else tr('Automatic · exact fee shown at confirmation'))
        self.mine_start_button.configure(state='normal' if ready and wallet and self._mining_allowed() else 'disabled')
        self.backup_button.configure(state='normal' if ready and wallet else 'disabled')
        self.copy_button.configure(state='normal' if wallet and (not self._closing) else 'disabled')
        self.mine_stop_button.configure(state='normal' if self._mining and (not self._closing) else 'disabled')
        self.mine_count_entry.configure(state='normal' if ready else 'disabled')
        if hasattr(self, 'hardware_button'):
            self.hardware_button.configure(state='normal' if ready else 'disabled')

    def _configure_mining_hardware(self):
        def action():
            height = self._node_snapshot.get('height', 0)
            from .hardware_mining import UNLOCK_HEIGHTS
            modes = [mode for mode, minimum in UNLOCK_HEIGHTS.items() if height >= minimum]
            dialog = tk.Toplevel(self.root)
            dialog.title(tr('Mining device'))
            dialog.transient(self.root)
            dialog.grab_set()
            _label(dialog, text=tr('CPU always · GPU from 12,000 · ASIC from 12,000'), wraplength=440).pack(padx=18,pady=12)
            current = getattr(self, '_hardware_mode', 'cpu')
            selected = tk.StringVar(master=dialog, value=current if current in modes else 'cpu')
            for mode in ('cpu', 'gpu', 'asic'):
                ttk.Radiobutton(dialog, text=mode.upper(), value=mode, variable=selected,
                                state='normal' if mode in modes else 'disabled').pack(anchor='w',padx=18,pady=5)
            def apply():
                mode = selected.get()
                dialog.destroy()
                args = [mode]
                if mode == 'asic':
                    host = simpledialog.askstring(tr('ASIC listener'),tr('Local/LAN listening IP'),initialvalue='0.0.0.0',parent=self.root)
                    if host is None:return
                    port = simpledialog.askinteger(tr('ASIC listener'),tr('Port'),initialvalue=3333,minvalue=1024,maxvalue=65535,parent=self.root)
                    if port is None:return
                    password = simpledialog.askstring(tr('ASIC connection'),tr('Connection password (16+ characters)'),show='*',parent=self.root)
                    if password is None:return
                    args += [host,port,password]
                self._run_action(self.service.configure_mining_hardware, *args,
                                 message=tr('Mining device settings saved.'))
            controls = ttk.Frame(dialog)
            controls.pack(padx=18,pady=15)
            _button(controls,text=tr('Apply'),command=apply).pack(side='left',padx=5)
            _button(controls,text=tr('Cancel'),command=dialog.destroy).pack(side='left',padx=5)
            dialog.bind('<Escape>',lambda event: dialog.destroy())
            _label(dialog,text=tr('ASIC: stratum+tcp://this-node:3333 · worker sumuww · your connection password'),wraplength=440).pack(padx=18,pady=8)
            dialog.update_idletasks()
            width, height = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
            x = max(0, min(self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2,
                           dialog.winfo_screenwidth() - width))
            y = max(0, min(self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2,
                           dialog.winfo_screenheight() - height))
            dialog.geometry(f'+{x}+{y}')
            dialog.focus_set()
            dialog.after_idle(dialog.focus_set)
            self.root.wait_window(dialog)
        self._dialog_action(action)

    def _can_act(self):
        return self._started and (not (self._closing or self._busy or self._dialog_open or self._mining or self._mine_inflight))

    def _password(self, *, creating=False):
        dialog = _PasswordDialog(self.root, creating=creating)
        password = dialog.result
        dialog.result = None
        return password

    def _choose_file(self, *, save=False, initialfile='wallet.json'):
        options = dict(parent=self.root, initialdir=str(self.directory), filetypes=((tr('Encrypted wallet'), '*.json'), (tr('All files'), '*.*')))
        if save:
            options.update(title=tr('New wallet file location'), initialfile=initialfile, defaultextension='.json', confirmoverwrite=False)
            path = filedialog.asksaveasfilename(**options)
        else:
            options.update(title=tr('Select an encrypted wallet file'))
            path = filedialog.askopenfilename(**options)
        return Path(path) if path else None

    def _dialog_action(self, function):
        if not self._can_act():
            return
        self._dialog_open = True
        self._sync_controls()
        try:
            function()
        finally:
            self._dialog_open = False
            self._sync_controls()

    def _run_action(self, method, *args, message, callback=None):
        if self._busy or self._closing:
            return
        self._busy = True
        self._sync_controls()
        self._message(tr('Working…'))

        def done(result):
            self._busy = False
            if self._closing:
                return
            if isinstance(result, dict) and all((name in result for name in ('address', 'path', 'unlocked'))):
                current = self._wallet if self._wallet and self._wallet.get('address') == result.get('address') and (self._wallet.get('path') == result.get('path')) else {}
                wallet = dict(current)
                wallet.update(result)
                self._wallet_epoch += 1
                self._apply_status({'node': self._node_snapshot, 'wallet': wallet})
            if isinstance(result, dict):
                connection = result.get('connection')
                if connection is None and all((name in result for name in ('listen', 'peers', 'allow_internet', 'allow_lan'))):
                    connection = result
                if isinstance(connection, dict):
                    self._wallet_epoch += 1
                    self._set_connection(connection)
            if callback is not None:
                callback(result)
            self._message(message)
            self._sync_controls()
            self._request_status()

        def failed(error):
            self._busy = False
            if self._closing:
                return
            self._message(_error_message(error), error=True)
            self._sync_controls()
            messagebox.showerror(tr('Check operation'), _error_message(error), parent=self.root)
        try:
            future = method(*args)
        except Exception as error:
            failed(error)
        else:
            self._watch(future, done, failed)

    def _create_wallet(self):
        if self._wallet and self._wallet.get('unlocked'):
            return

        def action():
            path = self._choose_file(save=True)
            if path is None:
                return
            password = self._password(creating=True)
            if password is None:
                return
            self._run_action(self.service.create_wallet, path, password, message=tr('New wallet created. Keep your backup and password safe.'))
            password = None
        self._dialog_action(action)

    def _open_wallet(self):
        if self._wallet and self._wallet.get('unlocked'):
            return

        def action():
            path = self._choose_file()
            if path is None:
                return
            password = self._password()
            if password is None:
                return
            self._run_action(self.service.open_wallet, path, password, message=tr('Wallet opened.'))
            password = None
        self._dialog_action(action)

    def _display_recovery_phrase(self, phrase):
        self._dialog_open = True
        self._sync_controls()
        try:
            dialog = _RecoveryPhraseDialog(self.root, phrase=phrase)
            dialog.result = None
        finally:
            phrase = None
            self._dialog_open = False
            self._sync_controls()

    def _create_seed_wallet(self):
        if self._wallet and self._wallet.get('unlocked'):
            return
        def action():
            path = self._choose_file(save=True, initialfile='wallet.seed.json')
            if path is None:
                return
            password = self._password(creating=True)
            if password is None:
                return
            def created(result):
                self._run_action(self.service.recovery_phrase, password,
                                 message=tr('Seed wallet created. Keep your recovery words private.'),
                                 callback=self._display_recovery_phrase)
            self._run_action(self.service.create_seed_wallet, path, password,
                             message=tr('Seed wallet created. Keep your recovery words private.'), callback=created)
        self._dialog_action(action)

    def _show_seed_wallet(self):
        def action():
            password = self._password()
            if password is None:
                return
            self._run_action(self.service.recovery_phrase, password,
                             message=tr('Recovery phrase closed.'), callback=self._display_recovery_phrase)
            password = None
        self._dialog_action(action)

    def _recover_seed_wallet(self):
        if self._wallet and self._wallet.get('unlocked'):
            return
        def action():
            dialog = _RecoveryPhraseDialog(self.root)
            phrase, dialog.result = dialog.result, None
            if phrase is None:
                return
            path = self._choose_file(save=True, initialfile='wallet.recovered.json')
            if path is None:
                return
            password = self._password(creating=True)
            if password is None:
                return
            self._run_action(self.service.recover_seed_wallet, path, password, phrase,
                             message=tr('Seed wallet recovered. Your existing address is preserved.'))
            phrase = password = None
        self._dialog_action(action)

    def _lock_wallet(self):
        if self._can_act() and self._wallet and self._wallet.get('unlocked'):
            self._run_action(self.service.lock_wallet, message=tr('Wallet locked. Open it again to send funds.'))

    def _backup_wallet(self):
        if not self._wallet:
            return

        def action():
            path = self._choose_file(save=True, initialfile='wallet.backup.json')
            if path is None:
                return
            password = self._password()
            if password is None:
                return
            self._run_action(self.service.backup_wallet, path, password, message=tr('Encrypted wallet backed up. Restore requires both this file and the password.'))
            password = None
        self._dialog_action(action)

    def _restore_wallet(self):
        if self._wallet and self._wallet.get('unlocked'):
            return

        def action():
            source = self._choose_file()
            if source is None:
                return
            destination = self._choose_file(save=True, initialfile='wallet.restored.json')
            if destination is None:
                return
            password = self._password()
            if password is None:
                return
            self._run_action(self.service.restore_wallet, source, destination, password, message=tr('Backup restored. You can use the balance at your existing address.'))
            password = None
        self._dialog_action(action)

    def _copy_address(self):
        address = self.address_text.get()
        if address and (not self._closing):
            self.root.clipboard_clear()
            self.root.clipboard_append(address)
            self._message(tr('Receive address copied.'))

    def _send(self):
        if not self._can_act() or not self._wallet or (not self._wallet.get('unlocked')):
            return
        address = self.send_address.get().strip()
        amount = self.send_amount.get().strip()
        fee = self.send_fee.get().strip() if self.manual_fee.get() else None
        try:
            from .address import decode_address
            from .primitives import parse_amount
            decode_address(address, network=getattr(self.service, 'network', self.network_name))
            if parse_amount(amount) <= 0:
                raise ValueError('Payment amount must be positive')
            if fee is not None:
                parse_amount(fee)
        except (ValueError, TypeError) as error:
            messagebox.showerror(tr('Confirm transfer'), _error_message(error), parent=self.root)
            return
        self._busy = True
        self._sync_controls()
        self._message(tr('Calculating fee and total debit…'))

        def failed(error):
            self._busy = False
            if self._closing:
                return
            self._message(_error_message(error), error=True)
            self._sync_controls()
            messagebox.showerror(tr('Confirm transfer'), _error_message(error), parent=self.root)

        def submitted(result):
            self._busy = False
            if self._closing:
                return
            self.send_address.set('')
            self.send_amount.set('')
            self._message(tr('Transfer submitted. The confirmed balance updates after inclusion in a block.'))
            self._sync_controls()
            self._request_status()

        def prepared(quote):
            if self._closing:
                self._busy = False
                return
            # The confirmation displays the exact signed transaction's amounts.
            self.send_fee.set(quote['fee_smw'])
            self._dialog_open = True
            self._sync_controls()
            confirmation = tr('Send this transaction?\n\nRecipient address\n{0}\n\nAmount: {1} SMW\nFee: {2} SMW\nTotal debit: {3} SMW',
                              address, quote['amount_smw'], quote['fee_smw'], quote['total_smw'])
            if quote.get('capped'):
                confirmation += '\n\n' + tr('The automatic fee cap was applied. Confirmation time is not guaranteed.')
            try:
                accepted = messagebox.askyesno(tr('Confirm transfer'), confirmation, parent=self.root)
            finally:
                self._dialog_open = False
            if not accepted:
                self._busy = False
                self._message(tr('Payment cancelled.'))
                self._sync_controls()
                return
            try:
                future = self.service.submit_payment(quote['quote_id'])
            except Exception as error:
                failed(error)
            else:
                self._watch(future, submitted, failed)

        try:
            future = self.service.prepare_payment(address, amount, fee)
        except Exception as error:
            failed(error)
        else:
            self._watch(future, prepared, failed)

    def _add_peer(self):
        if self._can_act():
            endpoint = self.peer_endpoint.get().strip()
            if not endpoint:
                self._message(tr('Enter the peer IP:port.'), error=True)
                return
            self._run_action(self.service.add_peer, endpoint, message=tr('Peer added. Check its connection status in the node information above.'), callback=lambda result: self.peer_endpoint.set(''))

    def _set_connection(self, connection):
        self._connection_snapshot = {'listen': str(connection.get('listen') or '127.0.0.1:0'), 'peers': list(connection.get('peers') or []), 'allow_internet': bool(connection.get('allow_internet')), 'allow_lan': bool(connection.get('allow_lan')), 'public_contact': str(connection.get('public_contact') or ''), 'auto_address': bool(connection.get('auto_address')), 'own_addresses': list(connection.get('own_addresses') or []), 'self_address': dict(connection.get('self_address') or {})}
        self._connection_snapshot['privacy'] = dict(connection.get('privacy') or {})

    def _configure_network(self):

        def action():
            connection = self._connection_snapshot or {'listen': getattr(self.service, 'listen', None) or '127.0.0.1:0', 'peers': [], 'allow_internet': bool(getattr(self.service, 'allow_internet', False)), 'allow_lan': bool(getattr(self.service, 'allow_lan', False))}
            dialog = _ConnectionDialog(self.root, connection)
            options = dialog.result
            if options is None:
                return
            self._run_action(lambda: self.service.configure_network(options['listen'], options['peers'], allow_internet=options['allow_internet'], allow_lan=options['allow_lan'], advertise=options['advertise'], auto_address=options['auto_address']), message=tr('Connection settings saved and connections restarted. Check the actual connection count.'))
        self._dialog_action(action)

    def _configure_privacy(self):
        def action():
            options = (self._connection_snapshot or {}).get('privacy', {})
            dialog = _PrivacyDialog(self.root, options)
            if dialog.result is not None:
                from .privacy_ui import load_hidden
                selected = dialog.result['mode']
                if not load_hidden().get(selected, False):
                    if not _PrivacyHelpDialog(self.root, selected).result:
                        return
                self._run_action(lambda: self.service.configure_privacy(**dialog.result))
        self._dialog_action(action)

    def _rpc_can_act(self):
        return self._started and not (self._closing or self._busy or self._dialog_open)

    def _set_rpc(self, settings):
        self._rpc_snapshot = dict(settings)
        if settings.get('error'):
            self.rpc_text.set(tr('RPC/API startup failed · Check settings'))
        elif settings.get('enabled'):
            self.rpc_text.set(tr('RPC/API active · Port {0}', settings.get('active_port') or '—'))
        else:
            self.rpc_text.set(tr('RPC/API off'))

    def _configure_rpc(self):
        if not self._rpc_can_act():
            return
        self._dialog_open = True
        self._sync_controls()
        try:
            settings = self._rpc_snapshot or {'enabled': False, 'port': 18443,
                                             'token_file': str(self.directory / 'rpc-token')}
            dialog = _RpcDialog(self.root, settings)
            if dialog.result is not None:
                options = dialog.result
                self._run_action(self.service.configure_rpc, options['enabled'], options['port'],
                                 message=tr('RPC/API settings saved.'),
                                 callback=lambda result: self._set_rpc(result['rpc']))
        finally:
            self._dialog_open = False
            self._sync_controls()

    def _start_mining(self):
        if not self._can_act() or not self._wallet:
            return
        if not self._mining_allowed():
            self._message(tr('You can start SMW mining after synchronizing with connected nodes.'), error=True)
            return
        try:
            count_text = self.mine_count.get().strip()
            if not count_text.isascii() or not count_text.isdigit():
                raise ValueError
            count = int(count_text)
            if not 1 <= count <= 10000:
                raise ValueError
        except ValueError:
            self._message(tr('Enter 1–10,000 blocks to mine.'), error=True)
            return
        self._mining = True
        self._mining_waiting = False
        self._mine_target = count
        self._mine_completed = 0
        self._mine_network_wait_total = 0.0
        self.mine_progress.configure(maximum=count, value=0)
        self._sync_controls()
        self._mine_next()

    def _mine_next(self):
        if not self._mining or self._closing or self._mine_inflight:
            return
        if not self._mining_allowed():
            self._wait_for_mining_sync()
            self._request_status()
            return
        self._mining_waiting = False
        self._mine_inflight = True
        self.mine_text.set(tr('Mining · {0}/{1} blocks completed', self._mine_completed, self._mine_target))
        self._message(tr('Computing proof of work. Use Stop to cancel the current search.'))
        try:
            future = self.service.mine_one()
        except Exception as error:
            self._mine_failed(error)
            return
        self._watch(future, self._mine_done, self._mine_failed)

    def _mine_done(self, result):
        self._mine_inflight = False
        if self._closing:
            return
        cancelled = isinstance(result, dict) and bool(result.get('cancelled'))
        if not cancelled and (not isinstance(result, dict) or not result.get('block_hash')):
            self._mine_failed(RuntimeError('Mining ended without an accepted block'))
            return
        if cancelled:
            self._mining = False
            self._mining_waiting = False
        else:
            self._mine_network_wait_total = getattr(self, '_mine_network_wait_total', 0.0) + result.get('network_wait_seconds', 0.0)
            self._mine_completed += 1
            self.mine_progress.configure(value=self._mine_completed)
        if self._mining and self._mine_completed < self._mine_target:
            self.mine_text.set(tr('Mining · {0}/{1} blocks completed', self._mine_completed, self._mine_target))
            self.root.after(10, self._mine_next)
        else:
            completed = self._mine_completed >= self._mine_target
            self._mining = False
            self._mining_waiting = False
            self.mine_text.set(tr('{0} · {1}/{2} blocks', tr('Complete') if completed else tr('Stopped'), self._mine_completed, self._mine_target))
            self._message(tr('Mining {0} · Created {1} blocks.', tr('Complete') if completed else tr('Stop'), self._mine_completed))
        self._sync_controls()
        self._request_status()

    def _mine_failed(self, error):
        self._mine_inflight = False
        # The initial backend guard can race a successful block's callback.
        # Preserve this already-requested batch while no new worker is running.
        if self._mining and not self._closing and 'connect and synchronize' in str(error).lower():
            self._wait_for_mining_sync()
            self._sync_controls()
            self._request_status()
            return
        self._mining = False
        self._mining_waiting = False
        if self._closing:
            return
        cancelled = 'cancel' in str(error).lower()
        self.mine_text.set(tr('{0} · {1}/{2} blocks', tr('Stopped') if cancelled else tr('Paused'), self._mine_completed, self._mine_target))
        self._message(_error_message(error), error=not cancelled)
        self._sync_controls()
        self._request_status()
        if not cancelled:
            messagebox.showerror(tr('Check mining'), _error_message(error), parent=self.root)

    def _wait_for_mining_sync(self):
        self._mining_waiting = True
        if self._node_snapshot.get('listener_active') is False:
            self.mine_text.set(tr('Mining waiting for node recovery · {0}/{1} blocks completed', self._mine_completed, self._mine_target))
        elif not self._node_snapshot.get('peers', 0):
            dht = self._node_snapshot.get('dht_discovery') or {}
            remaining = dht.get('next_query_seconds')
            if dht.get('state') == 'active':
                if not dht.get('round_in_progress') and type(remaining) is int and remaining > 0:
                    self.mine_text.set(tr('Mining waiting for nodes · {0}/{1} blocks completed · Next search in {2}s', self._mine_completed, self._mine_target, remaining))
                else:
                    self.mine_text.set(tr('Mining waiting for nodes · {0}/{1} blocks completed · Searching…', self._mine_completed, self._mine_target))
            else:
                self.mine_text.set(tr('Mining waiting for nodes · {0}/{1} blocks completed', self._mine_completed, self._mine_target))
        else:
            self.mine_text.set(tr('Mining waiting for block synchronization · {0}/{1} blocks completed', self._mine_completed, self._mine_target))
        self._message(tr('Waiting for connected nodes and synchronization. Your mining target is kept and resumes automatically.'))

    def _stop_mining(self):
        if not self._mining and (not self._mine_inflight):
            return
        self._mining = False
        self._mining_waiting = False
        self._message(tr('Stop requested. Cancelling the current mining search.'))
        try:
            future = self.service.cancel_mining()
        except Exception:
            self._message(tr('No more blocks will be mined. Wait for the current search to finish.'))
        else:
            self._watch(future, None, None)
        self._sync_controls()

    def _close(self):
        if self._closing:
            return
        if self._history_dialog is not None:
            self._history_dialog.close()
        if self._update_dialog is not None:
            self._update_dialog.destroy()
        self._closing = True
        self._mining = False
        self._mining_waiting = False
        self._message(tr('Stopping the node and finishing storage operations…'))
        self._sync_controls()
        try:
            cancellation = self.service.cancel_mining()
        except Exception:
            pass
        else:
            self._watch(cancellation, None, None)
        if self._stop_requested:
            return
        self._stop_requested = True
        try:
            future = self.service.stop()
        except Exception as error:
            self._finish_close(error)
        else:
            self._watch(future, lambda result: self._finish_close(), self._finish_close)

    def _finish_close(self, error=None):
        if self._destroyed:
            return
        if error is not None:
            messagebox.showerror(tr('Check shutdown'), tr('A problem occurred while stopping the node.\n') + _error_message(error), parent=self.root)
        self._destroyed = True
        try:
            timers = self.root.tk.splitlist(self.root.tk.call('after', 'info'))
            for timer in timers:
                try:
                    self.root.after_cancel(timer)
                except tk.TclError:
                    pass
        except tk.TclError:
            pass
        # Drain Tk's own theme idle work while its widgets still exist.
        # This does not run timers or process new user input during shutdown.
        self.root.update_idletasks()
        self.root.destroy()

class _FailedStartupService:
    """Keep the window closable when constructing the real service fails."""

    def __init__(self, directory, network, error):
        self.directory = directory
        self.network = network
        self.error = error

    def start(self):
        future = Future()
        future.set_exception(self.error)
        return future

    def cancel_mining(self):
        future = Future()
        future.set_result(None)
        return future
    stop = cancel_mining

def main(argv=None):
    from .app_service import AppService
    from .network_settings import default_directory
    from .profiles import NETWORK_NAMES
    set_translator(Translator(load_language()))
    parser = argparse.ArgumentParser(description=tr('SMW private-key wallet, transfers, and mining'))
    parser.add_argument('--directory', type=Path, default=None, help=tr('Wallet node data folder; omitted uses the existing SMW data location'))
    parser.add_argument('--network', choices=NETWORK_NAMES, default='dora', help=tr('Development network; select regtest explicitly for quick tests'))
    parser.add_argument('--listen', default=None, help=tr('Listening IPv4:port; omitted uses saved settings'))
    parser.add_argument('--advertise', default=None, help=tr('Public IPv4:port to advertise; requires internet permission and a non-loopback listener'))
    parser.add_argument('--allow-lan', action='store_true', default=None, help=tr('Allow manual RFC1918 LAN connections'))
    parser.add_argument('--allow-internet', action='store_true', default=None, help=tr('Allow internet IP·domain peer connections'))
    parser.add_argument('--peer', action='append', default=None, help=tr('Peer IP·domain:port; can be specified more than once'))
    options = parser.parse_args(argv)
    if options.network == 'sumuww':
        options.network = 'dora'
    root = tk.Tk()
    try:
        directory = options.directory if options.directory is not None else default_directory()
        service = AppService(directory, network=options.network, listen=options.listen, allow_lan=options.allow_lan, allow_internet=options.allow_internet, peers=options.peer, bootstrap=options.network == 'dora', advertise=options.advertise)
    except Exception as error:
        service = _FailedStartupService(options.directory or Path.cwd(), options.network, error)
    SumuwwApp(root, service)
    root.mainloop()
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
