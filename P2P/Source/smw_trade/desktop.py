from . import __version__
"""Native Tk/ttk desktop, direct model calls, no browser or HTTP listener."""
import json
from decimal import Decimal
from queue import Queue, Empty
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from .vertical_text import VerticalLabel, VerticalButton, VerticalTreeview, render_vertical_ppm
BG = '#0b1222'
PANEL = '#142038'
EDGE = '#263754'
INK = '#edf2ff'
MUTED = '#a6b6d2'
BLUE = '#456ff0'
PHASES = {'STARTING': 'Starting test nodes', 'AGREED': 'Swap terms agreed', 'SMW_LOCK_CONFIRMED': 'SMW lock confirmed', 'BOTH_LOCKS_CONFIRMED': 'Both locks confirmed', 'BTC_CLAIM_CONFIRMED': 'BTC claim confirmed', 'COMPLETED': 'Swap completed', 'REFUND_WAIT': 'Checking refund height', 'REFUNDED': 'Both refunds completed'}
PHASES.update({'RESERVED': 'Reserved', 'FINALIZING': 'Saving trade result', 'FAILED': 'Failed', 'INTERRUPTED': 'Interrupted · records retained'})
STATUS = {'active': 'Available', 'reserved': 'Reserved', 'canceled': 'Canceled', 'expired': 'Expired'}

