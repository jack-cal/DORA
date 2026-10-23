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
        self.title(tr('All blocks') + ' · SUMUWW')
        self.transient(owner.root)
        self.geometry('1140x600')
        self.minsize(780, 380)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Escape>', lambda event: self.close())
        body = ttk.Frame(self, padding=14)
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
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
        self.table=VerticalTreeview(body,columns=('height','time','producer','hash'),show='headings',height=16,selectmode='browse')
        for key, caption, width in [('height','Block height',100),('time','Block time (local)',180),('producer','Producer',580),('hash','Block hash',510)]:
            _heading(self.table,key,text=tr(caption))
            self.table.column(key,width=width,minwidth=width,stretch=key=='hash')
        self.table.grid(row=2,column=0,sticky='nsew')
        vertical=ttk.Scrollbar(body,orient='vertical',command=self.table.yview)
        vertical.grid(row=2,column=1,sticky='ns')
        horizontal=ttk.Scrollbar(body,orient='horizontal',command=self.table.xview)
        horizontal.grid(row=3,column=0,sticky='ew')
        self.table.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        self.state=LocalizedStringVar(self)
        _label(body,textvariable=self.state,wraplength=1000).grid(row=4,column=0,sticky='ew',pady=8)
        controls=ttk.Frame(body);controls.grid(row=5,column=0,sticky='ew')
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

    def find(self):
        value=self.query.get().strip()
        if not value.isascii() or not value.isdecimal():
            self.state.set(tr('Block height')+f': 0–{max(0,self.total-1)}')
            return
        self.load(0,int(value))

    def load(self,offset,height=None):
        if self.closed or self.busy:return
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
            self.table.insert('','end',iid=block['hash'],values=(block['height'],time,origin,block['hash']))
        if self.rows:
            self.state.set(tr('Block height')+f": {self.rows[-1]['height']:,}–{self.rows[0]['height']:,} / {self.total-1:,}")

    def failed(self,error):
        from .app import _error_message
        self.busy=False;self.state.set(_error_message(error));self.controls()

    def refresh_language(self):
        self.title(tr('All blocks')+' · SUMUWW')
        for widget in self.owner._walk_widgets(self):
            message=getattr(widget,'_localized_text',None)
            if message is not None:widget.configure(text=message.render())
            for column,message in getattr(widget,'_localized_headings',{}).items():
                widget.heading(column,text=message.render())
        if not self.busy:self.render()

    def close(self):
        if self.closed:return
        self.closed=True
        if self.timer is not None:self.after_cancel(self.timer)
        if self.owner._blocks_dialog is self:self.owner._blocks_dialog=None
        self.destroy()
