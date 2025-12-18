import os
import ctypes
import sys

# --- 现代彩色 3D 符号库 (利用系统原生渲染，高清不失真) ---
# 这些符号在 Windows 10/11 上会自动显示为精美的彩色 3D 图标
ICONS = {
    'clean': "🧹",
    'chat': "💬",
    'fire': "🔥",
    'folder': "📁",
    'box': "📦",
    'search': "🔎",
    'sys': "💻",
    'app': "🧩",
    'bin': "🗑️",
    'secure': "🛡️",
    'mail': "📧",
    'key': "🔑",
    'cmd': "⌨️"
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
    # 现在直接返回文字字符，性能更高，视觉更佳
    return ICONS