class Desktop:

    def __init__(self, app, *, window=None):
        self.app = app
        from .localization import Localizer
        self.localization = Localizer(app.store.directory)
        self.tr = self.localization.text
        self.root = window or tk.Tk()
        self.queue = Queue()
        self.busy = False
        self.closing = False
        self.workers = []
        self.root.title('SUMUWW P2P '+__version__)
        self.root.geometry(f'1140x{min(900, self.root.winfo_screenheight() - 100)}')
        self.root.minsize(980, 700)
        self.root.configure(bg=BG)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.side = tk.StringVar(value=self.tr('Sell SMW'))
        self.smw = tk.StringVar()
        self.btc = tk.StringVar()
        self.port = tk.StringVar()
        self.peer_host = tk.StringVar(value='127.0.0.1')
        self.message = tk.StringVar(value=self.tr('Public-money deposits and swaps are disabled.'))
        self.peers = tk.StringVar(value='0')
        self.count = tk.StringVar(value='0')
        self.job = tk.StringVar(value=self.tr('Not started.'))
        self._style()
        self._layout()
        self.latest = None
        self.order_map = {}
        self.trade_map = {}
        self._paint()
        self.timer = self.root.after(250, self.poll)

    def change_language(self, event=None):
        if self.busy or self.closing or (self.latest and self.latest['job'].get('running')):
            self.language_choice.set(self.localization.languages[self.localization.code])
            return
        code = next(k for k, v in self.localization.languages.items() if v == self.language_choice.get())
        old_side = 'sell' if self.side.get() == self.tr('Sell SMW') else 'buy'
        snapshot = {}
        for name in ('smw', 'btc', 'port', 'peer_host', 'listen_host', 'listen_port', 'peer_session', 'wallet_password', 'wallet_confirm', 'link_vars', 'swap_vars'):
            variable = getattr(self, name)
            snapshot[name] = {k: v.get() for k, v in variable.items()} if isinstance(variable, dict) else variable.get()
        selected_tab = self.tabs.index(self.tabs.select())
        self.localization.set(code)
        self.outer.destroy()
        self._layout()
        self.side.set(self.tr('Sell SMW' if old_side == 'sell' else 'Buy SMW'))
        for name, value in snapshot.items():
            variable = getattr(self, name)
            if isinstance(variable, dict):
                for key, text in value.items(): variable[key].set(text)
            else: variable.set(value)
        self.message.set(self.tr('Public-money deposits and swaps are disabled.'))
        self.tabs.select(selected_tab)
        self._paint()

    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use('clam')
        s.configure('.', font=('Segoe UI', 10), background=PANEL, foreground=INK, bordercolor=EDGE)
        s.configure('TFrame', background=BG)
        s.configure('Card.TFrame', background=PANEL)
        s.configure('TLabel', background=BG)
        s.configure('Card.TLabel', background=PANEL)
        s.configure('Muted.TLabel', foreground=MUTED)
        s.configure('Title.TLabel', font=('Segoe UI', 21, 'bold'))
        s.configure('Head.TLabel', font=('Segoe UI', 14, 'bold'))
        s.configure('TButton', padding=(14, 9), background='#263b5d', foreground=INK, borderwidth=0)
        s.map('TButton', background=[('active', '#354f78'), ('disabled', '#202d43')])
        s.configure('Primary.TButton', background=BLUE, font=('Segoe UI', 10, 'bold'))
        s.map('Primary.TButton', background=[('active', '#5b80fb')])
        s.configure('TEntry', fieldbackground='#0d182b', foreground=INK, insertcolor=INK, padding=8)
        s.configure('TCombobox', fieldbackground='#0d182b', foreground=INK, arrowsize=15, padding=7)
        s.map('TCombobox', fieldbackground=[('readonly', '#0d182b')], foreground=[('readonly', INK)])
        s.configure('TNotebook', background=BG, borderwidth=0)
        s.configure('TNotebook.Tab', background=PANEL, padding=(12, 10), foreground=MUTED)
        s.map('TNotebook.Tab', background=[('selected', '#25416b')], foreground=[('selected', INK)])
        s.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=INK, rowheight=39, borderwidth=0)
        s.configure('Treeview.Heading', background='#203251', foreground=MUTED, padding=9)
        s.map('Treeview', background=[('selected', '#315287')], foreground=[('selected', '#ffffff')])

    def label(self, parent, text, **kwargs):
        maximum = int(kwargs.setdefault('wraplength', 500))
        widget = VerticalLabel(parent, text=text, **kwargs)
        widget._vertical_max_width = maximum
        widget.refresh_vertical()
        def resize(event):
            if event.widget == parent and widget.winfo_exists() and event.width > 60:
                width = max(60, min(maximum, event.width - 40))
                if int(float(widget.cget('wraplength'))) != width:
                    widget.configure(wraplength=width)
                    widget._vertical_max_width = width
                    widget.refresh_vertical()
        parent.bind('<Configure>', resize, add='+')
        return widget

    def flow_actions(self, parent):
        """Wrap action rows without changing commands or translated captions."""
        children = parent.winfo_children()
        if len(children) > 1 and all(isinstance(w, VerticalButton) for w in children):
            for widget in children:
                widget.pack_forget()
            def arrange(event=None):
                available = max(100, parent.winfo_width())
                cell = max(widget.winfo_reqwidth() + 8 for widget in children)
                columns = max(1, min(len(children), available // cell))
                for index, widget in enumerate(children):
                    widget.grid(row=index // columns, column=index % columns, sticky='w', padx=(0, 8), pady=4)
            parent.bind('<Configure>', arrange, add='+')
            arrange()
        for child in children:
            if isinstance(child, ttk.Frame):
                self.flow_actions(child)

    def _layout(self):
        outer = ttk.Frame(self.root, padding=24)
        self.outer = outer
        outer.pack(fill='both', expand=True)
        top = ttk.Frame(outer)
        top.pack(fill='x')
        self.language_choice = tk.StringVar(value=self.localization.languages[self.localization.code])
        self.language_select = ttk.Combobox(top, textvariable=self.language_choice, values=list(self.localization.languages.values()), state='readonly', width=22)
        self.language_select.pack(side='right', padx=(12, 0))
        self.language_select.bind('<<ComboboxSelected>>', self.change_language)
        self.label(top, 'SUMUWW  P2P', style='Title.TLabel').pack(side='left')
        self.label(outer, self.tr('0.1.6 · HTLC activation 9100 · Public swaps disabled').replace('0.1.6', __version__, 1), style='Muted.TLabel', wraplength=1050).pack(anchor='w', pady=(6, 0))
        self.label(outer, self.tr('Share SMW orders at a price you choose.'), style='Muted.TLabel').pack(anchor='w', pady=(6, 18))
        banner = ttk.Frame(outer, style='Card.TFrame', padding=12)
        banner.pack(fill='x', pady=(0, 16))
        self.label(banner, self.tr('Connect existing wallets for address and balance queries. Swap execution requires compatible test nodes.'), style='Card.TLabel').pack(anchor='w')
        metrics = ttk.Frame(outer)
        metrics.pack(fill='x', pady=(0, 15))
        for col, (title, value) in enumerate(((self.tr('Trading pair'), 'SMW / BTC'), (self.tr('Operator fee'), '0%'), (self.tr('Connected test peers'), self.peers), (self.tr('Active orders'), self.count))):
            metrics.columnconfigure(col, weight=1, uniform='metric')
            f = ttk.Frame(metrics, style='Card.TFrame', padding=13)
            f.grid(row=0, column=col, sticky='nsew', padx=(0, 8 if col < 3 else 0))
            self.label(f, title, style='Card.TLabel', foreground=MUTED, wraplength=185).pack(anchor='w')
            label = VerticalLabel(f, style='Card.TLabel', font=('Segoe UI', 17, 'bold'))
            label.configure(textvariable=value) if isinstance(value, tk.Variable) else label.configure(text=value)
            label.pack(anchor='w', pady=(4, 0))
        self.label(outer, '', textvariable=self.message, style='Muted.TLabel', wraplength=1070).pack(side='bottom', fill='x', pady=(12, 0))
        self.tab_images = []
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill='both', expand=True)
        market = ttk.Frame(self.tabs, padding=(0, 15))
        wallets = ttk.Frame(self.tabs, padding=(0, 15))
        network = ttk.Frame(self.tabs, padding=(0, 15))
        self.add_tab(market, 'Market')
        self.add_tab(wallets, 'Test vault')
        self.add_tab(network, 'Connections & tests')
        trades = ttk.Frame(self.tabs, padding=(0, 15))
        self.add_tab(trades, 'Trade history')
        links = ttk.Frame(self.tabs, padding=(0, 15))
        self.add_tab(links, 'Wallet queries')
        independent = ttk.Frame(self.tabs, padding=(0, 15))
        self.add_tab(independent, 'Two-party test swap')
        self.page_canvases = []
        market = self.scroll_page(market)
        wallet_body = self.scroll_page(wallets)
        network = self.scroll_page(network)
        trades = self.scroll_page(trades)
        links = self.scroll_page(links)
        independent = self.scroll_page(independent)
        self.root.bind('<MouseWheel>', lambda event: self.page_canvases[self.tabs.index(self.tabs.select())].yview_scroll(-int(event.delta / 120), 'units'))
        self._market(market)
        self._wallets(wallet_body)
        self._network(network)
        self._trades(trades)
        self._wallet_links(links)
        self._independent(independent)
        for page in (market, wallet_body, network, trades, links, independent):
            self.flow_actions(page)

    def add_tab(self, page, source):
        text = self.tr(source)
        if self.localization.code == 'mn-Mong':
            ppm, _, _ = render_vertical_ppm(text, 16, (237, 242, 255), (20, 32, 56), 80)
            image = tk.PhotoImage(master=self.root, data=ppm, format='PPM')
            self.tab_images.append(image)
            self.tabs.add(page, text=text, image=image, compound='none')
        else:
            # Short wrapped captions retain all six tabs on a normal laptop window.
            import textwrap
            shown = '\n'.join(textwrap.wrap(text, width=18, break_long_words=False))
            self.tabs.add(page, text=shown)

    def scroll_page(self, page):
        canvas = tk.Canvas(page, bg=BG, highlightthickness=0, bd=0)
        horizontal = ttk.Scrollbar(page, orient='horizontal', command=canvas.xview)
        horizontal.pack(side='bottom', fill='x')
        scrollbar = ttk.Scrollbar(page, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
        content = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=content, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        content.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        # Wide forms remain reachable even with unusually long translations.
        def resize(event):
            canvas.itemconfigure(window, width=max(event.width, content.winfo_reqwidth()))
        canvas.bind('<Configure>', resize)
        self.page_canvases.append(canvas)
        return content

    def _wallet_links(self, page):
        self.label(page, self.tr('Query existing SMW and BTC wallet addresses'), style='Head.TLabel').pack(anchor='w')
        self.label(page, self.tr('Enter the authentication file and receiving address for your running local node. Private keys and recovery words are not imported.\nThis view only queries address balances; it does not send coins, unlock wallets or execute public swaps.'), style='Muted.TLabel', wraplength=1050).pack(anchor='w', pady=8)
        self.link_vars = {'coin': tk.StringVar(value='smw'), 'url': tk.StringVar(value='http://127.0.0.1:18443/rpc'), 'credential_file': tk.StringVar(), 'address': tk.StringVar()}
        form = ttk.Frame(page)
        form.pack(fill='x', pady=5)
        for row, (key, title) in enumerate((('coin', self.tr('Coin')), ('url', self.tr('Local RPC URL')), ('credential_file', self.tr('SMW token / BTC .cookie file')), ('address', self.tr('Existing wallet receiving address')))):
            self.label(form, title).grid(row=row, column=0, sticky='w', pady=4)
            if key == 'coin':
                widget = ttk.Combobox(form, textvariable=self.link_vars[key], values=('smw', 'btc'), state='readonly')
            else:
                widget = ttk.Entry(form, textvariable=self.link_vars[key])
            widget.grid(row=row, column=1, sticky='ew', padx=12, pady=4)
        form.columnconfigure(1, weight=1)
        VerticalButton(form, text=self.tr('Select file'), command=lambda: self.pick_credential(self.link_vars['credential_file'])).grid(row=2, column=2)
        actions = ttk.Frame(page)
        actions.pack(fill='x', pady=8)
        self.link_button = VerticalButton(actions, text=self.tr('Connect and query balance'), command=lambda: self.submit('wallet_link', {k: v.get() for k, v in self.link_vars.items()}, self.tr('Address balance queried from the local node.')))
        self.link_button.pack(side='left')
        self.link_refresh = VerticalButton(actions, text=self.tr('Refresh configured address'), command=lambda: self.submit('wallet_refresh', {'coin': self.link_vars['coin'].get()}, self.tr('Address balance refreshed.')))
        self.link_refresh.pack(side='left', padx=8)
        self.link_result = tk.Text(page, height=9, bg=PANEL, fg=INK, font=('Consolas', 10), wrap='word', state='disabled')
        self.link_result.pack(fill='both', expand=True, pady=6)

    def pick_credential(self, variable):
        path = filedialog.askopenfilename(parent=self.root, title=self.tr('Select local node authentication file'))
        if path:
            variable.set(path)

    def _independent(self, page):
        self.label(page, self.tr('Two-party test swap using separately held keys'), style='Head.TLabel').pack(anchor='w')
        self.label(page, self.tr('Open your own test vault and connect your local regtest nodes on each device.\nPublic-money swaps are disabled. Peer reports do not replace actual chain confirmation.'), style='Muted.TLabel', wraplength=1050).pack(anchor='w', pady=6)
        self.swap_vars = {k: tk.StringVar() for k in ('smw_url', 'smw_token', 'btc_url', 'btc_cookie')}
        form = ttk.Frame(page)
        form.pack(fill='x')
        for row, (key, title) in enumerate((('smw_url', self.tr('SMW test HTLC RPC URL')), ('smw_token', self.tr('SMW test token file')), ('btc_url', 'Bitcoin Core regtest RPC URL'), ('btc_cookie', self.tr('Bitcoin regtest .cookie file')))):
            self.label(form, title).grid(row=row, column=0, sticky='w', pady=3)
            ttk.Entry(form, textvariable=self.swap_vars[key]).grid(row=row, column=1, sticky='ew', padx=12, pady=3)
            if key in ('smw_token', 'btc_cookie'):
                VerticalButton(form, text=self.tr('Select file'), command=lambda k=key: self.pick_credential(self.swap_vars[k])).grid(row=row, column=2)
        form.columnconfigure(1, weight=1)
        self.swap_configure_button = VerticalButton(page, text=self.tr('Connect both test nodes'), command=lambda: self.submit('swap_configure', {k: v.get() for k, v in self.swap_vars.items()}, self.tr('Both test chains connected.')))
        self.swap_configure_button.pack(anchor='w', pady=6)
        self.peer_session = tk.StringVar()
        self.peer_sessions = ttk.Combobox(page, textvariable=self.peer_session, state='readonly')
        self.peer_sessions.pack(fill='x', pady=6)
        actions = ttk.Frame(page)
        actions.pack(fill='x')
        self.peer_buttons = {}
        for action, title in (('prepare', self.tr('Prepare my keys')), ('sync', self.tr('Exchange terms')), ('fund', self.tr('Lock my asset')), ('claim', self.tr('Claim my asset')), ('refund', self.tr('Refund after expiry')), ('status', self.tr('Check chains'))):
            button = VerticalButton(actions, text=title, command=lambda a=action: self.peer_action(a))
            button.pack(side='left', padx=(0, 6))
            self.peer_buttons[action] = button
        self.peer_result = tk.Text(page, height=5, bg=PANEL, fg=INK, font=('Consolas', 10), wrap='word', state='disabled')
        self.peer_result.pack(fill='both', expand=True, pady=8)

    def peer_action(self, action):
        session = self.peer_session.get()
        if not session:
            self.message.set(self.tr('Select a reserved order.'))
            return
        if action in ('fund', 'claim', 'refund'):
            trade = next((t for t in self.latest['trades'] if t['session'] == session), None)
            if not trade:
                return
            if not messagebox.askyesno(self.tr('Sign two-party test transaction'), f"{trade['smw']} SMW ↔ {trade['btc']}{self.tr(' BTC\n\nBroadcast a test transaction using your local key or saved refund signature.\nNetwork fees are separate. Continue?')}", parent=self.root):
                return
        self.submit('peer_' + action, {'session': session}, self.tr('Test-swap operation processed. Review the result.'))

    def _market(self, page):
        page.columnconfigure(0, weight=3)
        page.columnconfigure(1, weight=1)
        page.rowconfigure(0, weight=1)
        left = ttk.Frame(page)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 20))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(left)
        toolbar.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        self.label(toolbar, self.tr('Order book'), style='Head.TLabel').pack(side='left')
        self.sync_button = VerticalButton(toolbar, text=self.tr('Synchronize'), command=lambda: self.submit('sync', {}, self.tr('Orders synchronized.')))
        self.sync_button.pack(side='right')
        cols = ('side', 'smw', 'btc', 'status', 'owner')
        self.orders = VerticalTreeview(left, columns=cols, show='headings', selectmode='browse', height=5)
        for col, title, width in zip(cols, (self.tr('Side'), self.tr('SMW amount'), self.tr('Total BTC amount'), self.tr('Status'), self.tr('Owner')), (60, 150, 145, 95, 70)):
            self.orders.heading(col, text=title)
            self.orders.column(col, width=width, minwidth=55, anchor='w')
        self.orders.grid(row=1, column=0, sticky='nsew')
        bar = ttk.Scrollbar(left, orient='vertical', command=self.orders.yview)
        bar.grid(row=1, column=1, sticky='ns')
        self.orders.configure(yscrollcommand=bar.set)
        self.orders.bind('<<TreeviewSelect>>', lambda _: self.selection_changed())
        actions = ttk.Frame(left)
        actions.grid(row=2, column=0, sticky='ew', pady=(12, 0))
        self.reserve_button = VerticalButton(actions, text=self.tr('Reserve selected order'), command=self.reserve, state='disabled')
        self.reserve_button.pack(side='left')
        self.cancel_button = VerticalButton(actions, text=self.tr('Cancel my order'), command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left', padx=8)
        self.label(left, self.tr('Reserving an order does not transfer assets.'), style='Muted.TLabel').grid(row=3, column=0, sticky='w', pady=(10, 0))
        right = ttk.Frame(page, style='Card.TFrame', padding=18)
        right.grid(row=0, column=1, sticky='nsew')
        self.label(right, self.tr('Create order'), style='Card.TLabel', font=('Segoe UI', 14, 'bold')).pack(anchor='w', pady=(0, 15))
        for text, var, name in ((self.tr('Order side'), self.side, 'side'), (self.tr('SMW amount'), self.smw, 'smw'), (self.tr('BTC amount for the full quantity'), self.btc, 'btc')):
            self.label(right, text, style='Card.TLabel').pack(anchor='w', pady=(9, 5))
            if name == 'side':
                widget = ttk.Combobox(right, textvariable=var, values=(self.tr('Sell SMW'), self.tr('Buy SMW')), state='readonly', width=23)
            else:
                widget = ttk.Entry(right, textvariable=var, width=25)
            widget.pack(fill='x')
            setattr(self, name + '_entry', widget)
        self.label(right, self.tr('Order validity: 1 hour.\nNetwork fees are separate from the swap amount.'), style='Card.TLabel', foreground=MUTED, wraplength=230).pack(anchor='w', pady=16)
        self.create_button = VerticalButton(right, text=self.tr('Publish test order'), style='Primary.TButton', command=self.create)
        self.create_button.pack(fill='x')

    def _wallets(self, page):
        self.label(page, self.tr('Encrypted test vault · Separate SMW and BTC keys'), style='Head.TLabel').pack(anchor='w')
        self.wallet_status = self.label(page, '', style='Muted.TLabel')
        self.wallet_status.pack(anchor='w', pady=(8, 12))
        self.label(page, self.tr('These addresses are for regtest only. Existing SMW private wallets cannot be imported and real coins cannot be deposited.'), style='Muted.TLabel', wraplength=1020).pack(anchor='w', pady=(0, 12))
        cards = ttk.Frame(page)
        cards.pack(fill='x')
        self.wallet_entries = {}
        for col, (coin, code) in enumerate((('SUMUWW · SMW', 'smw'), ('Bitcoin · BTC', 'btc'))):
            cards.columnconfigure(col, weight=1)
            f = ttk.Frame(cards, style='Card.TFrame', padding=16)
            f.grid(row=0, column=col, sticky='nsew', padx=(0, 15 if col == 0 else 0))
            self.label(f, coin, style='Card.TLabel', font=('Segoe UI', 16, 'bold')).pack(anchor='w')
            self.label(f, self.tr('Real wallet: not connected'), style='Card.TLabel', foreground='#e7c884').pack(anchor='w', pady=8)
            self.label(f, self.tr('Test receiving address · Unlock vault to display'), style='Card.TLabel', foreground=MUTED).pack(anchor='w')
            entry = ttk.Entry(f, state='readonly', width=43)
            entry.pack(fill='x', pady=(5, 0))
            self.wallet_entries[code] = entry
        passwords = ttk.Frame(page)
        passwords.pack(fill='x', pady=(15, 10))
        self.wallet_password = tk.StringVar()
        self.wallet_confirm = tk.StringVar()
        self.label(passwords, self.tr('Password (12+ characters)')).grid(row=0, column=0, sticky='w')
        self.label(passwords, self.tr('Confirm new vault password')).grid(row=0, column=1, sticky='w', padx=(15, 0))
        self.wallet_password_entry = ttk.Entry(passwords, textvariable=self.wallet_password, show='•', width=35)
        self.wallet_password_entry.grid(row=1, column=0, sticky='ew', pady=(5, 0))
        ttk.Entry(passwords, textvariable=self.wallet_confirm, show='•', width=35).grid(row=1, column=1, sticky='ew', padx=(15, 0), pady=(5, 0))
        passwords.columnconfigure(0, weight=1)
        passwords.columnconfigure(1, weight=1)
        actions = ttk.Frame(page)
        actions.pack(fill='x', pady=(0, 12))
        self.wallet_buttons = {}
        for command, title in (('create', self.tr('New test vault')), ('unlock', self.tr('Unlock vault')), ('lock', self.tr('Lock')), ('backup', self.tr('Encrypted backup')), ('restore', self.tr('Restore backup'))):
            button = VerticalButton(actions, text=title, command=lambda c=command: self.wallet_action(c))
            button.pack(side='left', padx=(0, 8))
            self.wallet_buttons[command] = button
        self.label(page, self.tr('After creating a vault, trade-history actions sign test transactions with your local keys.\nRecovery requires both the backup file and its password. Existing vaults and backups are not overwritten.\nLocking prevents new signatures; previously approved work can finish.'), style='Muted.TLabel', wraplength=1020).pack(anchor='w')
        self.label(page, self.tr('Storage — Orders, encrypted test vault and execution records'), style='Head.TLabel').pack(anchor='w', pady=(15, 8))
        self.data_path = ttk.Entry(page)
        self.data_path.insert(0, str(self.app.store.directory))
        self.data_path.configure(state='readonly')
        self.data_path.pack(fill='x')

    def wallet_action(self, action):
        password = self.wallet_password.get()
        confirmation = self.wallet_confirm.get()
        self.wallet_password.set('')
        self.wallet_confirm.set('')
        body = {}
        if action in ('create', 'unlock', 'restore'):
            body['password'] = password
        if action == 'create' and password != confirmation:
            self.message.set(self.tr('Password confirmation does not match.'))
            return
        if action in ('backup', 'restore'):
            if action == 'backup':
                path = filedialog.asksaveasfilename(parent=self.root, title=self.tr('Back up encrypted test vault'), defaultextension='.smwvault', filetypes=[('Encrypted test wallet', '*.smwvault')])
            else:
                path = filedialog.askopenfilename(parent=self.root, title=self.tr('Restore test-vault backup'), filetypes=[('Encrypted test wallet', '*.smwvault'), ('All files', '*')])
            if not path:
                return
            body['path'] = path
        messages = {'create': self.tr('Encrypted test vault created.'), 'unlock': self.tr('Test vault unlocked.'), 'lock': self.tr('Vault locked. New transactions require unlocking.'), 'backup': self.tr('Encrypted test vault backed up.'), 'restore': self.tr('Backup verified and the same test vault restored.')}
        self.submit('wallet_' + action, body, messages[action])

    def _network(self, page):
        page.columnconfigure(0, weight=1)
        page.columnconfigure(1, weight=1)
        page.rowconfigure(0, weight=1)
        left = ttk.Frame(page, style='Card.TFrame', padding=20)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 15))
        self.label(left, self.tr('Test-peer connection'), style='Card.TLabel', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        self.label(left, self.tr('Enter the peer IPv4/IPv6 address and port. Automatic Internet discovery and NAT traversal are not provided.'), style='Card.TLabel', foreground=MUTED, wraplength=430).pack(anchor='w', pady=8)
        self.label(left, self.tr('Peer IP address'), style='Card.TLabel').pack(anchor='w')
        ttk.Entry(left, textvariable=self.peer_host).pack(fill='x', pady=(3, 6))
        self.label(left, self.tr('Peer P2P port'), style='Card.TLabel').pack(anchor='w')
        self.peer_entry = ttk.Entry(left, textvariable=self.port)
        self.peer_entry.pack(fill='x', pady=(5, 10))
        self.connect_button = VerticalButton(left, text=self.tr('Connect'), command=self.connect)
        self.connect_button.pack(anchor='w')
        self.listen_host = tk.StringVar(value='127.0.0.1')
        self.listen_port = tk.StringVar(value='0')
        self.label(left, self.tr('My listening IP / port · Loopback by default'), style='Card.TLabel', foreground=MUTED).pack(anchor='w', pady=(10, 3))
        listen = ttk.Frame(left, style='Card.TFrame')
        listen.pack(fill='x')
        ttk.Entry(listen, textvariable=self.listen_host, width=18).pack(side='left')
        ttk.Entry(listen, textvariable=self.listen_port, width=7).pack(side='left', padx=6)
        self.listen_button = VerticalButton(listen, text=self.tr('Apply listener'), command=self.listen)
        self.listen_button.pack(side='left')
        self.my_port = self.label(left, '', style='Card.TLabel')
        self.my_port.pack(anchor='w', pady=(20, 8))
        self.identity = self.label(left, '', style='Card.TLabel', foreground=MUTED, wraplength=430)
        self.identity.pack(anchor='w')
        self.peer_list = tk.Listbox(left, bg='#0e192d', fg=INK, highlightthickness=0, bd=0, height=4, font=('Segoe UI', 10))
        self.peer_list.pack(fill='both', expand=True, pady=(15, 0))
        right = ttk.Frame(page, style='Card.TFrame', padding=20)
        right.grid(row=0, column=1, sticky='nsew')
        self.label(right, self.tr('Test swap and refund checks'), style='Card.TLabel', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        self.label(right, self.tr('Check 1 SMW ↔ 0.002 BTC on isolated SUMUWW and Bitcoin Core test chains.\nThis disposable-asset check is separate from order reservations.'), style='Card.TLabel', foreground=MUTED, wraplength=430).pack(anchor='w', pady=14)
        self.success_button = VerticalButton(right, text=self.tr('Test swap'), command=lambda: self.check('success'))
        self.success_button.pack(anchor='w', pady=5)
        self.refund_button = VerticalButton(right, text=self.tr('Test refund and recovery'), command=lambda: self.check('refund'))
        self.refund_button.pack(anchor='w', pady=5)
        VerticalLabel(right, textvariable=self.job, style='Card.TLabel', wraplength=430).pack(anchor='w', pady=20)
        self.evidence_button = VerticalButton(right, text=self.tr('View results'), command=self.show_evidence, state='disabled')
        self.evidence_button.pack(anchor='w')

    def _trades(self, page):
        self.label(page, self.tr('Run a test swap or refund for a reserved order'), style='Head.TLabel').pack(anchor='w')
        self.label(page, self.tr('Use the signed reservation amounts. A local encrypted test vault signs with its stored keys.\nThe other party is simulated with a disposable test wallet on this device. This is not a remote-party or public-money transaction.'), style='Muted.TLabel', wraplength=1050).pack(anchor='w', pady=(8, 12))
        frame = ttk.Frame(page)
        frame.pack(fill='both', expand=True)
        columns = ('direction', 'smw', 'btc', 'role', 'state')
        self.trade_rows = VerticalTreeview(frame, columns=columns, show='headings', selectmode='browse', height=3)
        for col, title, width in zip(columns, (self.tr('My side'), self.tr('SMW amount'), self.tr('Total BTC amount'), self.tr('Reservation role'), self.tr('My execution state')), (80, 170, 170, 130, 260)):
            self.trade_rows.heading(col, text=title)
            self.trade_rows.column(col, width=width, minwidth=70)
        self.trade_rows.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.trade_rows.yview)
        scroll.pack(side='right', fill='y')
        self.trade_rows.configure(yscrollcommand=scroll.set)
        self.trade_rows.bind('<<TreeviewSelect>>', lambda _: self.trade_selection_changed())
        actions = ttk.Frame(page)
        actions.pack(fill='x', pady=12)
        self.execute_button = VerticalButton(actions, text=self.tr('Test selected swap'), command=lambda: self.execute('success'), state='disabled')
        self.execute_button.pack(side='left')
        self.execute_refund_button = VerticalButton(actions, text=self.tr('Test selected refund'), command=lambda: self.execute('refund'), state='disabled')
        self.execute_refund_button.pack(side='left', padx=10)
        self.trade_evidence_button = VerticalButton(actions, text=self.tr('View selected records'), command=self.show_trade_evidence, state='disabled')
        self.trade_evidence_button.pack(side='left')
        self.label(page, self.tr('Received amounts match the order; fees are separate. Completed, refunded, failed and interrupted records are retained.\nExecuted reservations are not funded again. Peer completion reports do not count as chain confirmations.'), style='Muted.TLabel', wraplength=1050).pack(anchor='w')

    def selected_trade(self):
        selected = self.trade_rows.selection()
        return self.trade_map.get(selected[0]) if selected else None

    def trade_selection_changed(self):
        trade = self.selected_trade()
        running = bool(self.latest and self.latest['job'].get('running'))
        enabled = bool(trade and trade['can_execute'] and (not running) and (not self.busy) and (not self.closing))
        for button in (self.execute_button, self.execute_refund_button):
            button.configure(state='normal' if enabled else 'disabled')
        self.trade_evidence_button.configure(state='normal' if trade and trade['evidence'] and (not self.closing) else 'disabled')

    def execute(self, mode):
        trade = self.selected_trade()
        if not trade or not trade['can_execute']:
            return
        action = self.tr('swap') if mode == 'success' else self.tr('refund and recovery')
        if messagebox.askyesno(self.tr('Execute reserved test order'), f"{trade['smw']} SMW ↔ {trade['btc']}{self.tr(' BTC\n\nRun a test ')}{action}{self.tr(' with the signed reservation amounts.\nOnly disposable test assets are used; fees are prepared separately.\nExecute this reservation once. Continue?')}", parent=self.root):
            self.submit('execute', {'session': trade['session'], 'mode': mode}, self.tr('Test execution started with the reserved amounts.'))

    def show_trade_evidence(self):
        trade = self.selected_trade()
        if trade:
            self._evidence_dialog(trade['evidence'], self.tr('Reserved trade records · Regtest'))

    def selected(self):
        selected = self.orders.selection()
        return self.order_map.get(selected[0]) if selected else None

    def selection_changed(self):
        o = self.selected()
        active = o is not None and o['status'] == 'active' and (not self.busy) and (not self.closing)
        self.reserve_button.configure(state='normal' if active and (not o['mine']) else 'disabled')
        self.cancel_button.configure(state='normal' if active and o['mine'] else 'disabled')

    def create(self):
        self.submit('order', {'side': 'sell' if self.side.get() == self.tr('Sell SMW') else 'buy', 'smw': self.smw.get(), 'btc': self.btc.get()}, self.tr('Signed test order published.'))

    def connect(self):
        try:
            port = int(self.port.get())
        except ValueError:
            self.message.set(self.tr('Enter a numeric peer P2P port.'))
            return
        self.submit('connect', {'host': self.peer_host.get(), 'port': port}, self.tr('Connected to a test peer and received orders.'))

    def listen(self):
        try:
            port = int(self.listen_port.get())
        except ValueError:
            self.message.set(self.tr('Enter a numeric listening port.'))
            return
        self.submit('listen', {'host': self.listen_host.get(), 'port': port}, self.tr('Listening for test-order connections at the configured IP.'))

    def cancel(self):
        o = self.selected()
        if o and o['mine']:
            self.submit('cancel', {'id': o['id']}, self.tr('Order canceled.'))

    def reserve(self):
        o = self.selected()
        if not o or o['mine']:
            return
        if messagebox.askyesno(self.tr('Reserve order'), f"{o['smw']} SMW ↔ {o['btc']}{self.tr(' BTC\n\nThis step does not transfer assets.\nReserve this test order?')}", parent=self.root):
            self.submit('reserve', {'id': o['id']}, self.tr('Order reserved. No assets transferred.'))

    def check(self, mode):
        self.submit('check', {'mode': mode}, self.tr('Disposable-asset check started.'))

    def submit(self, name, body, success):
        if self.busy or self.closing:
            return
        self.busy = True
        self.message.set(self.tr('Processing…'))
        self._buttons()

        def worker():
            try:
                result = self.app.command(name, body)
                failures = any((not p.get('ok', True) for p in result.get('peers', []))) or any((not p['delivered'] for p in result.get('delivery', [])))
                self.queue.put((True, success if not failures else success + self.tr(' Delivery to some peers failed.'), name, result))
            except Exception as exc:
                self.queue.put((False, self.tr(str(exc)), name, None))
            finally:
                if name.startswith('wallet_'):
                    body.pop('password', None)
        thread = threading.Thread(target=worker, daemon=True)
        self.workers.append(thread)
        thread.start()

    def _buttons(self):
        state = 'disabled' if self.busy or self.closing else 'normal'
        for b in (self.create_button, self.connect_button, self.sync_button, self.listen_button, self.link_button, self.link_refresh, self.swap_configure_button):
            b.configure(state=state)
        for b in self.peer_buttons.values():
            b.configure(state=state)
        running = bool(self.latest and self.latest['job'].get('running'))
        for b in (self.success_button, self.refund_button):
            b.configure(state='disabled' if running or state == 'disabled' else 'normal')
        self.selection_changed()
        self.trade_selection_changed()
        wallet = self.latest['wallet'] if self.latest else {'exists': False, 'locked': True}
        states = {'create': not wallet['exists'] and (not running), 'restore': not wallet['exists'] and (not running), 'unlock': wallet['exists'] and wallet['locked'], 'lock': not wallet['locked'], 'backup': not wallet['locked']}
        for action, button in self.wallet_buttons.items():
            button.configure(state='normal' if states[action] and state == 'normal' else 'disabled')

    def _paint(self):
        self.latest = self.app.state()
        s = self.latest
        self.peers.set(str(len(s['peers'])))
        self.count.set(str(sum((o['status'] == 'active' for o in s['orders']))))
        chosen = self.orders.selection()
        self.order_map = {o['id']: o for o in s['orders']}
        wanted = set(self.order_map)
        for iid in self.orders.get_children():
            if iid not in wanted:
                self.orders.delete(iid)
        for o in s['orders']:
            values = (self.tr('Sell') if o['side'] == 'sell' else self.tr('Buy'), o['smw'], o['btc'], self.tr(STATUS[o['status']]), self.tr('You') if o['mine'] else self.tr('Peer'))
            if self.orders.exists(o['id']):
                self.orders.item(o['id'], values=values)
            else:
                self.orders.insert('', 'end', iid=o['id'], values=values)
        self.my_port.configure(text=f"{self.tr('My P2P listener: ')}{s['relay_host']}:{s['relay_port']}")
        self.identity.configure(text=f"{self.tr('Order identity key\n')}{s['identity']}")
        wallet = s['wallet']
        self.wallet_status.configure(text=self.tr('No test vault yet.') if not wallet['exists'] else self.tr('Locked · Enter password to unlock.') if wallet['locked'] else self.tr('Unlocked · Stored in an AES-256-GCM encrypted file'))
        for coin, entry in self.wallet_entries.items():
            value = wallet['addresses'].get(coin, '')
            if entry.get() != value:
                entry.configure(state='normal')
                entry.delete(0, 'end')
                entry.insert(0, value)
                entry.configure(state='readonly')
        self.trade_map = {t['session']: t for t in s['trades']}
        self.peer_sessions.configure(values=list(self.trade_map))
        if not self.peer_session.get() and self.trade_map:
            self.peer_session.set(next(iter(self.trade_map)))
        for iid in self.trade_rows.get_children():
            if iid not in self.trade_map:
                self.trade_rows.delete(iid)
        for t in s['trades']:
            values = (self.tr('Sell') if t['direction'] == 'sell' else self.tr('Buy'), t['smw'], t['btc'], self.tr('Taker') if t['role'] == 'taker' else self.tr('Maker'), self.tr(PHASES.get(t['state'], t['state'])))
            if self.trade_rows.exists(t['session']):
                self.trade_rows.item(t['session'], values=values)
            else:
                self.trade_rows.insert('', 'end', iid=t['session'], values=values)
        peer_text = [f"{p['host']}:{p['port']}" for p in s['peers']]
        if list(self.peer_list.get(0, 'end')) != peer_text:
            self.peer_list.delete(0, 'end')
            for item in peer_text:
                self.peer_list.insert('end', item)
        j = s['job']
        if j.get('running'):
            text = self.tr('Running · ') + self.tr(PHASES.get(j.get('state'), j.get('state', '')))
        elif j.get('passed'):
            text = (self.tr('Passed · Both sides completed the swap') if j['mode'] == 'success' else self.tr('Passed · Both sides refunded after restart')) + f"\n{j['result']['elapsed_seconds']}{self.tr(' seconds · Accelerated regtest')}"
        elif j.get('passed') is False:
            text = self.tr('Check interrupted or failed · ') + j.get('error', self.tr('Review the records.'))
        else:
            text = self.tr('Not started.')
        self.job.set(text)
        self.evidence_button.configure(state='normal' if j.get('result') else 'disabled')
        self._buttons()

    def poll(self):
        if self.closing:
            return
        try:
            while True:
                ok, text, name, result = self.queue.get_nowait()
                self.busy = False
                self.message.set(text)
                if name in ('wallet_link', 'wallet_refresh'):
                    self.link_result.configure(state='normal')
                    self.link_result.delete('1.0', 'end')
                    if ok:
                        from .orders import amount
                        coin = result['coin'].upper()
                        shown = f"{coin} · {result['network']}{self.tr(' · Height ')}{result['height']}{self.tr('\nAddress: ')}{result['address']}{self.tr('\n\nConfirmed balance: ')}{amount(result['confirmed_units'])} {coin}{self.tr('\nAvailable: ')}{amount(result['available_units'])} {coin}{self.tr('\nImmature: ')}{amount(result['immature_units'])} {coin}{self.tr('\n\nRead-only · No private-key access or spending authority (read_only)')}"
                        if result.get('htlc_activation_height'):
                            shown += f"{self.tr('\nNode HTLC activation height: ')}{result['htlc_activation_height']}{self.tr(' · Currently active: ')}{(self.tr('Yes') if result['htlc_spending_supported'] else self.tr('No'))}"
                    else:
                        shown = text
                    self.link_result.insert('1.0', shown)
                    self.link_result.configure(state='disabled')
                if name.startswith('peer_') or name == 'swap_configure':
                    self.peer_result.configure(state='normal')
                    self.peer_result.delete('1.0', 'end')
                    if ok and name != 'swap_configure':
                        yes = lambda flag: self.tr('Confirmed') if result.get(flag) else self.tr('Not yet confirmed')
                        shown = f"{self.tr('Reservation: ')}{result['session']}{self.tr('\nMy swap keys prepared: ')}{yes('prepared')}{self.tr('\nPeer terms received: ')}{yes('peer_ready')}{self.tr('\nMy funding transaction saved: ')}{yes('funding_saved')}{self.tr('\nMy refund transaction retained: ')}{yes('refund_saved')}{self.tr('\nMy claim confirmed on chain: ')}{yes('received_confirmed')}{self.tr('\nMy refund confirmed on chain: ')}{yes('refund_confirmed')}"
                    else:
                        shown = text
                    self.peer_result.insert('1.0', shown)
                    self.peer_result.configure(state='disabled')
        except Empty:
            pass
        self._paint()
        self.timer = self.root.after(400, self.poll)

    def show_evidence(self):
        result = self.latest['job'].get('result')
        if not result:
            return
        self._evidence_dialog(result, self.tr('Test execution results'))

    def _evidence_dialog(self, result, title):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry('800x560')
        dialog.configure(bg=BG)
        text = tk.Text(dialog, bg=PANEL, fg=INK, wrap='word', font=('Consolas', 10), padx=14, pady=14)
        text.pack(fill='both', expand=True)
        text.insert('1.0', json.dumps(result, ensure_ascii=False, indent=2))
        text.configure(state='disabled')

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.root.after_cancel(self.timer)
        self.message.set(self.tr('Stopping active work and test nodes…'))
        self._buttons()
        done = threading.Event()

        def shutdown():
            try:
                self.app.close()
                for worker in self.workers:
                    worker.join(10)
            finally:
                done.set()
        self.shutdown_thread = threading.Thread(target=shutdown, daemon=True)
        self.shutdown_thread.start()

        def wait():
            if done.is_set():
                self.shutdown_thread.join()
                for name in ('side', 'smw', 'btc', 'port', 'message', 'peers', 'count', 'job', 'wallet_password', 'wallet_confirm', 'peer_host', 'listen_host', 'listen_port', 'peer_session', 'link_vars', 'swap_vars', 'language_choice'):
                    setattr(self, name, None)
                self.root.destroy()
            else:
                self.root.after(100, wait)
        self.root.after(100, wait)

    def run(self):
        self.root.mainloop()
