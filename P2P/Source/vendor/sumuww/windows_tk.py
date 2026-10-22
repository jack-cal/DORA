"""Select the project's audited Tk runtime for standalone Windows source UI."""
from __future__ import annotations

import ctypes
import importlib.util
import os
from pathlib import Path
import sys

_runtime = None
_dpi_prepared = False


def prepare_dpi():
    """Use native screen resolution without changing the user's display settings.

    Tk 8.6 uses system DPI for widget metrics. System awareness avoids Windows
    bitmap-stretching the whole window while keeping Tk's metrics consistent.
    Frozen GUI executables declare the same mode in their manifest.
    """
    global _dpi_prepared
    if sys.platform != 'win32' or _dpi_prepared:
        return
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.SetProcessDPIAware.argtypes = []
    user32.SetProcessDPIAware.restype = ctypes.c_int
    # A manifest or an embedding host may already have selected DPI awareness.
    # In that case Windows rejects a later change and preserves the set mode.
    user32.SetProcessDPIAware()
    _dpi_prepared = True


def prepare_tk():
    """Load before tkinter; frozen builds already carry this same native DLL."""
    global _runtime
    prepare_dpi()
    if _runtime is not None or sys.platform != 'win32' or getattr(sys, 'frozen', False) or '_tkinter' in sys.modules:
        return
    directory = Path(__file__).resolve().parent.parent / 'vendor' / 'tk-font-quality'
    binary, library = directory / 'tk86t.dll', directory / 'tk8.6'
    if not binary.is_file() or not (library / 'tk.tcl').is_file():
        return  # Source trees without Windows binaries use their installed Tk.
    spec = importlib.util.find_spec('_tkinter')
    if spec is None or spec.origin is None:
        return
    # Tk 9 and nonstandard Python builds must use their matching native ABI.
    with Path(spec.origin).open('rb') as stream:
        imports = stream.read(2 * 1024 * 1024).lower()
    if b'tk86t.dll' not in imports:
        return
    _runtime = ctypes.WinDLL(str(binary))
    os.environ['TK_LIBRARY'] = str(library)
