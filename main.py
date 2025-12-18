import tkinter as tk
import ctypes
import os
from gui import CleanerGUI

def main():
    root = tk.Tk()
    
    # 高 DPI 适配
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    
    # 设置窗口图标
    icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
    if os.path.exists(icon_path):
        try:
            root.iconbitmap(icon_path)
        except:
            pass
        
    app = CleanerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
