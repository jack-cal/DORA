"""Original typography must initialize and paint, not just construct widgets."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(sys.platform == 'win32', 'Windows native font rendering')
class WindowsTkRenderingTests(unittest.TestCase):
    def test_source_entry_selects_system_dpi_before_creating_windows(self):
        source = Path(__file__).resolve().parents[1]
        code = r'''
import ctypes
from sumuww.windows_tk import prepare_tk
prepare_tk()
awareness=ctypes.c_int(-1)
shcore=ctypes.WinDLL('shcore')
shcore.GetProcessDpiAwareness.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int)]
assert shcore.GetProcessDpiAwareness(None,ctypes.byref(awareness))==0
assert awareness.value==1,awareness.value
print('SYSTEM_DPI_AWARE')
'''
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=source,
                                env=dict(os.environ, PYTHONPATH=str(source)),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('SYSTEM_DPI_AWARE', result.stdout)

    def test_original_fonts_remain_reachable_at_four_display_scales(self):
        source = Path(__file__).resolve().parents[1]
        code = r'''
import gc, json, tempfile
from pathlib import Path
from concurrent.futures import Future
from types import SimpleNamespace
from sumuww.app import SumuwwApp
from sumuww.i18n import LANGUAGE_CODES
from sumuww.profiles import REGTEST
import tkinter as tk
from tkinter import ttk
cases=0
with tempfile.TemporaryDirectory(prefix='sumuww-dpi-layout-') as folder:
    for scale in (1,1.25,1.5,2):
        root=tk.Tk()
        root.tk.call('tk','scaling',scale*96/72)
        service=SimpleNamespace(directory=Path(folder),network=REGTEST,
                                start=lambda:Future(),status=lambda:Future())
        app=SumuwwApp(root,service,language='en',language_path=Path(folder)/'language.json')
        app._started=True
        # Also exercise a viewport narrower than high-DPI content.
        root.minsize(320,240)
        root.geometry('940x700')
        for language in LANGUAGE_CODES:
            app.set_language(language)
            root.update()
            outer_right=app._outer.winfo_rootx()+app._outer.winfo_width()
            for widget in app._walk_widgets(app._outer):
                if isinstance(widget,ttk.Button) and widget.winfo_ismapped():
                    assert widget.winfo_rootx()+widget.winfo_width()<=outer_right+2,(scale,language,widget.cget('text'))
            if app._outer.winfo_width()>app._canvas.winfo_width():
                assert app._horizontal_scroll.winfo_ismapped(),(scale,language)
                app._canvas.xview_moveto(1)
                root.update()
                assert app._canvas.xview()[1]>=.999,(scale,language)
                app._canvas.xview_moveto(0)
            assert int(ttk.Style(root).lookup('Treeview','rowheight'))>=round(23*scale)-1
            cases+=1
        app._finish_close()
        del app,root
        gc.collect()
print(json.dumps({'scale_language_cases':cases}))
'''
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=source,
                                env=dict(os.environ, PYTHONPATH=str(source)),
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('"scale_language_cases": 136', result.stdout)

    def test_original_fonts_paint_in_all_languages_using_source_entry_runtime(self):
        source = Path(__file__).resolve().parents[1]
        code = r'''
import gc, json, tempfile
from pathlib import Path
from concurrent.futures import Future
from types import SimpleNamespace
from sumuww.app import SumuwwApp, _font_family
from sumuww.i18n import LANGUAGE_CODES
from sumuww.profiles import REGTEST
import tkinter as tk
from tkinter import ttk
errors=[]
with tempfile.TemporaryDirectory(prefix='sumuww-original-fonts-') as folder:
    root=tk.Tk()
    root.report_callback_exception=lambda *args:errors.append(str(args))
    service=SimpleNamespace(directory=Path(folder),network=REGTEST,
                            start=lambda:Future(),status=lambda:Future())
    app=SumuwwApp(root,service,language='en',language_path=Path(folder)/'language.json')
    app._started=True
    style=ttk.Style(root)
    for language in LANGUAGE_CODES:
        app.set_language(language)
        root.update()
        requested=root.tk.splitlist(style.lookup('CardTitle.TLabel','font'))
        assert requested==(_font_family(language),'14' if language=='ar' else '11','bold'),(language,requested)
        assert app.translator.language==language
        assert root.winfo_exists()
        assert not errors,(language,errors)
    app._finish_close()
    assert not errors,errors
    del app,root
    gc.collect()
print(json.dumps({'languages':len(LANGUAGE_CODES),'painted':True,'original_styles':True}))
'''
        env = dict(os.environ, PYTHONPATH=str(source))
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=source,
                                env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('"languages": 34', result.stdout)
        self.assertIn('"original_styles": true', result.stdout)
