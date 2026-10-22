"""Windows complex-script shaping for vertical Mongolian Tk captions.

GDI shapes whole Mongolian words before rotation; Latin runs remain upright. Columns are composed individually
from left to right; rotating a multiline paragraph would reverse that order.
No key handling, commands, wallet data or user input passes through this module.
"""
from __future__ import annotations

import ctypes as c
from ctypes import wintypes as w
from functools import lru_cache
from pathlib import Path
import sys
import re
import tkinter as tk
from tkinter import font as tkfont, ttk


def contains_mongolian(text):
    return any('\u1800' <= char <= '\u18af' for char in str(text))


class _BitmapHeader(c.Structure):
    _fields_ = [('size', w.DWORD), ('width', w.LONG), ('height', w.LONG),
                ('planes', w.WORD), ('bits', w.WORD), ('compression', w.DWORD),
                ('image_size', w.DWORD), ('x_ppm', w.LONG), ('y_ppm', w.LONG),
                ('used', w.DWORD), ('important', w.DWORD)]


@lru_cache(maxsize=1)
def _apis():
    gdi, user = c.WinDLL('gdi32', use_last_error=True), c.WinDLL('user32', use_last_error=True)
    declarations = [
        (gdi.AddFontResourceExW, [w.LPCWSTR, w.DWORD, c.c_void_p], c.c_int),
        (gdi.CreateCompatibleDC, [w.HDC], w.HDC),
        (gdi.CreateFontW, [c.c_int] * 5 + [w.DWORD] * 8 + [w.LPCWSTR], w.HANDLE),
        (gdi.SelectObject, [w.HDC, w.HANDLE], w.HANDLE),
        (gdi.DeleteObject, [w.HANDLE], w.BOOL),
        (gdi.DeleteDC, [w.HDC], w.BOOL),
        (gdi.SetTextColor, [w.HDC, w.DWORD], w.DWORD),
        (gdi.SetBkColor, [w.HDC, w.DWORD], w.DWORD),
        (gdi.SetBkMode, [w.HDC, c.c_int], c.c_int),
        (gdi.CreateDIBSection, [w.HDC, c.POINTER(_BitmapHeader), w.UINT,
                               c.POINTER(c.c_void_p), w.HANDLE, w.DWORD], w.HANDLE),
        (user.DrawTextW, [w.HDC, w.LPCWSTR, c.c_int, c.POINTER(w.RECT), w.UINT], c.c_int),
    ]
    for function, args, result in declarations:
        function.argtypes, function.restype = args, result
    path = Path(__file__).resolve().parent.parent / 'assets/fonts/NotoSansMongolian-Regular.ttf'
    if not gdi.AddFontResourceExW(str(path), 0x10, None):
        raise OSError(c.get_last_error(), 'Could not load bundled Mongolian font')
    return gdi, user


