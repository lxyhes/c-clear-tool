import os
import shutil
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
import subprocess
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
import time
from datetime import datetime

class SystemCleaner:
    def __init__(self):
        self.user_profile = os.environ['USERPROFILE']
        self.local_appdata = os.environ['LOCALAPPDATA']
        self.roaming_appdata = os.environ['APPDATA']
        self.temp = os.environ['TEMP']
        self.system_root = os.environ['SystemRoot']
        self.downloads = os.path.join(self.user_profile, "Downloads")
        
        # 基础清理项 (带分类标签)
        self.base_targets = [
            {"name": "用户临时文件", "path": self.temp, "cat": "系统垃圾"},
            {"name": "系统临时文件", "path": os.path.join(self.system_root, "Temp"), "cat": "系统垃圾"},
            {"name": "预读取文件 (Prefetch)", "path": os.path.join(self.system_root, "Prefetch"), "cat": "系统垃圾"},
            {"name": "Windows 更新缓存", "path": os.path.join(self.system_root, "SoftwareDistribution", "Download"), "cat": "系统垃圾"},
            {"name": "错误报告", "path": os.path.join(self.local_appdata, "Microsoft", "Windows", "WER"), "cat": "系统日志"},
        ]

        self.safe_keywords = ['cache', 'temp', 'log', 'logs', 'dump', 'crashes', 'crashpad', 'shadercache']
        self.danger_keywords = ['profile', 'save', 'saved', 'backup', 'database', 'user data', 'config']
        
        # 软件映射 & 分类推断
        self.app_mapping = {
            'google': ('谷歌 (Google)', '浏览器缓存'),
            'edge': ('Edge 浏览器', '浏览器缓存'),
            'microsoft': ('微软 (Microsoft)', '应用缓存'), 
            'mozilla': ('Firefox', '浏览器缓存'),
            'brave': ('Brave', '浏览器缓存'),
            'opera': ('Opera', '浏览器缓存'),
            'tencent': ('腾讯 (Tencent)', '社交通讯'),
            'wechat': ('微信 (WeChat)', '社交通讯'),
            'qq': ('QQ', '社交通讯'),
            'dingtalk': ('钉钉', '办公软件'),
            'feishu': ('飞书', '办公软件'),
            'lark': ('飞书', '办公软件'),
            'adobe': ('Adobe', '设计工具'),
            'autodesk': ('Autodesk', '设计工具'),
            'blender': ('Blender', '设计工具'),
            'steam': ('Steam', '游戏平台'),
            'epic': ('Epic Games', '游戏平台'),
            'vscode': ('VS Code', '开发工具'),
            'jetbrains': ('JetBrains', '开发工具'),
            'python': ('Python', '开发工具'),
            'pip': ('Pip Cache', '开发工具'),
            'nvidia': ('NVIDIA', '驱动缓存'),
            'amd': ('AMD', '驱动缓存'),
        }

    def infer_category(self, name, dir_path):
        """推断分类"""
        name_lower = name.lower()
        path_lower = dir_path.lower()
        
        # 1. 优先查表
        if name_lower in self.app_mapping:
            return self.app_mapping[name_lower] # 返回 (ReadableName, Category)
            
        # 2. 关键词推断
        if 'log' in path_lower or 'dump' in path_lower or 'crash' in path_lower:
            return (name, "日志与报错")
        
        # 3. 默认
        # 尝试查找是否包含映射表中的键
        for key, (readable, cat) in self.app_mapping.items():
            if key in name_lower:
                return (f"[{readable}] {name}", cat)
                
        return (name, "应用缓存")

    def get_dir_size_fast(self, path):
        total = 0
        try:
            stack = [path]
            while stack:
                current = stack.pop()
                try:
                    with os.scandir(current) as it:
                        for entry in it:
                            try:
                                if entry.is_file(follow_symlinks=False):
                                    total += entry.stat().st_size
                                elif entry.is_dir(follow_symlinks=False):
                                    stack.append(entry.path)
                            except: pass
                except: pass
        except: pass
        return total

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"

    def scan_generator(self):
        """生成器：产生每一个发现的垃圾项"""
        # 1. 扫描基础项
        for item in self.base_targets:
            if os.path.exists(item['path']):
                size = self.get_dir_size_fast(item['path'])
                if size > 0:
                    yield {
                        "category": item['cat'],
                        "name": item['name'],
                        "path": item['path'],
                        "raw_size": size,
                        "display_size": self.format_size(size)
                    }

        # 2. 扫描 AppData
        roots = [self.local_appdata, self.roaming_appdata]
        
        def process_appdata_root(root):
            local_results = []
            if not os.path.exists(root): return local_results
            try:
                with os.scandir(root) as it:
                    for entry in it:
                        if not entry.is_dir(): continue
                        
                        try:
                            # 快速遍历该软件目录寻找垃圾
                            for dirpath, dirnames, filenames in os.walk(entry.path):
                                # 深度限制
                                if dirpath.count(os.sep) - entry.path.count(os.sep) > 3:
                                    dirnames[:] = []
                                    continue
                                
                                current_dirname = os.path.basename(dirpath).lower()
                                is_junk = any(k in current_dirname for k in self.safe_keywords)
                                is_danger = any(k in current_dirname for k in self.danger_keywords)

                                if is_junk and not is_danger:
                                    # 推断分类和名称
                                    readable_info = self.infer_category(entry.name, dirpath)
                                    if isinstance(readable_info, tuple):
                                        readable_name, category = readable_info
                                    else:
                                        readable_name, category = readable_info, "应用缓存"
                                        
                                    junk_type = os.path.basename(dirpath)
                                    
                                    size = self.get_dir_size_fast(dirpath)
                                    if size > 0:
                                        local_results.append({
                                            "category": category,
                                            "name": f"{readable_name} ({junk_type})",
                                            "path": dirpath,
                                            "raw_size": size,
                                            "display_size": self.format_size(size)
                                        })
                                    dirnames[:] = []
                        except: pass
            except: pass
            return local_results

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_appdata_root, r) for r in roots]
            for future in futures:
                for res in future.result():
                    yield res

    def scan_installers(self):
        """扫描过期安装包"""
        if not os.path.exists(self.downloads): return
        
        extensions = {'.exe', '.msi', '.iso', '.zip', '.rar', '.7z'}
        now = time.time()
        limit_days = 30 * 24 * 3600 # 30天
        
        try:
            with os.scandir(self.downloads) as it:
                for entry in it:
                    if entry.is_file() and os.path.splitext(entry.name)[1].lower() in extensions:
                        try:
                            stat = entry.stat()
                            mtime = stat.st_mtime
                            size = stat.st_size
                            
                            # 如果修改时间超过30天
                            if now - mtime > limit_days:
                                dt_object = datetime.fromtimestamp(mtime)
                                date_str = dt_object.strftime("%Y-%m-%d")
                                
                                yield {
                                    "name": entry.name,
                                    "path": entry.path,
                                    "raw_size": size,
                                    "date": date_str,
                                    "display_size": self.format_size(size)
                                }
                        except: pass
        except: pass

    def scan_large_files(self):
        target_dirs = [
            os.path.join(self.user_profile, "Downloads"),
            os.path.join(self.user_profile, "Desktop"),
            os.path.join(self.user_profile, "Documents"),
            os.path.join(self.user_profile, "Videos"),
            os.path.join(self.user_profile, "Pictures"),
        ]
        limit_size = 100 * 1024 * 1024 # 100MB
        for root_dir in target_dirs:
            if not os.path.exists(root_dir): continue
            try:
                for dirpath, dirnames, filenames in os.walk(root_dir):
                    if os.path.basename(dirpath).startswith('.'):
                        dirnames[:] = []
                        continue
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        try:
                            size = os.path.getsize(fp)
                            if size > limit_size:
                                yield {
                                    "name": f,
                                    "path": fp,
                                    "raw_size": size,
                                    "display_size": self.format_size(size)
                                }
                        except: pass
            except: pass

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

