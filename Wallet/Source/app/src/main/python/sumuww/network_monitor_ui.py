"""Live independent P2P network survey screen; no miner control or RPC."""
from pathlib import Path
import time
from .windows_tk import prepare_tk
prepare_tk()
import tkinter as tk
from tkinter import ttk
from .i18n import LANGUAGES,Translator,load_language,save_language,set_translator,tr
from .vertical_text import VerticalLabel,VerticalButton,VerticalTreeview
from .network_monitor import NetworkSurvey


class NetworkMonitorApp:
    def __init__(self,root,directory,*,network='dora',survey=None):
        self.root=root;self.directory=Path(directory);self._job=None;self._closing=False
        self.language_path=self.directory/'ui-language.json'
        self.translator=Translator(load_language(self.language_path));set_translator(self.translator)
        root._sumuww_translator=self.translator
        self.survey=survey or NetworkSurvey(self.directory,network=network)
        self._signature=None;self._destroyed=False
        root.geometry('1180x650');root.minsize(900,450)
        root.protocol('WM_DELETE_WINDOW',self._close);root.bind('<Destroy>',self._dispose,add='+')
        frame=ttk.Frame(root,padding=18);frame.pack(fill='both',expand=True)
        frame.columnconfigure(0,weight=1);frame.rowconfigure(3,weight=1)
        self.heading=VerticalLabel(frame,font=('Segoe UI',18));self.heading.grid(row=0,column=0,sticky='w')
        self.language=tk.StringVar(value=dict(LANGUAGES)[self.translator.language])
        self.language_box=ttk.Combobox(frame,textvariable=self.language,values=[name for _,name in LANGUAGES],state='readonly',width=22)
        self.language_box.grid(row=0,column=1,sticky='e');self.language_box.bind('<<ComboboxSelected>>',self._language)
        self.status=tk.StringVar();self.status_label=VerticalLabel(frame,textvariable=self.status,wraplength=1100)
        self.status_label.grid(row=1,column=0,columnspan=2,sticky='ew',pady=12)
        self.note=VerticalLabel(frame,wraplength=1100)
        self.note.grid(row=2,column=0,columnspan=2,sticky='ew',pady=(0,8))
        table_frame=ttk.Frame(frame);table_frame.grid(row=3,column=0,columnspan=2,sticky='nsew')
        table_frame.columnconfigure(0,weight=1);table_frame.rowconfigure(0,weight=1)
        self.columns=('peer_id','addresses','height','tip','status','updates','seen','direction')
        self.table=VerticalTreeview(table_frame,columns=self.columns,show='headings',height=12)
        for name,width in zip(self.columns,(155,300,90,165,150,90,95,130)):self.table.column(name,width=width,minwidth=70)
        self.table.grid(row=0,column=0,sticky='nsew')
        y=ttk.Scrollbar(table_frame,orient='vertical',command=self.table.yview);y.grid(row=0,column=1,sticky='ns')
        x=ttk.Scrollbar(table_frame,orient='horizontal',command=self.table.xview);x.grid(row=1,column=0,sticky='ew')
        self.table.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        self.refresh_button=VerticalButton(frame,command=self.request_refresh)
        self.refresh_button.grid(row=4,column=0,sticky='w',pady=10)
        self._translate();self.survey.start();self._poll()

    def _translate(self):
        from .brand import apply_window_icon
        set_translator(self.translator);apply_window_icon(self.root,self.translator.language)
        self.root.title(str(tr('SUMUWW Network Monitor')))
        self.heading.configure(text=str(tr('SUMUWW Network Monitor')))
        self.refresh_button.configure(text=str(tr('Refresh')))
        self.note.configure(text=str(tr('Direct network responses; discovered peers only. Mining status is not observable.')))
        for column,label in zip(self.columns,('Node ID','Node address','Block height','Advertised tip','Status','Tip updates','Last response','Direction')):
            self.table.heading(column,text=str(tr(label)))
        ttk.Style(self.root).configure('Treeview',rowheight=32 if self.translator.language=='ar' else 25)

    def _language(self,_event=None):
        code=next(code for code,name in LANGUAGES if name==self.language.get())
        self.translator.set_language(code);save_language(code,self.language_path)
        self._translate();self._signature=None;self.refresh()

    def refresh(self):
        if self._destroyed:return
        set_translator(self.translator);value=self.survey.snapshot();rows=[]
        for item in value['nodes']:
            rows.append((item['peer_id'],', '.join(item['addresses']),str(item['height']) if item['height'] is not None else '—',
                         item['tip'],str(tr('Tip hash, PoW and Merkle checked' if item['tip_pow_merkle_checked'] else 'Protocol response confirmed')),
                         str(item['tip_updates']),time.strftime('%H:%M:%S',time.localtime(item['seen'])),
                         str(tr('Incoming connection' if item.get('direction')=='incoming' else 'Outgoing'))))
        if rows!=self._signature:
            for item in self.table.get_children():self.table.delete(item)
            for row in rows:self.table.insert('','end',values=row)
            self._signature=rows
        if value.get('error'):self.status.set(str(tr('Network discovery failed')))
        elif self._closing:self.status.set(str(tr('Stopping...')))
        else:self.status.set(str(tr('Responding nodes: {0} | Discovered addresses: {1} | Checking: {2}',len(rows),value['candidates'],value['checking'])))

    def request_refresh(self):
        self.survey.request_refresh()
        self.refresh()

    def _poll(self):
        self._job=None
        if self._destroyed:return
        self.refresh()
        if self._closing and self.survey.stopped:self.root.destroy();return
        self._job=self.root.after(500,self._poll)

    def _close(self):
        self._closing=True;self.survey.stop();self.refresh()

    def _dispose(self,event):
        if event.widget is self.root:
            self._destroyed=True;self.survey.stop()
            if self._job is not None:self.root.after_cancel(self._job);self._job=None
