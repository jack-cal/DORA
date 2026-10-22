"""Vertical Mongolian prompts without changing validation or user input."""
import tkinter as tk
from tkinter import messagebox as native_messagebox, simpledialog as native_simpledialog, ttk
from .vertical_text import VerticalLabel, VerticalButton, contains_mongolian, render_vertical_ppm
from .i18n import tr


class _Message(native_simpledialog.Dialog):
    def __init__(self, title, message, parent, question=False):
        self.message = str(message)
        self.question = question
        self.result = False
        super().__init__(parent, str(title))

    def body(self, master):
        canvas = tk.Canvas(master, width=560, height=360, highlightthickness=0)
        xbar = ttk.Scrollbar(master, orient='horizontal', command=canvas.xview)
        ybar = ttk.Scrollbar(master, orient='vertical', command=canvas.yview)
        canvas.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        canvas.grid(row=0, column=0, sticky='nsew')
        ybar.grid(row=0, column=1, sticky='ns')
        xbar.grid(row=1, column=0, sticky='ew')
        label = VerticalLabel(canvas, text=self.message, vertical_inline=320, padding=12)
        canvas.create_window(0, 0, window=label, anchor='nw')
        label.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox('all'))

    def buttonbox(self):
        box = ttk.Frame(self)
        if self.question:
            VerticalButton(box, text=tr('Confirm'), command=self.ok).pack(side='left', padx=6)
            cancel = VerticalButton(box, text=tr('Cancel'), command=self.cancel)
            cancel.pack(side='left', padx=6)
            cancel.focus_set()
        else:
            VerticalButton(box, text=tr('Confirm'), command=self.ok).pack(padx=6)
        box.pack(pady=8)
        self.bind('<Escape>', self.cancel)

    def apply(self):
        self.result = True


class _MessageProxy:
    def __getattr__(self, name):
        return getattr(native_messagebox, name)

    def showerror(self, title, message, **kwargs):
        if not contains_mongolian(message):
            return native_messagebox.showerror(title, message, **kwargs)
        _Message(title, message, kwargs.get('parent'))
        return 'ok'

    def askyesno(self, title, message, **kwargs):
        if not contains_mongolian(message):
            return native_messagebox.askyesno(title, message, **kwargs)
        return bool(_Message(title, message, kwargs.get('parent'), question=True).result)


class _QueryCaption:
    def body(self, master):
        entry = super().body(master)
        for child in master.winfo_children():
            if isinstance(child, tk.Label) and contains_mongolian(child.cget('text')):
                ppm, _, _ = render_vertical_ppm(str(child.cget('text')), inline=240)
                child._vertical_image = tk.PhotoImage(master=child, data=ppm, format='PPM')
                child.configure(image=child._vertical_image, compound='none')
        return entry


class _QueryString(_QueryCaption, native_simpledialog._QueryString):
    pass


class _QueryInteger(_QueryCaption, native_simpledialog._QueryInteger):
    pass


class _SimpleProxy:
    def __getattr__(self, name):
        return getattr(native_simpledialog, name)

    def askstring(self, title, prompt, **kwargs):
        if contains_mongolian(prompt):
            return _QueryString(title, prompt, **kwargs).result
        return native_simpledialog.askstring(title, prompt, **kwargs)

    def askinteger(self, title, prompt, **kwargs):
        if contains_mongolian(prompt):
            return _QueryInteger(title, prompt, **kwargs).result
        return native_simpledialog.askinteger(title, prompt, **kwargs)


messagebox = _MessageProxy()
simpledialog = _SimpleProxy()