class CleanerGUI:
    def __init__(self, root):
        self.root = root
        self.cleaner = SystemCleaner()
        
        # 结果缓存
        self.junk_items = {} # Map iid -> item data
        self.total_junk_size = 0
        self.categories_created = set()
        
        self.queue = Queue()
        self.scanning = False
        
        self.setup_styles()
        self.setup_ui()
        
        if not self.is_admin():
            messagebox.showwarning("权限提示", "建议以【管理员身份】运行，否则系统临时文件无法清理。")

    def is_admin(self):
        try: return ctypes.windll.shell32.IsUserAnAdmin()
        except: return False

    def setup_styles(self):
        style = ttk.Style()
        if 'vista' in style.theme_names(): style.theme_use('vista')
        elif 'clam' in style.theme_names(): style.theme_use('clam')
        
        style.configure(".", font=("Microsoft YaHei", 9))
        style.configure("Treeview", rowheight=26)
        style.configure("Treeview.Heading", font=("Microsoft YaHei", 9, "bold"))

    def setup_ui(self):
        self.root.title("C盘深度清理助手 (v4.0 分类增强版)")
        self.root.geometry("1000x750")
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: 智能清理 (分类)
        self.tab_junk = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_junk, text=" 🧹 智能清理 ")
        self.setup_junk_ui(self.tab_junk)

        # Tab 2: 📦 旧安装包
        self.tab_installer = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_installer, text=" 📦 旧安装包 ")
        self.setup_installer_ui(self.tab_installer)
        
        # Tab 3: 大文件
        self.tab_large = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_large, text=" 🐘 大文件查找 ")
        self.setup_large_ui(self.tab_large)
        
        # 状态栏
        self.status_var = tk.StringVar(value="准备就绪")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)
        self.progress = ttk.Progressbar(self.root, mode='indeterminate')
        self.progress.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_junk_ui(self, parent):
        top_frame = ttk.Frame(parent, padding=10)
        top_frame.pack(fill=tk.X)
        
        ttk.Button(top_frame, text="⚡ 扫描垃圾", command=self.start_scan_junk).pack(side=tk.LEFT, padx=5)
        self.btn_clean_junk = ttk.Button(top_frame, text="🗑️ 清理选中", command=self.clean_junk, state=tk.DISABLED)
        self.btn_clean_junk.pack(side=tk.LEFT, padx=5)
        ttk.Label(top_frame, text="支持双击分类折叠/展开", foreground="gray").pack(side=tk.LEFT, padx=10)
        
        self.lbl_junk_stats = ttk.Label(top_frame, text="", foreground="#2e7d32")
        self.lbl_junk_stats.pack(side=tk.RIGHT)

        tree_frame = ttk.Frame(parent, padding=5)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree_junk = ttk.Treeview(tree_frame, columns=("path", "size", "status"), selectmode="extended")
        self.tree_junk.heading("#0", text="分类 / 名称", anchor="w")
        self.tree_junk.heading("path", text="路径", anchor="w")
        self.tree_junk.heading("size", text="大小", anchor="e")
        self.tree_junk.heading("status", text="状态", anchor="c")
        
        self.tree_junk.column("#0", width=300)
        self.tree_junk.column("path", width=400)
        self.tree_junk.column("size", width=100, anchor="e")
        self.tree_junk.column("status", width=80, anchor="c")
        
        scrolly = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_junk.yview)
        self.tree_junk.configure(yscroll=scrolly.set)
        self.tree_junk.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree_junk.bind("<Button-3>", lambda e: self.show_context_menu(e, self.tree_junk))

    def setup_installer_ui(self, parent):
        top_frame = ttk.Frame(parent, padding=10)
        top_frame.pack(fill=tk.X)
        
        ttk.Button(top_frame, text="🔍 扫描 Download 文件夹", command=self.start_scan_installers).pack(side=tk.LEFT)
        ttk.Label(top_frame, text="筛选：超过 30 天未使用的 .exe/.msi/.zip", foreground="gray").pack(side=tk.LEFT, padx=10)
        
        self.tree_inst = ttk.Treeview(parent, columns=("date", "path", "size"), show="headings", selectmode="extended")
        self.tree_inst.heading("date", text="修改日期")
        self.tree_inst.heading("path", text="文件路径")
        self.tree_inst.heading("size", text="大小")
        self.tree_inst.column("date", width=120)
        self.tree_inst.column("path", width=500)
        self.tree_inst.column("size", width=100, anchor="e")
        self.tree_inst.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.tree_inst.bind("<Button-3>", lambda e: self.show_context_menu(e, self.tree_inst))

    def setup_large_ui(self, parent):
        top_frame = ttk.Frame(parent, padding=10)
        top_frame.pack(fill=tk.X)
        ttk.Button(top_frame, text="🔍 查找 >100MB 文件", command=self.start_scan_large).pack(side=tk.LEFT)
        
        self.tree_large = ttk.Treeview(parent, columns=("path", "size"), show="headings", selectmode="extended")
        self.tree_large.heading("path", text="文件路径")
        self.tree_large.heading("size", text="大小")
        self.tree_large.column("path", width=600)
        self.tree_large.column("size", width=100, anchor="e")
        self.tree_large.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
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
        # Treeview hierarchy items don't have paths in values usually, need check
        values = item.get('values', [])
        path = ""
        # Check different tree structures
        if tree == self.tree_junk:
            # child nodes have path in col 0 (which is values[0] if show="tree headings"?) 
            # Actually col indices: path=0, size=1, status=2
            if values: path = values[0]
        elif tree == self.tree_inst:
            if len(values) > 1: path = values[1]
        elif tree == self.tree_large:
            if len(values) > 0: path = values[0]
            
        if path and os.path.exists(path):
            if os.path.isfile(path):
                subprocess.run(['explorer', '/select,', os.path.normpath(path)])
            else:
                os.startfile(path)

    # --- Junk Scan ---
    def start_scan_junk(self):
        if self.scanning: return
        self.scanning = True
        self.tree_junk.delete(*self.tree_junk.get_children())
        self.junk_items.clear()
        self.categories_created.clear()
        self.total_junk_size = 0
        self.btn_clean_junk.config(state=tk.DISABLED)
        self.progress.start(10)
        self.status_var.set("正在分析系统与软件垃圾...")
        
        threading.Thread(target=self.thread_scan_junk, daemon=True).start()
        self.root.after(50, self.consume_scan_queue)

    def thread_scan_junk(self):
        for item in self.cleaner.scan_generator():
            self.queue.put(("junk_item", item))
        self.queue.put(("done", None))

    def consume_scan_queue(self):
        try:
            for _ in range(30):
                msg_type, data = self.queue.get_nowait()
                if msg_type == "junk_item":
                    cat = data['category']
                    # Ensure Category Node Exists
                    if cat not in self.categories_created:
                        self.tree_junk.insert("", tk.END, iid=cat, text=cat, open=True)
                        self.categories_created.add(cat)
                    
                    # Insert Item under Category
                    item_id = self.tree_junk.insert(cat, tk.END, text=data['name'], values=(
                        data['path'], data['display_size'], "待清理"
                    ))
                    self.junk_items[item_id] = data
                    self.total_junk_size += data['raw_size']
                    
                elif msg_type == "done":
                    self.scanning = False
                    self.progress.stop()
                    self.status_var.set("扫描完成")
                    self.lbl_junk_stats.config(text=f"总计可释放: {self.cleaner.format_size(self.total_junk_size)}")
                    self.btn_clean_junk.config(state=tk.NORMAL)
                    return
        except Empty: pass
        
        if self.scanning:
            self.root.after(50, self.consume_scan_queue)

    def clean_junk(self):
        # Recursive selection finding
        selected_iids = []
        for sel in self.tree_junk.selection():
            # If it's a category, clean all children? 
            # Simpler: user must select items. Or if category selected, get children.
            if sel in self.categories_created:
                selected_iids.extend(self.tree_junk.get_children(sel))
            else:
                selected_iids.append(sel)
        
        # Deduplicate
        selected_iids = list(set(selected_iids))
        if not selected_iids: return
        
        if not messagebox.askyesno("确认", f"清理选中的 {len(selected_iids)} 个项目？"): return
        
        self.progress.start(10)
        self.btn_clean_junk.config(state=tk.DISABLED)
        threading.Thread(target=self.thread_clean, args=(selected_iids,), daemon=True).start()
        self.root.after(50, self.consume_clean_queue)

    def thread_clean(self, iids):
        cleaned_size = 0
        for iid in iids:
            if iid not in self.junk_items: continue
            item = self.junk_items[iid]
            self.queue.put(("status", (iid, "清理中...")))
            size, errors = self.cleaner.delete_item(item['path'])
            cleaned_size += size
            self.queue.put(("status", (iid, "完成" if not errors else "跳过占用")))
        self.queue.put(("clean_done", cleaned_size))

    def consume_clean_queue(self):
        try:
            while True:
                msg, data = self.queue.get_nowait()
                if msg == "status":
                    self.tree_junk.set(data[0], "status", data[1])
                elif msg == "clean_done":
                    self.progress.stop()
                    messagebox.showinfo("完成", f"释放空间: {self.cleaner.format_size(data)}")
                    self.btn_clean_junk.config(state=tk.NORMAL)
                    return
        except Empty: pass
        self.root.after(50, self.consume_clean_queue)

    # --- Installers & Large Files (Simplified for brevity) ---
    def start_scan_installers(self):
        self.tree_inst.delete(*self.tree_inst.get_children())
        threading.Thread(target=self.thread_scan_inst, daemon=True).start()

    def thread_scan_inst(self):
        for item in self.cleaner.scan_installers():
            self.tree_inst.insert("", tk.END, values=(item['date'], item['path'], item['display_size']))

    def start_scan_large(self):
        self.tree_large.delete(*self.tree_large.get_children())
        threading.Thread(target=self.thread_scan_large, daemon=True).start()

    def thread_scan_large(self):
        results = sorted(list(self.cleaner.scan_large_files()), key=lambda x: x['raw_size'], reverse=True)
        for item in results:
            self.tree_large.insert("", tk.END, values=(item['path'], item['display_size']))

if __name__ == "__main__":
    root = tk.Tk()
    try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = CleanerGUI(root)
    root.mainloop()