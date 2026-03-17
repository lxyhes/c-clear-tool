#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开发模式启动器 - 支持热加载
监视文件变化，自动重启程序
"""

import sys
import os
import time
import subprocess
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("[WARNING] watchdog not installed. Auto-reload disabled.")
    print("Install with: pip install watchdog")

class CodeChangeHandler(FileSystemEventHandler):
    """监视代码变化并重启"""
    
    def __init__(self, restart_callback):
        self.restart_callback = restart_callback
        self.last_restart = 0
        self.ignore_paths = ['logs', '__pycache__', '.git']
        
    def should_ignore(self, path):
        """检查是否应该忽略此路径"""
        path_lower = path.lower()
        for ignore in self.ignore_paths:
            if ignore in path_lower:
                return True
        return False
        
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # 忽略日志目录等
        if self.should_ignore(event.src_path):
            return
        
        # 只监视Python文件
        if event.src_path.endswith('.py'):
            # 防抖，防止短时间内多次重启
            current_time = time.time()
            if current_time - self.last_restart < 2:
                return
            
            self.last_restart = current_time
            print(f"\n[RELOAD] Detected change: {os.path.basename(event.src_path)}")
            print("[RELOAD] Restarting application...\n")
            self.restart_callback()

class ApplicationRunner:
    """运行应用程序并支持重载"""
    
    def __init__(self):
        self.process = None
        self.observer = None
        
    def start_app(self):
        """启动应用程序"""
        print("[RUNNER] Starting main.py...")
        
        # 启动主程序
        self.process = subprocess.Popen(
            [sys.executable, '-u', 'main.py'],
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
    def stop_app(self):
        """停止应用程序"""
        if self.process:
            print("[RUNNER] Stopping application...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            self.process = None
            
    def restart_app(self):
        """重启应用程序"""
        self.stop_app()
        time.sleep(1)  # 等待资源释放
        self.start_app()
        
    def start_watching(self):
        """开始监视文件变化"""
        if not WATCHDOG_AVAILABLE:
            print("[RUNNER] File watching not available")
            return
            
        print("[RUNNER] Starting file watcher...")
        
        handler = CodeChangeHandler(self.restart_app)
        self.observer = Observer()
        
        # 监视当前目录的Python文件
        watch_path = os.path.dirname(os.path.abspath(__file__))
        self.observer.schedule(handler, watch_path, recursive=False)
        self.observer.start()
        
    def run(self):
        """主循环"""
        print("=" * 60)
        print("C-Cleaner Development Runner")
        print("=" * 60)
        print()
        print("Features:")
        print("  - Auto-reload on code changes")
        print("  - Console output visible")
        print("  - Press Ctrl+C to stop")
        print()
        print("=" * 60)
        print()
        
        # 启动应用程序
        self.start_app()
        
        # 开始监视文件
        self.start_watching()
        
        try:
            # 保持运行
            auto_restart_on_crash = False  # 是否崩溃自动重启
            while True:
                if self.process:
                    ret_code = self.process.poll()
                    if ret_code is not None:
                        # 程序退出
                        print(f"\n[RUNNER] Application exited with code: {ret_code}")
                        
                        # 正常退出 (code 0) 或用户关闭，不自动重启
                        if ret_code == 0:
                            print("[RUNNER] Normal exit, stopping watcher...")
                            break
                        
                        # 异常退出
                        if not auto_restart_on_crash:
                            print("[RUNNER] Abnormal exit. Press Enter to restart, Ctrl+C to stop...")
                            try:
                                input()
                                self.start_app()
                            except KeyboardInterrupt:
                                break
                        else:
                            print("[RUNNER] Auto-restarting in 2 seconds...")
                            time.sleep(2)
                            self.start_app()
                            
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[RUNNER] Stopping...")
        finally:
            self.stop_app()
            if self.observer:
                self.observer.stop()
                self.observer.join()

if __name__ == '__main__':
    runner = ApplicationRunner()
    runner.run()
