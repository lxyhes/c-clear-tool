import tkinter as tk
import ctypes
from gui import CleanerGUI

def main():
    root = tk.Tk()
    
    # 高 DPI 适配
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
        
    app = CleanerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
