import os
import shutil
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ctypes
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

class SystemCleaner:
    def __init__(self):
        self.user_profile = os.environ['USERPROFILE']
        self.local_appdata = os.environ['LOCALAPPDATA']
        self.roaming_appdata = os.environ['APPDATA']
        self.temp = os.environ['TEMP']
        self.system_root = os.environ['SystemRoot']
        
        # 基础清理项
        self.base_targets = [
            {"name": "[系统] 用户临时文件", "path": self.temp, "type": "dir", "safe": True},
            {"name": "[系统] 系统临时文件", "path": os.path.join(self.system_root, "Temp"), "type": "dir", "safe": True},
            {"name": "[系统] 预读取文件 (Prefetch)", "path": os.path.join(self.system_root, "Prefetch"), "type": "dir", "safe": True},
            {"name": "[系统] Windows 更新缓存", "path": os.path.join(self.system_root, "SoftwareDistribution", "Download"), "type": "dir", "safe": True},
            {"name": "[系统] 错误报告", "path": os.path.join(self.local_appdata, "Microsoft", "Windows", "WER"), "type": "dir", "safe": True},
        ]

        self.safe_keywords = ['cache', 'temp', 'log', 'logs', 'dump', 'crashes', 'crashpad', 'shadercache']
        self.danger_keywords = ['profile', 'save', 'saved', 'backup', 'database', 'user data', 'config']
        
        self.app_mapping = {
            'google': '谷歌 (Google)', 'microsoft': '微软 (Microsoft)', 'windows': 'Windows 系统',
            'tencent': '腾讯 (Tencent)', 'adobe': 'Adobe', 'discord': 'Discord',
            'wechat': '微信 (WeChat)', 'qq': 'QQ', 'dingtalk': '钉钉',
            'netease': '网易', 'cloudmusic': '网易云音乐', 'steam': 'Steam',
            'epic': 'Epic Games', 'origin': 'Origin', 'ubisoft': '育碧 (Ubisoft)',
            'vscode': 'VS Code', 'jetbrains': 'JetBrains', 'mozilla': 'Firefox',
            'spotify': 'Spotify', '360': '360安全卫士', 'wps': 'WPS Office',
            'baidu': '百度', 'nvidia': 'NVIDIA', 'amd': 'AMD', 'intel': 'Intel',
            'obs-studio': 'OBS 直播', 'autodesk': 'Autodesk', 'unity': 'Unity',
            'blender': 'Blender', 'docker': 'Docker', 'apple': 'Apple',
            'feishu': '飞书', 'lark': '飞书',
        }

    def get_readable_name(self, entry_name, dir_path):
        vendor_lower = entry_name.lower()
        mapped_vendor = self.app_mapping.get(vendor_lower)
        display_name = mapped_vendor if mapped_vendor else entry_name
        
        try:
            norm_path = os.path.normpath(dir_path)
            parts = norm_path.split(os.sep)
            if entry_name in parts:
                idx = parts.index(entry_name)
                if idx + 1 < len(parts):
                    sub_app = parts[idx + 1]
                    sub_app_lower = sub_app.lower()
                    is_keyword = any(k in sub_app_lower for k in self.safe_keywords)
                    if not is_keyword and sub_app_lower != entry_name.lower():
                        mapped_sub = self.app_mapping.get(sub_app_lower)
                        sub_display = mapped_sub if mapped_sub else sub_app
                        if mapped_vendor:
                            display_name = f"[{mapped_vendor}] {sub_display}"
                        else:
                            display_name = f"[{entry_name}] {sub_display}"
                        return display_name
        except:
            pass
        return f"[{display_name}]"

    def get_size(self, path):
        total_size = 0
        try:
            if os.path.isfile(path):
                return os.path.getsize(path)
            
            stack = [path]
            while stack:
                current_dir = stack.pop()
                try:
                    with os.scandir(current_dir) as it:
                        for entry in it:
                            try:
                                if entry.is_file(follow_symlinks=False):
                                    total_size += entry.stat().st_size
                                elif entry.is_dir(follow_symlinks=False):
                                    stack.append(entry.path)
                            except: pass
                except: pass
        except: pass
        return total_size

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"

    def scan_appdata_root(self, root):
        candidates = []
        if not os.path.exists(root): return candidates
        try:
            with os.scandir(root) as it:
                for entry in it:
                    if not entry.is_dir(): continue
                    try:
                        for dirpath, dirnames, filenames in os.walk(entry.path):
                            depth = dirpath.count(os.sep) - entry.path.count(os.sep)
                            if depth > 3: 
                                dirnames[:] = [] 
                                continue
                            
                            current_dirname = os.path.basename(dirpath).lower()
                            is_junk = any(k in current_dirname for k in self.safe_keywords)
                            is_danger = any(k in current_dirname for k in self.danger_keywords)

                            if is_junk and not is_danger:
                                readable_name = self.get_readable_name(entry.name, dirpath)
                                junk_type = os.path.basename(dirpath)
                                candidates.append({
                                    "name": f"{readable_name} - {junk_type}",
                                    "path": dirpath,
                                    "type": "dir",
                                    "safe": True
                                })
                                dirnames[:] = []
                    except: pass
        except: pass
        return candidates

    def scan_all_targets(self):
        results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_item = {executor.submit(self.get_size_and_info, item): item for item in self.base_targets}
            future_local = executor.submit(self.scan_appdata_root, self.local_appdata)
            future_roaming = executor.submit(self.scan_appdata_root, self.roaming_appdata)
            
            for future in future_to_item:
                res = future.result()
                if res: results.append(res)
            
            appdata_candidates = []
            if future_local.result(): appdata_candidates.extend(future_local.result())
            if future_roaming.result(): appdata_candidates.extend(future_roaming.result())
            
            future_to_candidate = {executor.submit(self.get_size_and_info, item): item for item in appdata_candidates}
            for future in future_to_candidate:
                res = future.result()
                if res and res['raw_size'] > 1024 * 1024:
                    results.append(res)
        return results

    def get_size_and_info(self, item):
        if os.path.exists(item['path']):
            size = self.get_size(item['path'])
            if size > 0:
                return {**item, "raw_size": size, "display_size": self.format_size(size)}
        return None

    def delete_item(self, path):
        deleted_size = 0
        errors = 0
        if not os.path.exists(path): return 0, 0
        try:
            if os.path.isfile(path):
                size = os.path.getsize(path)
                os.remove(path)
                return size, 0
            else:
                for root, dirs, files in os.walk(path, topdown=False):
                    for name in files:
                        try:
                            fp = os.path.join(root, name)
                            size = os.path.getsize(fp)
                            os.remove(fp)
                            deleted_size += size
                        except: errors += 1
                    for name in dirs:
                        try: os.rmdir(os.path.join(root, name))
                        except: pass
        except: errors += 1
        return deleted_size, errors

    def scan_large_files(self, callback):
        """扫描个人目录下的极大文件"""
        target_dirs = [
            os.path.join(self.user_profile, "Downloads"),
            os.path.join(self.user_profile, "Desktop"),
            os.path.join(self.user_profile, "Documents"),
            os.path.join(self.user_profile, "Videos"),
            os.path.join(self.user_profile, "Pictures"),
        ]
        
        large_files = []
        limit_size = 100 * 1024 * 1024 # 100MB
        
        for root_dir in target_dirs:
            if not os.path.exists(root_dir): continue
            
            try:
                for dirpath, dirnames, filenames in os.walk(root_dir):
                    # 跳过隐藏目录
                    if os.path.basename(dirpath).startswith('.'):
                        dirnames[:] = []
                        continue
                        
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        try:
                            size = os.path.getsize(fp)
                            if size > limit_size:
                                large_files.append({
                                    "name": f,
                                    "path": fp,
                                    "raw_size": size,
                                    "display_size": self.format_size(size)
                                })
                        except: pass
            except: pass
            
        large_files.sort(key=lambda x: x['raw_size'], reverse=True)
        return large_files[:50] # 只返回前50个

class CleanerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("C盘深度清理工具 (v2.0)")
        self.root.geometry("950x650")
        self.cleaner = SystemCleaner()
        self.scan_results = []
        self.large_files_results = []
        
        if not self.is_admin():
            messagebox.showwarning("权限警告", "建议以【管理员身份】运行此脚本，否则无法清理系统临时文件！")

        self.setup_ui()

    def is_admin(self):
        try: return ctypes.windll.shell32.IsUserAnAdmin()
        except: return False

    def setup_ui(self):
        # 使用 Notebook 实现选项卡
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # TAB 1: 垃圾清理
        self.tab_junk = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_junk, text=" 🗑️ 垃圾清理 ")
        self.setup_junk_ui(self.tab_junk)
        
        # TAB 2: 大文件查找
        self.tab_large = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_large, text=" 🐘 大文件查找 ")
        self.setup_large_ui(self.tab_large)
        
        # 底部状态栏
        self.status_var = tk.StringVar(value="准备就绪")
        self.lbl_status = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_status.pack(side=tk.BOTTOM, fill=tk.X)

        # 进度条
        self.progress = ttk.Progressbar(self.root, mode='indeterminate')
        self.progress.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)

    def setup_junk_ui(self, parent):
        top_frame = ttk.Frame(parent, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Button(top_frame, text="开始扫描垃圾", command=self.scan_junk).pack(side=tk.LEFT, padx=5)
        self.btn_clean = ttk.Button(top_frame, text="清理选中项", command=self.clean_junk, state=tk.DISABLED)
        self.btn_clean.pack(side=tk.LEFT, padx=5)
        
        list_frame = ttk.Frame(parent, padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("name", "path", "size", "status")
        self.tree_junk = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        
        self.tree_junk.heading("name", text="项目名称")
        self.tree_junk.heading("path", text="路径")
        self.tree_junk.heading("size", text="大小")
        self.tree_junk.heading("status", text="状态")
        
        self.tree_junk.column("name", width=250)
        self.tree_junk.column("path", width=400)
        self.tree_junk.column("size", width=100, anchor="e")
        self.tree_junk.column("status", width=100)
        
        scrolly = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree_junk.yview)
        self.tree_junk.configure(yscroll=scrolly.set)
        
        self.tree_junk.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定右键菜单
        self.tree_junk.bind("<Button-3>", lambda e: self.show_context_menu(e, self.tree_junk))

    def setup_large_ui(self, parent):
        top_frame = ttk.Frame(parent, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="扫描范围: 下载/桌面/文档/视频 (文件 > 100MB)").pack(side=tk.LEFT)
        ttk.Button(top_frame, text="开始查找大文件", command=self.scan_large).pack(side=tk.RIGHT, padx=5)
        
        list_frame = ttk.Frame(parent, padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("name", "path", "size")
        self.tree_large = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        
        self.tree_large.heading("name", text="文件名")
        self.tree_large.heading("path", text="完整路径")
        self.tree_large.heading("size", text="大小")
        
        self.tree_large.column("name", width=200)
        self.tree_large.column("path", width=500)
        self.tree_large.column("size", width=100, anchor="e")
        
        scrolly = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree_large.yview)
        self.tree_large.configure(yscroll=scrolly.set)
        
        self.tree_large.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定右键菜单
        self.tree_large.bind("<Button-3>", lambda e: self.show_context_menu(e, self.tree_large))

    def show_context_menu(self, event, tree):
        iid = tree.identify_row(event.y)
        if iid:
            tree.selection_set(iid)
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="📂 打开所在文件夹", command=lambda: self.open_folder(tree, iid))
            menu.post(event.x_root, event.y_root)

    def open_folder(self, tree, iid):
        item = tree.item(iid)
        path = item['values'][1] # Path is usually in column 1
        if os.path.exists(path):
            if os.path.isfile(path):
                # 选中文件
                subprocess.run(['explorer', '/select,', os.path.normpath(path)])
            else:
                # 打开文件夹
                os.startfile(path)
        else:
            messagebox.showerror("错误", "文件或目录不存在")

    # --- 垃圾清理逻辑 ---
    def scan_junk(self):
        self.tree_junk.delete(*self.tree_junk.get_children())
        self.progress.start(10)
        self.status_var.set("正在分析系统垃圾...")
        threading.Thread(target=self.thread_scan_junk, daemon=True).start()

    def thread_scan_junk(self):
        results = self.cleaner.scan_all_targets()
        total_size = sum(item['raw_size'] for item in results)
        results.sort(key=lambda x: x['raw_size'], reverse=True)
        self.root.after(0, self.finish_scan_junk, results, total_size)

    def finish_scan_junk(self, results, total_size):
        self.progress.stop()
        self.scan_results = results
        for idx, item in enumerate(results):
            self.tree_junk.insert("", tk.END, iid=idx, values=(
                item['name'], item['path'], item['display_size'], "待清理"
            ))
            self.tree_junk.selection_add(idx)
        
        self.status_var.set(f"扫描完成：发现 {len(results)} 个项目，共 {self.cleaner.format_size(total_size)}")
        self.btn_clean.config(state=tk.NORMAL)

    def clean_junk(self):
        selected = self.tree_junk.selection()
        if not selected: return
        if not messagebox.askyesno("确认", f"确定清理这 {len(selected)} 个项目吗？"): return
        
        self.progress.start(10)
        threading.Thread(target=self.thread_clean_junk, args=(selected,), daemon=True).start()

    def thread_clean_junk(self, selected_iids):
        total_cleaned = 0
        for iid in selected_iids:
            idx = int(iid)
            item = self.scan_results[idx]
            self.root.after(0, lambda i=iid: self.tree_junk.set(i, "status", "清理中..."))
            cleaned, errors = self.cleaner.delete_item(item['path'])
            total_cleaned += cleaned
            status = "完成" if errors == 0 else f"完成 (跳过{errors})"
            self.root.after(0, lambda i=iid, s=status: self.tree_junk.set(i, "status", s))
        
        self.root.after(0, self.finish_clean, total_cleaned)

    def finish_clean(self, total_cleaned):
        self.progress.stop()
        msg = f"清理结束！共释放: {self.cleaner.format_size(total_cleaned)}"
        self.status_var.set(msg)
        messagebox.showinfo("完成", msg)

    # --- 大文件逻辑 ---
    def scan_large(self):
        self.tree_large.delete(*self.tree_large.get_children())
        self.progress.start(10)
        self.status_var.set("正在搜索大文件 (Downloads, Desktop, Documents, Videos)...")
        threading.Thread(target=self.thread_scan_large, daemon=True).start()

    def thread_scan_large(self):
        results = self.cleaner.scan_large_files(None)
        self.root.after(0, self.finish_scan_large, results)

    def finish_scan_large(self, results):
        self.progress.stop()
        self.large_files_results = results
        for idx, item in enumerate(results):
            self.tree_large.insert("", tk.END, iid=idx, values=(
                item['name'], item['path'], item['display_size']
            ))
        
        self.status_var.set(f"搜索完成：找到 {len(results)} 个超过 100MB 的文件")

if __name__ == "__main__":
    root = tk.Tk()
    try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = CleanerGUI(root)
    root.mainloop()