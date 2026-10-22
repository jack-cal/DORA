"""Capture only the test-owned native window, never the user's desktop."""
import ctypes as c
from ctypes import wintypes as w
from PIL import Image

class Header(c.Structure):
    _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),('bits',w.WORD),('compression',w.DWORD),('image_size',w.DWORD),('xppm',w.LONG),('yppm',w.LONG),('used',w.DWORD),('important',w.DWORD)]

def capture(root,destination):
    user=c.WinDLL('user32',use_last_error=True);gdi=c.WinDLL('gdi32',use_last_error=True)
    user.GetDC.argtypes=[w.HWND];user.GetDC.restype=w.HDC
    user.ReleaseDC.argtypes=[w.HWND,w.HDC]
    user.PrintWindow.argtypes=[w.HWND,w.HDC,w.UINT];user.PrintWindow.restype=w.BOOL
    gdi.CreateCompatibleDC.argtypes=[w.HDC];gdi.CreateCompatibleDC.restype=w.HDC
    gdi.CreateDIBSection.argtypes=[w.HDC,c.POINTER(Header),w.UINT,c.POINTER(c.c_void_p),w.HANDLE,w.DWORD];gdi.CreateDIBSection.restype=w.HBITMAP
    gdi.SelectObject.argtypes=[w.HDC,w.HANDLE];gdi.SelectObject.restype=w.HANDLE
    gdi.DeleteObject.argtypes=[w.HANDLE];gdi.DeleteDC.argtypes=[w.HDC]
    width,height=root.winfo_width(),root.winfo_height();hwnd=root.winfo_id()
    dc=user.GetDC(hwnd);mem=gdi.CreateCompatibleDC(dc);bits=c.c_void_p()
    header=Header(c.sizeof(Header),width,-height,1,32,0,width*height*4,0,0,0,0)
    bitmap=gdi.CreateDIBSection(dc,c.byref(header),0,c.byref(bits),None,0);old=gdi.SelectObject(mem,bitmap)
    try:
        if not user.PrintWindow(hwnd,mem,3):raise RuntimeError('Owned-window rendering failed')
        raw=c.string_at(bits,width*height*4);Image.frombytes('RGB',(width,height),raw,'raw','BGRX').save(destination)
    finally:
        gdi.SelectObject(mem,old);gdi.DeleteObject(bitmap);gdi.DeleteDC(mem);user.ReleaseDC(hwnd,dc)
