"""Language-specific brand artwork; all other locales use the original mark."""
from pathlib import Path
import sys
import tkinter as tk


def artwork(language, kind='logo', assets=None, scale=1.0):
    assets = Path(assets) if assets is not None else Path(__file__).resolve().parent.parent / 'assets'
    if language in ('ko', 'ar'):
        names = {'logo': f'{language}-logo.png', 'window': f'{language}-window.png', 'ico': f'{language}.ico'}
        if kind == 'logo':
            percent = max(100, min(300, round(float(scale) * 4) * 25))
            scaled = assets / 'brand' / f'{language}-logo-{percent}.png'
            if scaled.is_file():
                return scaled
        path = assets / 'brand' / names[kind]
        if path.is_file():
            return path
    return assets / {'logo': 'sumuww_ui_logo.png', 'window': 'sumuww_window_icon.png', 'ico': 'sumuww.ico'}[kind]


def apply_window_icon(root, language):
    """Refresh the title bar and taskbar while retaining Tk's image reference."""
    try:
        path = artwork(language, 'ico')
        if sys.platform == 'win32' and path.is_file():
            # Tk's iconbitmap allocates unreleased native resources on each
            # update. Own the native icon handles and release replaced ones.
            from .windows_icon import install_taskbar_icon
            install_taskbar_icon(root, path)
            return
        icon = tk.PhotoImage(master=root, file=str(artwork(language, 'window')))
        root.iconphoto(True, icon)
        root._sumuww_language_icon = icon
    except (OSError, tk.TclError):
        pass