@lru_cache(maxsize=128)
def render_vertical_ppm(text, pixel_size=20, foreground=(30, 47, 67), background=(255, 255, 255), inline=220):
    """Return a PPM raster and its dimensions, with a bounded raster cache."""
    if sys.platform != 'win32':
        raise OSError('The native Mongolian renderer requires Windows')
    gdi, user = _apis()
    dc = gdi.CreateCompatibleDC(None)
    font = gdi.CreateFontW(-pixel_size, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 4, 0, 'Noto Sans Mongolian')
    if not dc or not font:
        if dc:
            gdi.DeleteDC(dc)
        raise OSError(c.get_last_error(), 'Could not create Mongolian drawing context')
    latin_font = gdi.CreateFontW(-pixel_size, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 4, 0, 'Segoe UI')
    previous_font = gdi.SelectObject(dc, font)
    bitmap = previous_bitmap = None
    try:
        def measure(value):
            rect = w.RECT(0, 0, 0, 0)
            user.DrawTextW(dc, value, -1, c.byref(rect), 0x400 | 0x20 | 0x800)
            return rect.right, rect.bottom

        rgb_color = lambda rgb: rgb[0] | (rgb[1] << 8) | (rgb[2] << 16)
        gdi.SetTextColor(dc, rgb_color(foreground)); gdi.SetBkColor(dc, rgb_color(background)); gdi.SetBkMode(dc, 1)
        def raster(value):
            gdi.SelectObject(dc, font if contains_mongolian(value) else latin_font)
            tw, th = measure(value); tw += 8; th += 8
            header = _BitmapHeader(c.sizeof(_BitmapHeader), tw, -th, 1, 32)
            pixels = c.c_void_p()
            bitmap = gdi.CreateDIBSection(dc, c.byref(header), 0, c.byref(pixels), None, 0)
            if not bitmap: raise OSError('Could not allocate caption bitmap')
            old = gdi.SelectObject(dc, bitmap)
            blank = bytes((background[2],background[1],background[0],0))*(tw*th)
            c.memmove(pixels,blank,len(blank))
            rect=w.RECT(4,4,tw,th); user.DrawTextW(dc,value,-1,c.byref(rect),0x20|0x800)
            gdi.GdiFlush(); source=c.string_at(pixels,len(blank))
            gdi.SelectObject(dc,old);gdi.DeleteObject(bitmap)
            ink=[(x,y) for y in range(th) for x in range(tw) if source[(y*tw+x)*4:(y*tw+x)*4+3]!=blank[:3]]
            if not ink:return 1,1,bytes(background)
            left=max(0,min(x for x,y in ink)-2);right=min(tw,max(x for x,y in ink)+3)
            top=max(0,min(y for x,y in ink)-2);bottom=min(th,max(y for x,y in ink)+3)
            rgb=bytearray()
            for y in range(top,bottom):
                for x in range(left,right):rgb.extend(source[(y*tw+x)*4:(y*tw+x)*4+3][::-1])
            return right-left,bottom-top,bytes(rgb)
        pattern = r"[\u1800-\u18af\u200c\u200d\u202f]+|[A-Za-z0-9][A-Za-z0-9:.,/_%+@=()\-]*|[^ \t\n]|[ \t]+|\n"
        tokens=[]
        for match in re.finditer(pattern,text):
            value=match.group()
            if value.isspace():tokens.append((value,False,0,0,b''));continue
            vertical=contains_mongolian(value)
            tw,th,rgb=raster(value)
            tokens.append((value,vertical,tw,th,rgb))
        target=max(inline,max((tw if vertical else th for _,vertical,tw,th,_ in tokens),default=1))
        columns=[];current=[];advance=0
        for value,vertical,tw,th,rgb in tokens:
            if value=='\n':
                if current:columns.append(current)
                current=[];advance=0;continue
            if value.isspace():
                if current:advance+=max(3,pixel_size//4)
                continue
            length=tw if vertical else th
            if current and advance+length>target:columns.append(current);current=[];advance=0
            current.append((vertical,tw,th,rgb,advance));advance+=length+2
        if current:columns.append(current)
        columns=columns or [[]]
        widths=[max((th if vertical else tw for vertical,tw,th,_,_ in column),default=1) for column in columns]
        width=sum(widths)+8*(len(columns)-1)
        height=max((offset+(tw if vertical else th) for column in columns for vertical,tw,th,_,offset in column),default=1)
        output=bytearray(bytes(background)*(width*height));column_x=0
        for column,cross_width in zip(columns,widths):
            for vertical,tw,th,rgb,offset in column:
                left=column_x+(cross_width-(th if vertical else tw))//2
                for sy in range(th):
                    for sx in range(tw):
                        x,y=(left+th-1-sy,offset+sx) if vertical else (left+sx,offset+sy)
                        src=(sy*tw+sx)*3;dst=(y*width+x)*3
                        output[dst:dst+3]=rgb[src:src+3]
            column_x+=cross_width+8
        return f'P6\n{width} {height}\n255\n'.encode('ascii') + output, width, height
    finally:
        if previous_bitmap:
            gdi.SelectObject(dc, previous_bitmap)
        if bitmap:
            gdi.DeleteObject(bitmap)
        gdi.SelectObject(dc, previous_font)
        gdi.DeleteObject(font)
        gdi.DeleteObject(latin_font)
        gdi.DeleteDC(dc)


class _VerticalCaption:
    """Retain native controls, focus, state and textvariable notifications."""
    def __init__(self, *args, **kwargs):
        self._vertical_ready = False
        self._vertical_inline = kwargs.pop('vertical_inline', 100)
        if isinstance(self, (ttk.Button, ttk.Checkbutton, ttk.Menubutton)):
            self._vertical_inline = 95
        self._vertical_image = None
        self._vertical_key = None
        super().__init__(*args, **kwargs)
        self._vertical_ready = True
        variable = self.cget('textvariable')
        self._vertical_trace = None
        if variable:
            # StringVar destruction also deletes its trace commands. Do not add
            # this command to the widget's independent destruction registry.
            callback = self._register(lambda *_: self.refresh_vertical(), needcleanup=0)
            self.tk.call('trace', 'add', 'variable', variable, 'write', callback)
            self._vertical_trace = variable, callback
        self.bind('<Destroy>', self._clear_vertical_trace, add='+')
        self.bind('<<ThemeChanged>>', lambda _: self.refresh_vertical(), add='+')
        self.refresh_vertical()

    def _clear_vertical_trace(self, event):
        if event.widget is self and self._vertical_trace:
            variable, callback = self._vertical_trace
            try:
                self.tk.call('trace', 'remove', 'variable', variable, 'write', callback)
                self.deletecommand(callback)
            except tk.TclError:
                pass
            self._vertical_trace = None

    def configure(self, cnf=None, **kwargs):
        result = super().configure(cnf, **kwargs)
        if self._vertical_ready and (kwargs or isinstance(cnf, dict)):
            self.refresh_vertical()
        return result

    config = configure

    def refresh_vertical(self):
        variable = self.cget('textvariable')
        try:
            text = str(self.getvar(variable) if variable else self.cget('text'))
        except tk.TclError:
            return  # A textvariable can be disposed before its owning window.
        if not contains_mongolian(text):
            if self._vertical_image is not None:
                super().configure(image='')
                self._vertical_image = self._vertical_key = None
            return
        style = ttk.Style(self)
        style_name = self.cget('style') or self.winfo_class()
        state = self.state()
        fg = self.cget('foreground') if isinstance(self, ttk.Label) else ''
        bg = self.cget('background') if isinstance(self, ttk.Label) else ''
        fg = fg or style.lookup(style_name, 'foreground', state) or '#1e2f43'
        bg = bg or style.lookup(style_name, 'background', state) or '#ffffff'
        color = lambda value: tuple(channel // 257 for channel in self.winfo_rgb(value))
        font_name = style.lookup(style_name, 'font') or 'TkDefaultFont'
        font = tkfont.Font(self, font=font_name)
        size = font.actual('size')
        pixels = max(18, abs(size) if size < 0 else round(size * float(self.tk.call('tk', 'scaling'))))
        pixels = min(pixels, 18)
        inline = self._vertical_inline if len(text) < 120 or getattr(self,'_vertical_compact',False) else max(130,self._vertical_inline)
        available = getattr(self, '_vertical_max_width', 32768)
        ppm, width, _ = render_vertical_ppm(text,pixels,color(fg),color(bg),inline)
        while width > available and inline < 8000:
            inline = int(inline * 1.4)
            ppm, width, _ = render_vertical_ppm(text,pixels,color(fg),color(bg),inline)
        key = text, pixels, color(fg), color(bg), inline
        if key == self._vertical_key:
            return
        ppm, _, _ = render_vertical_ppm(*key)
        image = tk.PhotoImage(master=self, data=ppm, format='PPM')
        super().configure(image=image, compound='none')
        self._vertical_image, self._vertical_key = image, key


class VerticalLabel(_VerticalCaption, ttk.Label):
    pass


class VerticalButton(_VerticalCaption, ttk.Button):
    pass


class VerticalCheckbutton(_VerticalCaption, ttk.Checkbutton):
    pass


class VerticalMenubutton(_VerticalCaption, ttk.Menubutton):
    pass


class VerticalTreeview(ttk.Treeview):
    """Keep native rows/selection/scrollbars; paint Mongolian cells vertically."""
    def __init__(self, *args, **kwargs):
        self._heading_images = {}
        self._cell_labels = []
        self._cell_signature = None
        self._paint_job = None
        super().__init__(*args, **kwargs)
        self._vertical_style = f'Mongolian{id(self)}.Treeview'
        self._original_style = self.cget('style')
        for event in ('<Configure>', '<Expose>', '<<TreeviewSelect>>', '<ButtonRelease-1>', '<MouseWheel>'):
            self.bind(event, lambda _: self._schedule_cells(), add='+')
        self.bind('<Destroy>', self._stop_paint, add='+')

    def _stop_paint(self, event):
        if event.widget is self and self._paint_job:
            self._root().after_cancel(self._paint_job)
            self._paint_job = None

    def heading(self, column, option=None, **kwargs):
        if 'text' in kwargs:
            value = str(kwargs['text'])
            if contains_mongolian(value):
                background = ttk.Style(self).lookup('Treeview.Heading','background') or '#dcdad5'
                rgb=tuple(channel//257 for channel in self.winfo_rgb(background))
                ppm, _, _ = render_vertical_ppm(value, pixel_size=18, background=rgb, inline=80)
                self._heading_images[column] = tk.PhotoImage(master=self, data=ppm, format='PPM')
                kwargs['image'] = self._heading_images[column]
                kwargs['text'] = ''
            else:
                self._heading_images.pop(column, None)
                kwargs['image'] = ''
            style = ttk.Style(self)
            style.configure(self._vertical_style, rowheight=100)
            style.configure(self._vertical_style + '.Heading', padding=(4, 4), font=('Segoe UI', -80))
            style.layout(self._vertical_style + '.Heading', [('Treeheading.cell', {'sticky':'nswe'}), ('Treeheading.border', {'sticky':'nswe', 'children':[('Treeheading.padding', {'sticky':'nswe', 'children':[('Treeheading.image', {'sticky':'nswe'}), ('Treeheading.text', {'sticky':'we'})]})]})])
            self.configure(style=self._vertical_style if self._heading_images else self._original_style)
            self._schedule_cells()
        return super().heading(column, option, **kwargs)

    def insert(self, *args, **kwargs):
        result = super().insert(*args, **kwargs)
        self._schedule_cells()
        return result

    def delete(self, *args):
        result = super().delete(*args)
        self._schedule_cells()
        return result

    def yview(self, *args):
        result = super().yview(*args)
        if args:
            self._schedule_cells()
        return result

    def xview(self, *args):
        result = super().xview(*args)
        if args:
            self._schedule_cells()
        return result

    def _schedule_cells(self):
        if self._paint_job is None:
            self._paint_job = self._root().after_idle(self._paint_cells)

    def _paint_cells(self):
        self._paint_job = None
        signature = (tuple(self.selection()), self.yview(), self.xview(), bool(self._heading_images),
            tuple((item, self.item(item, 'values'), tuple(self.bbox(item, column) for column in self.cget('columns')))
                  for item in self.get_children('')))
        if signature == self._cell_signature:
            return
        self._cell_signature = signature
        for label in self._cell_labels:
            label.destroy()
        self._cell_labels.clear()
        if not self._heading_images:
            return
        for item in self.get_children(''):
            values = self.item(item, 'values')
            for column, value in zip(self.cget('columns'), values):
                if not contains_mongolian(value):
                    continue
                box = self.bbox(item, column)
                if not box:
                    continue
                x, y, width, height = box
                selected = item in self.selection()
                style = ttk.Style(self)
                state = ('selected',) if selected else ()
                bg = style.lookup('Treeview', 'background', state) or 'white'
                fg = style.lookup('Treeview', 'foreground', state) or 'black'
                label = VerticalLabel(self, text=value, background=bg, foreground=fg, anchor='center', vertical_inline=80)
                label.place(x=x, y=y, width=width, height=height)
                def select(event, row=item):
                    self.focus(row)
                    self.selection_set(row)
                    self.focus_set()
                label.bind('<Button-1>', select)
                label.bind('<MouseWheel>', lambda event: self.yview_scroll(-int(event.delta / 120), 'units'))
                self._cell_labels.append(label)
