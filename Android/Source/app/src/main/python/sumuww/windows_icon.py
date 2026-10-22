"""Select native-size taskbar icons without changing the official artwork."""
import ctypes
from ctypes import wintypes
import sys


def install_taskbar_icon(root, path):
    if sys.platform != 'win32':
        return
    root._sumuww_native_icon_path = path
    if not getattr(root, '_sumuww_native_icon_map_bound', False):
        # A withdrawn Tk window may not yet have its outer Windows wrapper.
        # Install on that wrapper once it is mapped; the identity check below
        # makes subsequent Map events reuse the existing handles.
        def mapped(event):
            if event.widget is root:
                install_taskbar_icon(root, root._sumuww_native_icon_path)
        root.bind('<Map>', mapped, add='+')
        root._sumuww_native_icon_map_bound = True
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = wintypes.LPARAM
    user32.DestroyIcon.argtypes = [wintypes.HANDLE]
    hwnd = user32.GetAncestor(root.winfo_id(), 2) or root.winfo_id()
    dpi = 96
    if hasattr(user32, 'GetDpiForWindow'):
        user32.GetDpiForWindow.argtypes = [wintypes.HWND]
        user32.GetDpiForWindow.restype = wintypes.UINT
        dpi = user32.GetDpiForWindow(hwnd) or 96
    # DPI-unaware Tk windows report 96 even on a scaled monitor. Read the
    # monitor's physical scale without changing the wallet UI's DPI behaviour.
    try:
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        shcore = ctypes.WinDLL('shcore')
        shcore.GetScaleFactorForMonitor.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_int)]
        scale = ctypes.c_int()
        if shcore.GetScaleFactorForMonitor(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(scale)) == 0:
            dpi = max(dpi, round(96 * scale.value / 100))
    except (OSError, AttributeError):
        pass
    sizes = []
    for metric in (11, 49):  # SM_CXICON / SM_CXSMICON.
        if hasattr(user32, 'GetSystemMetricsForDpi'):
            user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, wintypes.UINT]
            size = user32.GetSystemMetricsForDpi(metric, dpi)
        else:
            size = user32.GetSystemMetrics(metric)
        sizes.append(size)
    identity = (str(path.resolve()), hwnd, tuple(sizes))
    if getattr(root, '_sumuww_native_icon_identity', None) == identity:
        return
    previous = getattr(root, '_sumuww_native_icon_handles', [])
    previous_identity = getattr(root, '_sumuww_native_icon_identity', None)
    handles = []
    for slot, size in zip((1, 0), sizes):
        handle = user32.LoadImageW(None, str(path), 1, size, size, 0x10)
        if handle:
            handles.append(handle)
    if len(handles) != 2:
        for handle in handles:
            user32.DestroyIcon(handle)
        return
    for slot, handle in zip((1, 0), handles):
        user32.SendMessageW(hwnd, 0x80, slot, handle)  # WM_SETICON.
    root._sumuww_native_icon_handles = handles
    root._sumuww_native_icon_identity = identity
    if previous_identity is not None and previous_identity[1] != hwnd:
        for slot in (1, 0):
            user32.SendMessageW(previous_identity[1], 0x80, slot, 0)
    for handle in previous:
        user32.DestroyIcon(handle)
    if not getattr(root, '_sumuww_native_icon_cleanup', False):
        def release(event):
            if event.widget is root:
                for handle in getattr(root, '_sumuww_native_icon_handles', []):
                    user32.DestroyIcon(handle)
                root._sumuww_native_icon_handles = []
        root.bind('<Destroy>', release, add='+')
        root._sumuww_native_icon_cleanup = True
    root._sumuww_taskbar_icon_sizes = tuple(sizes)
