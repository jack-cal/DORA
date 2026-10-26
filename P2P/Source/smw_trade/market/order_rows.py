"""Visible order terms with a real, keyboard-accessible action button per row."""
from tkinter import ttk
from ..vertical_text import VerticalLabel, VerticalButton


class OrderRows(ttk.Frame):
    def __init__(self, parent, tr, command):
        super().__init__(parent)
        self.tr, self.command = tr, command
        self.rows, self._selected, self.signature = {}, (), None
        self.pack(fill='x', pady=8)
        for col, title in enumerate(('Side','SMW quantity','Price per SMW','Total','Status','Trade')):
            VerticalLabel(self,text=tr(title),wraplength=155).grid(row=0,column=col,sticky='w',padx=6,pady=6)
            self.columnconfigure(col,weight=1)

    def render(self, orders, sessions, delivery, busy=False):
        signature=repr((orders,sessions,delivery,busy))
        if signature==self.signature:return
        self.signature=signature
        for data in self.rows.values():
            for widget in data['widgets']:widget.destroy()
        self.rows={}
        for index,post in enumerate(orders,1):
            sid=sessions.get(post['id']);mine=post['mine'];state=post['status']
            status={'active':'Available','reserved':'Reserved','canceled':'Canceled','expired':'Expired'}[state]
            if mine and state=='active' and not delivery.get(post['id']):status='Waiting for peers'
            action='Open trade' if sid else 'Cancel my order' if mine and state=='active' else 'Trade'
            fields=[self.tr('Sell SMW' if post['side']=='sell' else 'Buy SMW'),post['quantity']+' SMW',
                    post['price']+' BTC',post['total']+' BTC',self.tr(status)]
            widgets=[]
            for col,value in enumerate(fields):
                label=VerticalLabel(self,text=value,wraplength=155)
                label.grid(row=index,column=col,sticky='nw',padx=6,pady=8);widgets.append(label)
            button=VerticalButton(self,text=self.tr(action),command=lambda oid=post['id']:self.invoke(oid))
            button.grid(row=index,column=5,sticky='ew',padx=6,pady=8)
            button.configure(state='normal' if not busy and (sid or state=='active') else 'disabled')
            self.rows[post['id']]={'widgets':widgets+[button],'button':button}
        if self._selected and self._selected[0] not in self.rows:self._selected=()

    def invoke(self, oid):
        self._selected=(oid,);self.command(oid)

    def selection(self):return self._selected
    def selection_set(self,oid):self._selected=(oid,)
    def exists(self,oid):return oid in self.rows
    def get_children(self):return tuple(self.rows)
