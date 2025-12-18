import os
import ctypes
import sys
import tkinter as tk

# --- Base64 图标库 ---
ICONS = {
    'clean': b'R0lGODlhEAAQAJEAAP///wAAAP///wAAACH5BAEAAAIALAAAAAAQABAAAAIqlI+py+0Po5x00osBTfD2jXHg93Ei+aCmmqKcy7LzC8N0JEN7v/v+QAQAOw==',
    'box': b'R0lGODlhEAAQAJEAAP///wAAAP///wAAACH5BAEAAAIALAAAAAAQABAAAAIolI+py+0PxhQ0Wnhd1Z3y7g1C95GZaJqmOK5uK88TQtO2HeM41/dBAQA7',
    'search': b'R0lGODlhEAAQAJEAAP///wAAAP///wAAACH5BAEAAAIALAAAAAAQABAAAAInlI+py+0PjApQsGmv1XD7D3ZiaJbm6aFqymrt8sLwPN90nQ98rwAAOw==',
    'sys': b'R0lGODlhEAAQAJEAAP///wAAAP///////yH5BAEAAAIALAAAAAAQABAAAAIplI+py+0PopwxUbpuZRfQqGwYMDQeMAxs6z4wLCON8j1vW9vn/P9DAgA7', 
    'app': b'R0lGODlhEAAQAJEAAP///wAAAP///////yH5BAEAAAIALAAAAAAQABAAAAIolI+py+0PowR0TgrhzTbx7m2Y95GZaPp4GpqmFp3nSlr1rM965/9DCAA7', 
    'bin': b'R0lGODlhEAAQAJEAAP///wAAAP///////yH5BAEAAAIALAAAAAAQABAAAAIqlI+py+0Po5x00osBTfD2jXHg93Ei+aCmmqKcy7LzC8N0JEN7v/v+QAQAOw==',
    'chat': b'R0lGODlhEAAQAJEAAP///wAAAP///////yH5BAEAAAIALAAAAAAQABAAAAIolI+py+0Po5x00osBTfD2jXHg93Ei+aCmmqKcy7LzC8N0JEN7v/v+QAQAOw==',
    'folder': b'R0lGODlhEAAQAJEAAP///wAAAP///wAAACH5BAEAAAIALAAAAAAQABAAAAIolI+py+0Po5x00osBTfD2jXHg93Ei+aCmmqKcy7LzC8N0JEN7v/v+QAQAOw=='
}

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def get_icons():
    return {k: tk.PhotoImage(data=v) for k, v in ICONS.items()}
