"""Vertical raster order, live captions, table selection and dialog decisions."""
import sys
import tkinter as tk
import unittest
from sumuww.vertical_text import VerticalLabel, VerticalButton, VerticalTreeview, render_vertical_ppm
from sumuww.vertical_dialogs import _Message, _QueryString


@unittest.skipUnless(sys.platform == 'win32', 'Windows GDI renderer')
class VerticalMongolianTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def test_columns_keep_left_to_right_order_and_connected_ink(self):
        first = 'ᠮᠣᠩᠭᠣᠯ'
        a, aw, ah = render_vertical_ppm(first)
        both, bw, bh = render_vertical_ppm(first + '\nᠬᠡᠯᠡ')
        _, second_width, _ = render_vertical_ppm('ᠬᠡᠯᠡ')
        self.assertEqual(aw + second_width + 8, bw)
        self.assertEqual(ah, bh)
        ap = a.split(b'\n', 3)[3]
        bp = both.split(b'\n', 3)[3]
        for row in range(ah):
            self.assertEqual(ap[row*aw*3:(row+1)*aw*3], bp[row*bw*3:row*bw*3+aw*3])
        self.assertGreater(len(set(ap)), 2)

    def test_live_variable_language_change_and_disposal(self):
        variable = tk.StringVar(self.root, 'ᠮᠣᠩᠭᠣᠯ')
        label = VerticalLabel(self.root, textvariable=variable)
        self.assertIsNotNone(label._vertical_image)
        variable.set('1.25000000 SMW')
        self.assertIsNone(label._vertical_image)
        variable.set('ᠬᠡᠯᠡ')
        self.assertIsNotNone(label._vertical_image)
        del variable
        self.root.update_idletasks()
        label.destroy()

    def test_vertical_button_and_transaction_selection_preserve_values(self):
        clicks=[]
        button=VerticalButton(self.root,text='ᠮᠣᠩᠭᠣᠯ',command=lambda:clicks.append(True))
        button.invoke()
        self.assertEqual([True],clicks)
        table=VerticalTreeview(self.root,columns=('kind','amount'),show='headings')
        table.heading('kind',text='ᠮᠣᠩᠭᠣᠯ')
        table.heading('amount',text='SUMUWW')
        row=table.insert('','end',values=('ᠮᠣᠩᠭᠣᠯ','1.25000000'))
        table.selection_set(row)
        self.root.update_idletasks()
        self.assertEqual(('ᠮᠣᠩᠭᠣᠯ','1.25000000'),table.item(row,'values'))
        self.assertEqual((row,),table.selection())
        table.heading('kind',text='Transaction')
        self.assertFalse(table._heading_images)
        table.destroy()

    def _close_modal(self, accept):
        def close():
            for widget in self.root.winfo_children():
                if isinstance(widget, _Message):
                    (widget.ok if accept else widget.cancel)()
                    return
            self.root.after(20,close)
        self.root.after(20,close)

    def test_confirmation_cancel_is_false_and_accept_is_true(self):
        self._close_modal(False)
        self.assertFalse(_Message('SUMUWW','ᠮᠣᠩᠭᠣᠯ',self.root,question=True).result)
        self._close_modal(True)
        self.assertTrue(_Message('SUMUWW','ᠮᠣᠩᠭᠣᠯ',self.root,question=True).result)

    def test_secret_query_preserves_input_and_mask(self):
        def complete():
            for widget in self.root.winfo_children():
                if isinstance(widget,_QueryString):
                    self.assertEqual('*',widget.entry.cget('show'))
                    widget.entry.insert(0,'literal-secret-123')
                    widget.ok()
                    return
            self.root.after(20,complete)
        self.root.after(20,complete)
        result=_QueryString('SUMUWW','ᠮᠣᠩᠭᠣᠯ',parent=self.root,show='*').result
        self.assertEqual('literal-secret-123',result)
