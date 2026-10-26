"""SMW/BTC trading board; translated native controls and explicit spend review."""
import json,threading,time
from pathlib import Path
from queue import Queue,Empty
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
from ..localization import Localizer
from ..vertical_text import VerticalLabel,VerticalButton,VerticalTreeview,render_vertical_ppm
from ..desktop import Desktop as LegacyStyle
from . import VERSION
from .amounts import QUOTES,quote_total,show
from .vault import COINS
from .order_rows import OrderRows

class MarketDesktop:
    _style=LegacyStyle._style
    flow_actions=LegacyStyle.flow_actions
    def __init__(self,app,window=None):
        self.app=app;self.root=window or tk.Tk();self.localization=Localizer(app.store.directory)
        self.extra=json.loads((Path(__file__).parent/'translations.json').read_text(encoding='utf8'))
        self.root.title('SUMUWW P2P '+('Light' if app.flavor=='light' else 'Full')+' '+VERSION);self.root.geometry('1180x860');self.root.minsize(900,650)
        try:self.root.iconbitmap(str(app.root/'vendor/assets/sumuww.ico'))
        except tk.TclError:pass
        self.queue=Queue();self.busy=False;self.closing=False;self.workers=[];self.buttons={};self.images=[];self.last_result=None
        self.vars={k:tk.StringVar(value=v) for k,v in {'coin':'BTC','quantity':'','price':'','password':'','confirm':'',
                   'node_coin':'SMW','url':'','auth':'','server1':'','server2':'','server3':'',
                   'fee_mode':'','fee_rate':''}.items()}
        self.side=tk.IntVar(value=0);self.message=tk.StringVar();self.total=tk.StringVar();self.wallet_state=tk.StringVar();self.balance_text=tk.StringVar();self.last_paint=0
        self.vars['quantity'].trace_add('write',lambda *_:self.total_changed());self.vars['price'].trace_add('write',lambda *_:self.total_changed())
        self._style();self.layout();self.paint();self.root.protocol('WM_DELETE_WINDOW',self.close);self.timer=self.root.after(100,self.poll)

    def tr(self,text):return self.extra.get(self.localization.code,{}).get(text,self.localization.text(text))
    def label(self,parent,text,**kw):return VerticalLabel(parent,text=self.tr(text),**kw)
    def button(self,parent,text,command):
        b=VerticalButton(parent,text=self.tr(text),command=command);self.buttons[text]=b;return b
    def entry(self,parent,key,width=28,secret=False):return ttk.Entry(parent,textvariable=self.vars[key],width=width,show='●' if secret else '')
    def row(self,parent,text,key,secret=False):
        f=ttk.Frame(parent);f.pack(fill='x',pady=4);self.label(f,text,wraplength=250).pack(side='left',padx=(0,12));e=self.entry(f,key,secret=secret);e.pack(side='right',fill='x',expand=True);return e

    def page(self,notebook,title):
        container=ttk.Frame(notebook);canvas=tk.Canvas(container,highlightthickness=0,bg='#0b1222');bar=ttk.Scrollbar(container,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        body=ttk.Frame(canvas,padding=14);item=canvas.create_window((0,0),window=body,anchor='nw')
        body.bind('<Configure>',lambda _:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
        if self.localization.code=='mn-Mong':
            ppm,w,h=render_vertical_ppm(self.tr(title),pixel_size=16,inline=90)
            image=tk.PhotoImage(data=ppm);self.images.append(image);notebook.add(container,image=image)
        else:notebook.add(container,text=self.tr(title))
        return body

    def table(self,parent,columns):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True,pady=8)
        tree=VerticalTreeview(frame,columns=[c[0] for c in columns],show='headings',height=9,selectmode='browse')
        for key,label,width in columns:tree.heading(key,text=self.tr(label));tree.column(key,width=width,minwidth=80,stretch=True)
        scroll=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview);tree.configure(xscrollcommand=scroll.set)
        tree.pack(fill='both',expand=True);scroll.pack(fill='x');return tree

    def layout(self):
        self.buttons={};self.images=[];self.outer=ttk.Frame(self.root,padding=16);self.outer.pack(fill='both',expand=True)
        top=ttk.Frame(self.outer);top.pack(fill='x',pady=(0,10))
        self.label(top,'Trading board',font=('Segoe UI',20,'bold')).pack(side='left')
        self.language=tk.StringVar(value=self.localization.languages[self.localization.code]);choose=ttk.Combobox(top,textvariable=self.language,values=list(self.localization.languages.values()),state='readonly',width=26)
        choose.pack(side='right');choose.bind('<<ComboboxSelected>>',self.change_language)
        captions=[('Mainnet' if self.app.store.network=='mainnet' else 'Test network','#efb35d',90),
                  ('SUMUWW transfers activate at block 9100.','#edf2ff',250),
                  ('Bitcoin: light client' if self.app.flavor=='light' else 'Bitcoin: full node','#79d6b6',100)]
        if self.app.flavor=='light':captions.append(('Light mode checks proofs but relies on servers for complete transaction history.','#efb35d',350))
        if self.localization.code=='mn-Mong':
            metadata=ttk.Frame(self.outer);metadata.pack(fill='x',pady=4)
            for text,color,width in captions:
                label=self.label(metadata,text,foreground=color);label._vertical_max_width=width;label.refresh_vertical()
                label.pack(side='left',anchor='n',padx=(0,12))
        else:
            for text,color,_ in captions:self.label(self.outer,text,foreground=color,wraplength=1000).pack(anchor='w',pady=2)
        self.tabs=ttk.Notebook(self.outer);self.tabs.pack(fill='both',expand=True)
        board=self.page(self.tabs,'Trading board');trades=self.page(self.tabs,'My trades');wallet=self.page(self.tabs,'Trading wallet');connections=self.page(self.tabs,'Connections')
        form=ttk.Frame(board);form.pack(fill='x')
        left=ttk.Frame(form);left.pack(side='left',fill='both',expand=True,padx=(0,25));right=ttk.Frame(form);right.pack(side='left',fill='both',expand=True)
        direction=ttk.Frame(left);direction.pack(fill='x',pady=4)
        for value,label in ((0,'Sell SMW'),(1,'Buy SMW')):
            # Button captions use the same complex-script renderer as other controls.
            self.button(direction,label,lambda v=value:self.set_side(v)).pack(side='left',padx=4)
        self.side_caption=tk.StringVar(value=self.tr('Sell SMW' if self.side.get()==0 else 'Buy SMW'));VerticalLabel(left,textvariable=self.side_caption).pack(anchor='w')
        self.pair_select=ttk.Combobox(left,textvariable=self.vars['coin'],values=QUOTES,state='readonly');self.pair_select.pack(fill='x',pady=5);self.pair_select.bind('<<ComboboxSelected>>',lambda _:self.total_changed())
        self.row(left,'SMW quantity','quantity');self.row(left,'Price per SMW','price')
        VerticalLabel(left,textvariable=self.total).pack(anchor='w',pady=6)
        self.label(right,'Deposit the paying coin and network fees before publishing.',wraplength=380).pack(anchor='w',pady=4)
        self.label(right,'Full quantity only.',wraplength=380).pack(anchor='w',pady=4)
        self.button(right,'Publish',self.publish).pack(anchor='e',pady=6)
        actions=ttk.Frame(board);actions.pack(fill='x')
        self.button(actions,'Synchronize',lambda:self.work(self.app.sync)).pack(side='left',padx=5,pady=5)
        self.button(actions,'Trading wallet',lambda:self.tabs.select(2)).pack(side='left',padx=5,pady=5)
        self.orders=OrderRows(board,self.tr,self.open_order)
        self.label(trades,'Configure both chains before trading.',wraplength=1000).pack(anchor='w')
        self.trades=self.table(trades,[('side','Side',110),('coin','Trading pair',120),('quantity','SMW quantity',150),('total','Total',150),('session','Details',280)])
        toolbar=ttk.Frame(trades);toolbar.pack(fill='x')
        commands=[('Prepare trade',lambda s:self.app.engine.prepare(s)),('Exchange details',self.app.sync_trade),('Refresh status',self.app.engine.status),('Cancel trade',self.app.cancel_trade)]
        for i,(title,callback) in enumerate(commands):self.button(toolbar,title,lambda cb=callback:self.trade_command(cb)).grid(row=0,column=i,padx=4,pady=5,sticky='ew')
        for i,(title,action) in enumerate([('Lock my asset','lock'),('Receive coins','claim'),('Refund','refund')]):self.button(toolbar,title,lambda a=action:self.spend(a)).grid(row=1,column=i,padx=4,pady=5,sticky='ew')
        self.button(toolbar,'Increase fee',lambda:self.spend('increase_fee')).grid(row=1,column=3,padx=4,pady=5,sticky='ew')
        for i in range(4):toolbar.columnconfigure(i,weight=1)
        self.label(trades,'Locked funds can be refunded after the deadline.',wraplength=1000).pack(anchor='w',pady=10)
        self.trade_result=tk.Text(trades,height=9,wrap='word',bg='#142038',fg='#edf2ff',relief='flat',state='disabled');self.trade_result.pack(fill='x')
        self.row(wallet,'Password (12+ characters)','password',True);self.row(wallet,'Confirm new vault password','confirm',True)
        wallet_actions=ttk.Frame(wallet);wallet_actions.pack(fill='x',pady=8)
        for text,cb in [('Create wallet',self.wallet_create),('Unlock vault',self.wallet_unlock),('Lock',lambda:self.work(self.app.vault.lock)),('Back up wallet',self.wallet_backup),('Restore backup',self.wallet_restore)]:self.button(wallet_actions,text,cb).pack(side='left',padx=4)
        VerticalLabel(wallet,textvariable=self.wallet_state,wraplength=1000).pack(anchor='w',pady=6)
        self.label(wallet,'Keep the wallet backup and trade records.',wraplength=1000).pack(anchor='w',pady=6)
        self.addresses=tk.Text(wallet,height=10,wrap='word',bg='#142038',fg='#edf2ff',relief='flat',state='disabled');self.addresses.pack(fill='x')
        self.button(wallet,'Refresh balance',lambda:self.work(self.app.refresh_balances)).pack(anchor='w',pady=6)
        VerticalLabel(wallet,textvariable=self.balance_text,wraplength=1000).pack(anchor='w',pady=6)
        self.button(wallet,'Recovery backup',self.recovery_backup).pack(anchor='w',pady=10)
        self.label(connections,'Automatic peer connection',font=('Segoe UI',14,'bold')).pack(anchor='w')
        self.button(connections,'Connect',lambda:self.work(self.app.sync)).pack(anchor='e')
        self.listener=tk.StringVar();VerticalLabel(connections,textvariable=self.listener).pack(anchor='w',pady=8)
        self.label(connections,'Chain connection',font=('Segoe UI',14,'bold')).pack(anchor='w',pady=8)
        self.node_select=ttk.Combobox(connections,textvariable=self.vars['node_coin'],values=COINS,state='readonly');self.node_select.pack(fill='x');self.node_select.bind('<<ComboboxSelected>>',lambda _:self.load_connection())
        self.connection_fields=ttk.Frame(connections);self.connection_fields.pack(fill='x')
        self.button(connections,'Save connection',self.save_connection).pack(anchor='e',pady=8)
        self.label(connections,'Configure both chains before trading.',wraplength=1000).pack(anchor='w')
        VerticalLabel(self.outer,textvariable=self.message,wraplength=1100).pack(fill='x',pady=(10,0))
        self.load_connection();self.total_changed()
        for frame in (direction,actions,toolbar,wallet_actions):self.flow_actions(frame)

    def set_side(self,value):self.side.set(value);self.side_caption.set(self.tr('Sell SMW' if value==0 else 'Buy SMW'))
    def change_language(self,event=None):
        if self.busy:self.language.set(self.localization.languages[self.localization.code]);return
        code=next(c for c,name in self.localization.languages.items() if name==self.language.get());tab=self.tabs.index(self.tabs.select())
        status_key=next((k for k in ('Done.','Action could not be completed.','Working…') if self.message.get()==self.tr(k)),None)
        selected_order=self.orders.selection();selected_trade=self.trades.selection()
        saved={k:v.get() for k,v in self.vars.items()}
        self.localization.set(code);self.outer.destroy();self.layout()
        for k,v in saved.items():self.vars[k].set(v)
        self.tabs.select(tab);self.paint()
        if status_key:self.message.set(self.tr(status_key))
        if selected_order and self.orders.exists(selected_order[0]):self.orders.selection_set(selected_order[0])
        if selected_trade and self.trades.exists(selected_trade[0]):self.trades.selection_set(selected_trade[0])
        if self.last_result:self.show_trade(self.last_result)
    def total_changed(self):
        try:_,total,_=quote_total(self.vars['quantity'].get(),self.vars['price'].get(),self.vars['coin'].get());text=show(total,self.vars['coin'].get())+' '+self.vars['coin'].get()
        except ValueError:text='—'
        self.total.set(self.tr('Total')+': '+text)
    def selected(self,tree,kind):
        values=tree.selection()
        if not values:messagebox.showinfo('SUMUWW',self.tr('Select an order.' if kind=='order' else 'Select a trade.'),parent=self.root);return None
        return values[0]
    def publish(self):
        values={k:self.vars[k].get() for k in ('coin','quantity','price')};values.update(side='sell' if self.side.get()==0 else 'buy')
        def published(result):
            self.orders.selection_set(result['id'])
            self.message.set(self.tr('Done.' if result['shared'] else 'Waiting for peers'))
        self.work(lambda:self.app.create(**values),published)
    def cancel_post(self):
        oid=self.selected(self.orders,'order')
        if oid:self.work(lambda:self.app.cancel_post(oid))
    def open_order(self,oid):
        if self.busy:return
        self.orders.selection_set(oid)
        session=next((t['session'] for t in self.app.store.sessions() if t['post']==oid),None)
        if session:self.open_trade(session);return
        if self.app.store.post(oid)['maker']==self.app.store.identity.public:self.cancel_post();return
        self.reserve()

    def open_trade(self,sid):
        self.paint();self.tabs.select(1);self.trades.selection_set(sid)
        self.work(lambda:self.app.engine.status(sid),self.show_trade)
    def reserve(self):
        oid=self.selected(self.orders,'order')
        if not oid:return
        post=self.app.store.post(oid)
        review=f"{post['quantity']} SMW ↔ {show(post['quote_units'],post['coin'])} {post['coin']}\n"+self.tr('Full quantity only.')
        if messagebox.askyesno(self.tr('Trade'),review,parent=self.root):self.work(lambda:self.app.reserve(oid),self.open_trade)
    def trade_command(self,command):
        sid=self.selected(self.trades,'trade')
        if sid:self.work(lambda:command(sid),self.show_trade)
    def spend(self,action):
        sid=self.selected(self.trades,'trade')
        if not sid:return
        def reviewed(p):
            lines=[self.tr('Mainnet' if p['network']=='mainnet' else 'Test network'),p['amount']+' '+p['coin'],self.tr('Network fee')+': '+p['fee']+' '+p['coin'],self.tr('Recipient')+': '+p['to'],self.tr('Locked funds can be refunded after the deadline.'),self.tr('Send transaction?')]
            if p['action'].startswith('fee:'):
                lines=[self.tr('Mainnet' if p['network']=='mainnet' else 'Test network'),self.tr('Increase fee'),
                       self.tr('Network fee')+': '+p['fee']+' '+p['coin'],self.tr('Send transaction?')]
            def submit():
                result=self.app.engine.submit(sid,p['action'],p['txid'])
                try:self.app.sync_trade(sid)
                except (OSError,ValueError):pass
                return result
            if messagebox.askyesno(self.tr('Transaction review'),'\n\n'.join(lines),parent=self.root):self.work(submit,self.show_trade)
        self.work(lambda:self.app.engine.preview_fee_increase(sid) if action=='increase_fee' else self.app.engine.preview(sid,action),reviewed)
    def show_trade(self,result):
        # No secret preimages, signed raw transactions or private keys enter this view.
        if isinstance(result,dict) and 'body' in result:result={'state':'prepared','session':result['body'].get('session')}
        self.last_result=result
        phases={'prepared':'Prepare trade','completed':'Swap completed','refunded':'Refund confirmed','claim_ready':'Receive coins','refund_wait':'Checking refund height','locked':'Confirmed','pending':'Awaiting confirmations','canceled':'Canceled','unavailable':'Connection unavailable'}
        text=self.tr(phases.get(result.get('state'),'Done.'))
        if result.get('session'):
            terms=self.app.store.terms(result['session']);selling=self.app.engine.selling(terms)
            own='SMW' if selling else 'BTC';other='BTC' if selling else 'SMW';chains=result.get('chains',{})
            own_state=chains.get(own,{}).get('status');other_state=chains.get(other,{}).get('status')
            next_action=None
            if result.get('peer_ready') and result.get('state') not in ('canceled','completed','refunded','refund_wait','unavailable'):
                if own_state=='missing' and (selling or other_state=='locked'):next_action='Lock my asset'
                elif other_state=='locked' and (selling and own_state=='locked' or not selling and own_state=='claimed'):next_action='Receive coins'
                else:next_action='Awaiting confirmations'
            if next_action:text=self.tr(next_action)
            text+='\n'+show(terms['smw_units'],'SMW')+' SMW ↔ '+show(terms['quote_units'],'BTC')+' BTC'
        for coin,state in result.get('chains',{}).items():
            label={'missing':'Not funded','pending':'Awaiting confirmations','locked':'Confirmed','claimed':'Swap completed','refunded':'Refund confirmed','unavailable':'Connection unavailable'}.get(state['status'],'Status')
            text+='\n\n'+coin+': '+self.tr(label)
            if state.get('txid'):text+='\n'+state['txid']
        if result.get('remaining'):text+='\n\n'+self.tr('Refund wait (seconds)')+': '+', '.join(c+' '+str(v) for c,v in result['remaining'].items())
        self.trade_result.configure(state='normal');self.trade_result.delete('1.0','end');self.trade_result.insert('1.0',text);self.trade_result.configure(state='disabled')
    def wallet_create(self):
        password=self.vars['password'].get()
        if password!=self.vars['confirm'].get():messagebox.showerror('SUMUWW',self.tr('Password confirmation does not match.'),parent=self.root);return
        self.work(lambda:self.app.vault.create(password),lambda _:self.clear_passwords())
    def wallet_unlock(self):
        password=self.vars['password'].get();self.work(lambda:self.app.vault.unlock(password),lambda _:self.clear_passwords())
    def clear_passwords(self):self.vars['password'].set('');self.vars['confirm'].set('')
    def wallet_backup(self):
        path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.vault',initialfile='SUMUWW-trading-wallet.vault')
        if path:self.work(lambda:self.app.vault.backup(path))
    def wallet_restore(self):
        path=filedialog.askopenfilename(parent=self.root,filetypes=[('SUMUWW','*.vault *.smwbackup')]);password=self.vars['password'].get()
        if path:self.work(lambda:self.app.restore_backup(path,password) if path.endswith('.smwbackup') else self.app.vault.restore(path,password),lambda _:self.clear_passwords())
    def recovery_backup(self):
        path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.smwbackup',initialfile='SUMUWW-trade-recovery.smwbackup')
        if path:self.work(lambda:self.app.backup(path))
    def auth_file(self):
        path=filedialog.askopenfilename(parent=self.root)
        if path:self.vars['auth'].set(path)
    def load_connection(self):
        config=self.app.config['nodes'].get(self.vars['node_coin'].get(),{})
        for key,source in [('url','url'),('auth','credential_file')]:self.vars[key].set(config.get(source,''))
        for child in self.connection_fields.winfo_children():child.destroy()
        self.buttons.pop('Select file',None)
        if self.app.flavor=='light' and self.vars['node_coin'].get()=='BTC':
            from .light_network import DEFAULT_SERVERS
            servers=config.get('servers',DEFAULT_SERVERS)
            for i in range(3):
                key='server'+str(i+1);self.vars[key].set(servers[i] if i<len(servers) else '')
                self.row(self.connection_fields,'Bitcoin server',key)
        else:
            self.row(self.connection_fields,'RPC URL','url');self.row(self.connection_fields,'Authentication file','auth')
            self.button(self.connection_fields,'Select file',self.auth_file).pack(anchor='e')
        modes={'fast':'Fast','normal':'Normal','slow':'Slow'}
        self.vars['fee_mode'].set(self.tr(modes.get(config.get('fee_mode','normal'),'Normal')))
        self.vars['fee_rate'].set(str(config.get('fee_rate','')))
        fee_row=ttk.Frame(self.connection_fields);fee_row.pack(fill='x',pady=4)
        self.label(fee_row,'Automatic fee').pack(side='left')
        ttk.Combobox(fee_row,state='readonly',textvariable=self.vars['fee_mode'],values=[self.tr(modes[m]) for m in modes]).pack(side='right')
        self.row(self.connection_fields,'Manual fee rate (blank = automatic)','fee_rate')
        self.label(self.connection_fields,'yugeon/vB' if self.vars['node_coin'].get()=='SMW' else 'sat/vB').pack(anchor='e')
    def save_connection(self):
        coin=self.vars['node_coin'].get();value={'url':self.vars['url'].get().strip()}
        if coin=='BTC' and self.app.flavor=='light':value={'mode':'light','servers':[self.vars['server'+str(i)].get().strip() for i in range(1,4)]}
        else:value['credential_file']=self.vars['auth'].get().strip()
        # Editing an endpoint must not silently change existing fee/timing policy.
        old=self.app.config['nodes'].get(coin,{})
        value.update({k:old[k] for k in ('fee_units','confirmations','block_seconds') if k in old})
        value['fee_mode']={self.tr('Fast'):'fast',self.tr('Normal'):'normal',self.tr('Slow'):'slow'}.get(self.vars['fee_mode'].get(),'normal')
        if self.vars['fee_rate'].get().strip():
            value['fee_rate']=self.vars['fee_rate'].get().strip()
        self.app.header_progress=None
        def saved(info):
            if coin=='BTC' and self.app.flavor=='light':
                self.message.set(self.tr('Bitcoin headers')+': '+str(info['height'])+' · '+self.tr('Peer')+': '+str(info.get('verified_servers',0)))
        self.work(lambda:self.app.configure(coin,value),saved)
    def work(self,job,done=None):
        if self.busy or self.closing:return
        self.app.header_progress=None
        self.busy=True;self.message.set(self.tr('Working…'))
        for b in self.buttons.values():b.configure(state='disabled')
        self.paint()
        def run():
            try:self.queue.put((True,job(),done))
            except Exception as exc:self.queue.put((False,str(exc),None))
        thread=threading.Thread(target=run,daemon=False);self.workers.append(thread);thread.start()
    def poll(self):
        if self.busy and self.app.header_progress:
            height,total=self.app.header_progress;self.message.set(self.tr('Bitcoin headers')+f': {height:,} / {total:,}')
        try:
            ok,value,done=self.queue.get_nowait();self.busy=False
            for b in self.buttons.values():b.configure(state='normal')
            self.message.set(self.tr('Done.' if ok else 'Action could not be completed.'))
            self.paint()
            if ok and done:done(value)
            elif not ok:messagebox.showerror(self.tr('Action could not be completed.'),self.tr(value),parent=self.root)
        except Empty:pass
        if not self.busy and time.monotonic()-self.last_paint>1:
            self.paint();self.last_paint=time.monotonic()
        if self.closing and not self.busy:self.app.close();self.root.destroy();return
        self.timer=self.root.after(100,self.poll)
    def paint(self):
        state=self.app.state()
        self.orders.render(state['orders'],{t['post']:t['session'] for t in state['sessions']},state['delivery'],self.busy)
        for tree in (self.trades,):
            selected=tree.selection();tree.delete(*tree.get_children())
            for t in state['sessions']:tree.insert('','end',iid=t['session'],values=(self.tr('Sell SMW' if self.app.engine.selling(t) else 'Buy SMW'),'SMW/'+t['coin'],show(t['smw_units'],'SMW'),show(t['quote_units'],t['coin']),t['session'][:20]))
            if selected and tree.exists(selected[0]):tree.selection_set(selected[0])
        self.wallet_state.set(self.tr('Create a trading wallet and deposit funds first.' if not state['wallet']['exists'] else 'Locked · Enter password to unlock.' if state['wallet']['locked'] else 'Unlocked · Stored in an AES-256-GCM encrypted file'))
        self.balance_text.set('\n'.join(coin+': '+(self.tr('Connection unavailable') if value is None else self.tr('Confirmed')+' '+value['confirmed']+' · '+self.tr('Available')+' '+value['available']) for coin,value in state['balances'].items()))
        self.addresses.configure(state='normal');self.addresses.delete('1.0','end');self.addresses.insert('1.0','\n\n'.join(c+': '+a for c,a in state['wallet']['addresses'].items()));self.addresses.configure(state='disabled')
        self.listener.set(self.tr('Peer')+': '+str(len(state['peers']))+' · TLS 1.3' if state['peers'] else self.tr('Searching for trading peers…'))
    def close(self):
        if self.closing:return
        self.closing=True
        if self.busy:self.message.set(self.tr('Working…'));return
        self.root.after_cancel(self.timer);self.app.close();self.root.destroy()
    def run(self):self.root.mainloop()
