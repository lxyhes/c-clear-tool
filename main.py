import tkinter as tk
import ctypes
import os
import sys
import logging
from datetime import datetime
from gui import CleanerGUI

# 设置日志
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'ccleaner_{datetime.now().strftime("%Y%m%d")}.log')

# 配置日志同时输出到文件和控制台
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('CCleaner')

def main():
    logger.info("=" * 60)
    logger.info("C-Cleaner Starting...")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 60)
    
    try:
        root = tk.Tk()
        
        # 高 DPI 适配
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            logger.info("DPI awareness set")
        except Exception as e:
            logger.warning(f"DPI setup failed: {e}")
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
        if os.path.exists(icon_path):
            try:
                root.iconbitmap(icon_path)
                logger.info(f"Icon loaded: {icon_path}")
            except Exception as e:
                logger.warning(f"Icon load failed: {e}")
        
        logger.info("Initializing GUI...")
        app = CleanerGUI(root)
        logger.info("GUI initialized, entering main loop")
        root.mainloop()
        
    except Exception as e:
        logger.exception("Fatal error in main")
        raise
    finally:
        logger.info("=" * 60)
        logger.info("C-Cleaner Stopped")
        logger.info("=" * 60)

if __name__ == "__main__":
    main()
