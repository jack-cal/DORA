"""Wallet-independent block browser; queries run through the asynchronous service."""
from datetime import datetime
import tkinter as tk
from tkinter import ttk

from .i18n import tr


class BlockBrowser(tk.Toplevel):
    PAGE_SIZE = 50

    def __init__(self, owner):
        from .app import _label, _button, _heading, VerticalTreeview, LocalizedStringVar
        super().__init__(owner.root)
        self.owner = owner
        self.closed = False
        self.busy = False
        self.timer = None
        self.offset = 0
        self.total = 0
        self.rows = []
        self.stored_proofs = 0
        self.lottery_jobs = None
        self.detail_generation = 0
        self.detail_timer = None
        self.detail = None
        self.detail_busy = False
        self.title(tr('All history') + ' · SUMUWW')
        self.transient(owner.root)
        self.geometry('1140x780')
        self.minsize(780, 620)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Escape>', lambda event: self.close())
        body = ttk.Frame(self, padding=14)
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        body.rowconfigure(5, weight=1)
        _label(body, text=tr('Validated blocks from genesis to the current tip. Includes all nodes.'), wraplength=1000).grid(row=0,column=0,sticky='ew')
        search = ttk.Frame(body)
        search.grid(row=1,column=0,sticky='ew',pady=10)
        _label(search,text=tr('Block height')).pack(side='left')
        self.query=tk.StringVar()
        self.entry=ttk.Entry(search,textvariable=self.query,width=16)
        self.entry.pack(side='left',padx=8)
        self.entry.bind('<Return>',lambda event:self.find())
        self.search_button=_button(search,text=tr('Search'),command=self.find)
        self.search_button.pack(side='left')
        self.table=VerticalTreeview(body,columns=('height','time','producer','transactions','proofs','hash'),show='headings',height=9,selectmode='browse')
        for key, caption, width in [('height','Block height',100),('time','Block time (local)',180),('producer','Producer',210),('transactions','Transaction',110),('proofs','Connection proofs',150),('hash','Block hash',510)]:
            _heading(self.table,key,text=tr(caption))
            self.table.column(key,width=width,minwidth=width,stretch=key=='hash')
        self.table.grid(row=2,column=0,sticky='nsew')
        vertical=ttk.Scrollbar(body,orient='vertical',command=self.table.yview)
        vertical.grid(row=2,column=1,sticky='ns')
        horizontal=ttk.Scrollbar(body,orient='horizontal',command=self.table.xview)
        horizontal.grid(row=3,column=0,sticky='ew')
        self.table.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        self.table.bind('<<TreeviewSelect>>', self.select_block)
        self.detail_state=LocalizedStringVar(self, value=tr('Select a block to view its transactions.'))
        _label(body,textvariable=self.detail_state,wraplength=1000).grid(row=4,column=0,sticky='ew',pady=6)
        self.transactions=VerticalTreeview(body,columns=('amount','confirmations','id'),show='tree headings',height=7,selectmode='browse')
        for key, caption, width in [('#0','Transaction',180),('amount','Output total SMW',160),('confirmations','Confirm',100),('id','Transaction ID',600)]:
            _heading(self.transactions,key,text=tr(caption))
            self.transactions.column(key,width=width,minwidth=width,stretch=key=='id')
        self.transactions.grid(row=5,column=0,sticky='nsew')
        self.transactions.bind('<<TreeviewOpen>>',self.expand_transaction)
        tx_vertical=ttk.Scrollbar(body,orient='vertical',command=self.transactions.yview)
        tx_vertical.grid(row=5,column=1,sticky='ns')
        tx_horizontal=ttk.Scrollbar(body,orient='horizontal',command=self.transactions.xview)
        tx_horizontal.grid(row=6,column=0,sticky='ew')
        self.transactions.configure(yscrollcommand=tx_vertical.set,xscrollcommand=tx_horizontal.set)
        tx_controls=ttk.Frame(body);tx_controls.grid(row=7,column=0,sticky='ew',pady=6)
        self.tx_previous=_button(tx_controls,text=tr('Previous'),command=lambda:self.load_transactions(self.detail['block_hash'],max(0,self.detail['offset']-self.PAGE_SIZE)))
        self.tx_previous.pack(side='left')
        self.tx_next=_button(tx_controls,text=tr('Next'),command=lambda:self.load_transactions(self.detail['block_hash'],self.detail['offset']+self.PAGE_SIZE))
        self.tx_next.pack(side='left',padx=8)
        self.state=LocalizedStringVar(self)
        _label(body,textvariable=self.state,wraplength=1000).grid(row=8,column=0,sticky='ew',pady=8)
        controls=ttk.Frame(body);controls.grid(row=9,column=0,sticky='ew')
        self.previous=_button(controls,text=tr('Previous'),command=lambda:self.load(max(0,self.offset-self.PAGE_SIZE)))
        self.previous.pack(side='left')
        self.next=_button(controls,text=tr('Next'),command=lambda:self.load(self.offset+self.PAGE_SIZE))
        self.next.pack(side='left',padx=8)
        self.refresh=_button(controls,text=tr('Refresh'),command=lambda:self.load(0))
        self.refresh.pack(side='left')
        _button(controls,text=tr('Close'),command=self.close).pack(side='right')
        self.load(0)

    def controls(self):
        self.previous.configure(state='normal' if not self.busy and self.offset>0 else 'disabled')
        self.next.configure(state='normal' if not self.busy and self.offset+self.PAGE_SIZE<self.total else 'disabled')
        for button in (self.search_button,self.refresh):
            button.configure(state='disabled' if self.busy else 'normal')
        available = self.detail is not None and not self.detail_busy and not self.busy
        self.tx_previous.configure(state='normal' if available and self.detail['offset']>0 else 'disabled')
        self.tx_next.configure(state='normal' if available and self.detail['offset']+self.PAGE_SIZE<self.detail['total'] else 'disabled')

    def find(self):
        value=self.query.get().strip()
        if not value.isascii() or not value.isdecimal():
            self.state.set(tr('Block height')+f': 0–{max(0,self.total-1)}')
            return
        self.load(0,int(value))

    def load(self,offset,height=None):
        if self.closed or self.busy:return
        self.clear_detail()
        self.busy=True;self.controls();self.state.set(tr('Loading history…'))
        try:self.poll(self.owner.service.block_history(offset,self.PAGE_SIZE,height))
        except Exception as error:self.failed(error)

    def poll(self,future):
        self.timer=None
        if self.closed:return
        if not future.done():
            self.timer=self.after(60,lambda:self.poll(future));return
        try:
            result=future.result()
            self.offset=result['offset'];self.total=result['total'];self.rows=result['blocks']
            self.stored_proofs=result.get('stored_proofs',0)
            self.lottery_jobs=result.get('lottery_jobs')
            self.render()
        except Exception as error:self.failed(error);return
        self.busy=False;self.controls()

    def render(self):
        children=self.table.get_children()
        if children:self.table.delete(*children)
        for block in self.rows:
            origin=tr({'local':'This node','other':'Other node'}.get(block['origin'],'Producer unavailable'))
            identity=block.get('producer_id')
            if identity:origin+=' · '+identity
            time=datetime.fromtimestamp(block['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            self.table.insert('','end',iid=block['hash'],values=(block['height'],time,origin,block.get('transactions',0),block.get('proofs',0),block['hash']))
        if self.rows:
            status=tr('Block height')+f": {self.rows[-1]['height']:,}–{self.rows[0]['height']:,} / {self.total-1:,} · "+tr('Connection proofs')+f': {self.stored_proofs:,}'
            if self.lottery_jobs is not None:
                jobs=self.lottery_jobs
                status+='\n'+tr('Local lottery jobs')+f": {jobs['total']:,} · "+tr('Not selected')+f": {jobs['not_selected']:,} · "+tr('Selected pending')+f": {jobs['selected_pending']:,} · "+tr('Selected complete')+f": {jobs['selected_complete']:,}"
                if jobs['awaiting_lottery']:
                    status+=' · '+tr('Pending')+f": {jobs['awaiting_lottery']:,}"
            self.state.set(status)

    def clear_detail(self):
        self.detail_generation += 1
        if self.detail_timer is not None:
            self.after_cancel(self.detail_timer); self.detail_timer=None
        self.detail=None;self.detail_busy=False
        children=self.transactions.get_children()
        if children:self.transactions.delete(*children)
        self.detail_state.set(tr('Select a block to view its transactions.'))

    def select_block(self,event=None):
        selected=self.table.selection()
        if selected and not self.busy and not self.closed:
            if self.detail is not None and self.detail['block_hash']==selected[0]:return
            self.load_transactions(selected[0],0)

    def load_transactions(self,digest,offset):
        if self.closed:return
        self.clear_detail();self.detail_busy=True;self.controls()
        generation=self.detail_generation
        self.detail_state.set(tr('Loading history…'))
        try:
            future=self.owner.service.block_transactions(digest,offset,self.PAGE_SIZE)
            self.poll_transactions(future,generation)
        except Exception as error:self.detail_failed(error)

    def poll_transactions(self,future,generation):
        if self.closed or generation!=self.detail_generation:return
        self.detail_timer=None
        if not future.done():
            self.detail_timer=self.after(60,lambda:self.poll_transactions(future,generation));return
        try:
            self.detail=future.result();self.render_transactions()
        except Exception as error:self.detail_failed(error);return
        self.detail_busy=False;self.controls()

    def detail_failed(self,error):
        from .app import _error_message
        self.detail_busy=False;self.detail=None
        self.detail_state.set(tr('Block is no longer in the active chain. Refresh the list.') if str(error)=='Block is no longer in the active chain. Refresh the list.' else _error_message(error))
        self.controls()

    def render_transactions(self):
        from .primitives import format_amount
        children=self.transactions.get_children()
        if children:self.transactions.delete(*children)
        if self.detail is None:return
        d=self.detail
        for index,tx in enumerate(d['transactions']):
            key=f'tx-{index}'
            self.transactions.insert('','end',iid=key,text=tr('Mining reward') if tx['coinbase'] else tr('Transaction'),
                values=(format_amount(tx['output_total']),d['confirmations'],tx['txid']))
            if tx.get('mining_reward'):
                from .rewards import reward_rows
                for label, value in reward_rows(tx['mining_reward']):
                    self.transactions.insert(key, 'end', text=tr(label), values=(value, '', ''))
            self.transactions.insert(key,'end',iid=key+'-pending',text='…')
        self.detail_state.set(tr('Block height')+f": {d['height']:,} · "+tr('Transaction')+f": {d['offset']+1:,}–{d['offset']+len(d['transactions']):,} / {d['total']:,}")

    def expand_transaction(self,event=None):
        from .primitives import format_amount
        key=self.transactions.focus()
        if self.detail is None or not self.transactions.exists(key+'-pending'):return
        self.transactions.delete(key+'-pending')
        tx=self.detail['transactions'][int(key.split('-')[1])]
        if not tx['coinbase']:
            for item in tx['inputs']:
                self.transactions.insert(key,'end',text=tr('Inputs'),values=('', '',item['txid']+f":{item['index']}"))
        for item in tx['outputs']:
            self.transactions.insert(key,'end',text=tr('Outputs')+f" #{item['index']}",
                values=(format_amount(item['value']),'',item['address'] or item['script']))

    def failed(self,error):
        from .app import _error_message
        self.busy=False;self.state.set(_error_message(error));self.controls()

    def refresh_language(self):
        self.title(tr('All history')+' · SUMUWW')
        for widget in self.owner._walk_widgets(self):
            message=getattr(widget,'_localized_text',None)
            if message is not None:widget.configure(text=message.render())
            for column,message in getattr(widget,'_localized_headings',{}).items():
                widget.heading(column,text=message.render())
        if not self.busy:
            selected=self.table.selection()
            self.render()
            if selected and self.table.exists(selected[0]):self.table.selection_set(selected)
        if self.detail is not None:self.render_transactions()

    def close(self):
        if self.closed:return
        self.closed=True
        if self.timer is not None:self.after_cancel(self.timer)
        if self.detail_timer is not None:self.after_cancel(self.detail_timer)
        if self.owner._blocks_dialog is self:self.owner._blocks_dialog=None
        self.destroy()
