import os
import sys
import shutil
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
import subprocess
import winreg
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
from datetime import datetime
import time

# --- Base64 图标库 (Win11 风格 - 适配浅色主题) ---
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

# --- 核心清理逻辑 ---
class SystemCleaner:
    def __init__(self):
        self.user_profile = os.environ['USERPROFILE']
        self.local_appdata = os.environ['LOCALAPPDATA']
        self.roaming_appdata = os.environ['APPDATA']
        self.temp = os.environ['TEMP']
        self.system_root = os.environ['SystemRoot']
        self.downloads = os.path.join(self.user_profile, "Downloads")
        
        self.base_targets = [
            {"name": "用户临时文件", "path": self.temp, "cat": "系统垃圾", "soft": "Windows"},
            {"name": "系统临时文件", "path": os.path.join(self.system_root, "Temp"), "cat": "系统垃圾", "soft": "Windows"},
            {"name": "预读取文件", "path": os.path.join(self.system_root, "Prefetch"), "cat": "系统垃圾", "soft": "Windows"},
            {"name": "系统更新缓存", "path": os.path.join(self.system_root, "SoftwareDistribution", "Download"), "cat": "系统垃圾", "soft": "Windows Update"},
            {"name": "错误报告", "path": os.path.join(self.local_appdata, "Microsoft", "Windows", "WER"), "cat": "系统垃圾", "soft": "Error Reporting"},
        ]
        self.safe_keywords = ['cache', 'temp', 'log', 'logs', 'dump', 'crashes', 'crashpad', 'shadercache']
        self.danger_keywords = ['profile', 'save', 'saved', 'backup', 'database', 'user data', 'config', 'cookies']
        self.app_mapping = {
            'google': ('浏览器缓存', 'Google Chrome'), 'chrome': ('浏览器缓存', 'Google Chrome'), 'edge': ('浏览器缓存', 'Edge'),
            'microsoft': ('应用缓存', 'Microsoft Apps'), 'mozilla': ('浏览器缓存', 'Firefox'),
            'tencent': ('社交通讯', '腾讯软件'), 'wechat': ('社交通讯', '微信 WeChat'), 'qq': ('社交通讯', 'QQ'),
            'dingtalk': ('办公软件', '钉钉'), 'feishu': ('办公软件', '飞书'),
            'adobe': ('设计工具', 'Adobe'), 'steam': ('游戏平台', 'Steam'), 'vscode': ('开发工具', 'VS Code'),
            'nvidia': ('驱动缓存', 'NVIDIA'), 'amd': ('驱动缓存', 'AMD'), 'obs': ('视频工具', 'OBS')
        }

    def infer_info(self, name, dir_path):
        name_lower = name.lower()
        cat, soft = "其他应用", name
        for key, (c, s) in self.app_mapping.items():
            if key in name_lower:
                cat, soft = c, s
                break
        return cat, soft

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
                                if entry.is_file(follow_symlinks=False): total += entry.stat().st_size
                                elif entry.is_dir(follow_symlinks=False): stack.append(entry.path)
                            except: pass
                except: pass
        except: pass
        return total

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0: return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"

    def scan_generator(self):
        # 1. 回收站
        try:
            rb_size = 0
            for drive in range(ord('C'), ord('Z')+1):
                root = f"{chr(drive)}:\\$Recycle.Bin"
                if os.path.exists(root): rb_size += self.get_dir_size_fast(root)
            if rb_size > 0:
                yield {"type": "item", "data": {"cat": "特别清理", "soft": "回收站", "detail": "已删除文件", "path": "RECYCLE_BIN_SPECIAL", "raw_size": rb_size, "display_size": self.format_size(rb_size)}}
        except: pass

        # 2. 基础目标
        for item in self.base_targets:
            yield {"type": "status", "msg": f"正在扫描: {item['path']}"}
            if os.path.exists(item['path']):
                s = self.get_dir_size_fast(item['path'])
                if s > 0: yield {"type": "item", "data": {"cat": item['cat'], "soft": item['soft'], "detail": item['name'], "path": item['path'], "raw_size": s, "display_size": self.format_size(s)}}
        
        # 3. AppData 深度扫描
        roots = [self.local_appdata, self.roaming_appdata]
        
        def process(root):
            res = []
            if not os.path.exists(root): return res
            try:
                with os.scandir(root) as it:
                    for entry in it:
                        if not entry.is_dir(): continue
                        try:
                            # 深度限制为3层，防止遍历过深
                            for dp, dn, fn in os.walk(entry.path):
                                if dp.count(os.sep) - entry.path.count(os.sep) > 3: dn[:]=[]; continue
                                
                                cur = os.path.basename(dp).lower()
                                if any(k in cur for k in self.safe_keywords) and not any(k in cur for k in self.danger_keywords):
                                    cat, soft = self.infer_info(entry.name, dp)
                                    s = self.get_dir_size_fast(dp)
                                    if s > 0:
                                        res.append({"type": "item", "data": {"cat": cat, "soft": soft, "detail": os.path.basename(dp), "path": dp, "raw_size": s, "display_size": self.format_size(s)}})
                                    dn[:] = [] # 找到目标后停止深入该分支
                        except: pass
            except: pass
            return res
        
        # 并行处理
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = []
            for r in roots:
                yield {"type": "status", "msg": f"正在深度扫描: {r} ..."}
                futures.append(ex.submit(process, r))
                
            for fut in futures:
                results = fut.result()
                for r in results: yield r

    def scan_installers(self):
        if not os.path.exists(self.downloads): return
        exts = {'.exe', '.msi', '.iso', '.zip', '.rar', '.7z'}
        now = time.time()
        limit = 30 * 86400
        yield {"type": "status", "msg": f"正在分析: {self.downloads}"}
        try:
            with os.scandir(self.downloads) as it:
                for entry in it:
                    if entry.is_file() and os.path.splitext(entry.name)[1].lower() in exts:
                        try:
                            st = entry.stat()
                            if now - st.st_mtime > limit:
                                yield {"type": "item", "data": {"name": entry.name, "path": entry.path, "raw_size": st.st_size, "date": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"), "display_size": self.format_size(st.st_size)}}
                        except: pass
        except: pass

    def scan_large_files(self):
        dirs = [os.path.join(self.user_profile, d) for d in ["Downloads", "Desktop", "Documents", "Videos", "Pictures"]]
        limit = 100 * 1024 * 1024
        for d in dirs:
            if not os.path.exists(d): continue
            yield {"type": "status", "msg": f"正在雷达扫描: {d}"}
            try:
                for r, ds, fs in os.walk(d):
                    if os.path.basename(r).startswith('.'): ds[:] = []; continue
                    for f in fs:
                        fp = os.path.join(r, f)
                        try:
                            sz = os.path.getsize(fp)
                            if sz > limit: 
                                yield {"type": "item", "data": {"name": f, "path": fp, "raw_size": sz, "display_size": self.format_size(sz)}}
                        except: pass
            except: pass

    def scan_social_apps(self):
        """注册表+路径探测：100% 准确定位微信和 QQ"""
        search_paths = []

        # 1. 尝试从注册表获取微信路径
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat", 0, winreg.KEY_READ)
            path, _ = winreg.QueryValueEx(key, "FileSavePath")
            if path and os.path.exists(path): search_paths.append(("微信 WeChat", path))
            winreg.CloseKey(key)
        except: pass

        # 2. 尝试从注册表获取 QQ 路径 (安装路径或数据路径)
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\QQ2012", 0, winreg.KEY_READ)
            path, _ = winreg.QueryValueEx(key, "UserDataSavePath") # 有些版本是这个
            if path and os.path.exists(path): search_paths.append(("腾讯 QQ", path))
            winreg.CloseKey(key)
        except: pass

        # 3. 常见默认路径补偿 (AppData 和 Documents)
        common_bases = [
            os.path.join(os.environ['APPDATA'], "Tencent"),
            os.path.join(os.environ['USERPROFILE'], "Documents"),
            os.path.join(os.environ['LOCALAPPDATA'], "Tencent")
        ]
        
        # 补加 SHGetSpecialFolderPath 获取的文档路径
        buf = ctypes.create_unicode_buffer(1024)
        ctypes.windll.shell32.SHGetSpecialFolderPathW(None, buf, 0x0005, False)
        if buf.value not in common_bases: common_bases.append(buf.value)

        social_targets = [
            {"name": "微信 WeChat", "root_names": ["WeChat Files", "WeChat"], "junk_subs": ["FileStorage\\Cache", "FileStorage\\Image", "FileStorage\\Video", "FileStorage\\File", "FileStorage\\CustomEmoji"]},
            {"name": "腾讯 QQ", "root_names": ["Tencent Files", "TencentFiles", "QQ"], "junk_subs": ["Image", "Video", "File", "Audio", "Cache"]}
        ]

        # 4. 针对用户的特殊自定义路径进行增强搜索 (例如 E:\Cache)
        custom_suspects = []
        for drive in drives:
            # 常见的自定义缓存命名
            for suspect in ["Cache", "TempCache", "TencentData", "WeChatData"]:
                p = os.path.join(drive, suspect)
                if os.path.exists(p): custom_suspects.append(p)
        
        for base in set(common_bases + custom_suspects):
            if not os.path.exists(base): continue
            
            # 模式 A: 目录直接是 WeChat Files
            for target in social_targets:
                for r_name in target['root_names']:
                    full_path = os.path.join(base, r_name)
                    if os.path.exists(full_path):
                        search_paths.append((target['name'], full_path))
            
            # 模式 B: 目录是 E:\Cache，里面直接就是账号文件夹 (微信特有结构)
            # 我们检查里面是否包含 FileStorage 这种特征
            try:
                with os.scandir(base) as it:
                    for entry in it:
                        if entry.is_dir():
                            # 微信特征检测
                            if os.path.exists(os.path.join(entry.path, "FileStorage")):
                                search_paths.append(("微信 WeChat", base))
                                break
                            # QQ 特征检测
                            if any(os.path.exists(os.path.join(entry.path, sub)) for sub in ["Image", "Video", "Audio"]):
                                search_paths.append(("腾讯 QQ", base))
                                break
            except: pass

        # 去重并开始分析
        unique_paths = {}
        for name, path in search_paths:
            if path not in unique_paths: unique_paths[path] = name

        for full_path, name in unique_paths.items():
            yield {"type": "status", "msg": f"正在分析社交目录: {full_path}"}
            target = next((t for t in social_targets if t['name'] == name), None)
            if not target: continue
            
            try:
                with os.scandir(full_path) as it:
                    for entry in it:
                        # 排除系统级文件夹，通常是 UIN 或微信号
                        if entry.is_dir() and entry.name not in ["All Users", "Applet", "config"]:
                            for sub in target['junk_subs']:
                                full_sub = os.path.join(entry.path, sub)
                                if os.path.exists(full_sub):
                                    s = self.get_dir_size_fast(full_sub)
                                    if s > 0:
                                        yield {"type": "item", "data": {
                                            "cat": target['name'],
                                            "soft": entry.name,
                                            "detail": sub.split('\\')[-1], 
                                            "path": full_sub, 
                                            "raw_size": s, 
                                            "display_size": self.format_size(s)
                                        }}
            except: pass

    def scan_custom(self, paths):
        """智能扫描用户自定义目录"""
        for base in paths:
            if not os.path.exists(base): continue
            yield {"type": "status", "msg": f"正在智能分析自定义目录: {base}"}
            try:
                # 使用 walk 遍历，但限制深度以保证性能
                for root, dirs, files in os.walk(base):
                    # 深度限制逻辑
                    if root.count(os.sep) - base.count(os.sep) > 3:
                        dirs[:] = []
                        continue
                    
                    cur_name = os.path.basename(root).lower()
                    # 识别垃圾文件夹特征
                    if any(k in cur_name for k in self.safe_keywords) and not any(k in cur_name for k in self.danger_keywords):
                        s = self.get_dir_size_fast(root)
                        if s > 0:
                            yield {"type": "item", "data": {
                                "cat": "自定义目录",
                                "soft": os.path.basename(base),
                                "detail": os.path.relpath(root, base),
                                "path": root,
                                "raw_size": s,
                                "display_size": self.format_size(s)
                            }}
                            dirs[:] = [] # 找到一个垃圾根目录后，不再深入其子目录以免重复统计
            except: pass

    def delete_item(self, path):
        if path == "RECYCLE_BIN_SPECIAL":
            try: return 0, 0 if ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7) == 0 else 1
            except: return 0, 1
        if not os.path.exists(path): return 0, 0
        ds, errs = 0, 0
        try:
            if os.path.isfile(path): s=os.path.getsize(path); os.remove(path); return s, 0
            for r, d, f in os.walk(path, topdown=False):
                for file in f:
                    try: fp=os.path.join(r,file); ds+=os.path.getsize(fp); os.remove(fp)
                    except: errs+=1
                for dir in d:
                    try: os.rmdir(os.path.join(r,dir))
                    except: pass
            try: os.rmdir(path)
            except: pass
        except: errs+=1
        return ds, errs

# --- UI 主程序 ---
class CleanerGUI:
    def __init__(self, root):
        self.root = root
        self.cleaner = SystemCleaner()
        self.queue = Queue()
        self.current_mode = "junk"
        self.custom_paths_file = "custom_paths.txt"
        self.custom_paths = self.load_custom_paths()
        
        self.node_map = {} 
        self.total_scan_size = 0
        
        self.load_icons()
        self.setup_style()
        self.setup_layout()
        
        if not is_admin():
            self.root.after(100, self.ask_admin)

    def load_custom_paths(self):
        if os.path.exists(self.custom_paths_file):
            try:
                with open(self.custom_paths_file, 'r', encoding='utf-8') as f:
                    return [line.strip() for line in f if os.path.exists(line.strip())]
            except: return []
        return []

    def save_custom_paths(self):
        try:
            with open(self.custom_paths_file, 'w', encoding='utf-8') as f:
                for p in self.custom_paths: f.write(p + "\n")
        except: pass

    def ask_admin(self):
        if messagebox.askyesno("权限请求", "本工具需要管理员权限才能清理系统垃圾。\n是否重新以管理员身份运行？"):
            run_as_admin()
            self.root.destroy()
            sys.exit()

    def load_icons(self):
        self.icons = {k: tk.PhotoImage(data=v) for k, v in ICONS.items()}

    def setup_style(self):
        s = ttk.Style()
        try: s.theme_use('vista')
        except: s.theme_use('clam')
        
        # --- 纯净白昼配色 (Pure Light Theme) ---
        self.colors = {
            "bg_side": "#f3f3f3",      # 极浅灰侧边栏
            "fg_side": "#444444",      # 深灰文字
            "accent": "#0067c0",       # Windows 11 Blue
            "bg_main": "#ffffff",      # 纯白内容区
            "sel_side": "#e9e9e9",     # 侧边栏选中背景
            "fg_title": "#202020",     # 标题文字
            "status_bar": "#f0f0f0"    # 状态栏背景
        }
        
        s.configure(".", background=self.colors["bg_main"], font=("Segoe UI Variable Display", 9))
        
        # 侧边栏样式
        s.configure("Sidebar.Treeview", 
                    background=self.colors["bg_side"], 
                    fieldbackground=self.colors["bg_side"], 
                    foreground=self.colors["fg_side"], 
                    rowheight=45, 
                    font=("Segoe UI", 11), 
                    borderwidth=0)
        s.map("Sidebar.Treeview", background=[('selected', self.colors["sel_side"])], foreground=[('selected', 'black')])
        
        # 内容区样式
        s.configure("Content.Treeview", background="white", fieldbackground="white", rowheight=32, font=("Segoe UI", 10), borderwidth=0)
        s.configure("Content.Treeview.Heading", background="white", foreground="#666", font=("Segoe UI", 9, "bold"), relief="flat")
        s.map("Content.Treeview", background=[('selected', '#e5f3ff')], foreground=[('selected', 'black')])
        
        # 进度条
        s.configure("Horizontal.TProgressbar", background=self.colors["accent"], troughcolor="#e0e0e0", bordercolor="#e0e0e0", lightcolor=self.colors["accent"], darkcolor=self.colors["accent"])

    def setup_layout(self):
        self.root.title("C盘深度清理 v4.2 (渲染增强版)")
        self.root.geometry("1100x750")
        
        main = tk.Frame(self.root, bg="white")
        main.pack(fill="both", expand=True)
        
        # --- Sidebar ---
        side = tk.Frame(main, bg=self.colors["bg_side"], width=240)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        
        # Title
        tk.Label(side, text="Clean Master", bg=self.colors["bg_side"], fg=self.colors["fg_title"], 
                 font=("Segoe UI", 16, "bold"), pady=30, anchor="w", padx=25).pack(fill="x")
        
        self.menu = ttk.Treeview(side, style="Sidebar.Treeview", show="tree", selectmode="browse")
        self.menu.pack(fill="both", expand=True)
        self.menu_items = {
            self.menu.insert("", "end", text=" 智能清理", image=self.icons['clean'], open=True): "junk",
            self.menu.insert("", "end", text=" 社交专清", image=self.icons['chat']): "social",
            self.menu.insert("", "end", text=" 自定义扫描", image=self.icons['folder']): "custom",
            self.menu.insert("", "end", text=" 安装包", image=self.icons['box']): "inst",
            self.menu.insert("", "end", text=" 大文件", image=self.icons['search']): "large"
        }
        self.menu.bind("<<TreeviewSelect>>", self.on_menu_change)
        
        # --- Content ---
        content = tk.Frame(main, bg="white")
        content.pack(side="right", fill="both", expand=True)
        
        # Header
        self.header = tk.Frame(content, bg="white", height=90, padx=30, pady=15)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        
        self.lbl_title = tk.Label(self.header, text="准备就绪", font=("Segoe UI Variable Display", 20, "bold"), bg="white", fg="#333")
        self.lbl_title.pack(side="left")
        
        # Action Buttons Container
        self.btn_frame = tk.Frame(self.header, bg="white")
        self.btn_frame.pack(side="right")

        self.btn_add_path = tk.Button(self.btn_frame, text="添加目录", bg="#666", fg="white", 
                                    font=("Segoe UI", 9), relief="flat", padx=15, pady=5, cursor="hand2", command=self.on_add_path)
        
        self.btn_action = tk.Button(self.btn_frame, text="开始扫描", bg=self.colors["accent"], fg="white", 
                                    font=("Segoe UI", 10, "bold"), relief="flat", padx=30, pady=8, cursor="hand2", command=self.on_scan)
        self.btn_action.pack(side="right", padx=(10, 0))
        
        # Progress Bar (Hidden by default)
        self.progress = ttk.Progressbar(content, style="Horizontal.TProgressbar", mode="indeterminate", length=500)
        
        # Tree Area
        self.tree_frame = tk.Frame(content, bg="white", padx=20, pady=0)
        self.tree_frame.pack(fill="both", expand=True)
        
        self.tree = ttk.Treeview(self.tree_frame, style="Content.Treeview", show="headings", selectmode="extended")
        scroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<ButtonRelease-1>", self.on_click_release)

        # Treeview Tags (颜色高亮) - Moved here to fix AttributeError
        self.tree.tag_configure("huge", foreground="#d83b01", font=("Segoe UI", 10, "bold")) # > 500MB (Red)
        self.tree.tag_configure("large", foreground="#ea5e00") # > 50MB (Orange)
        self.tree.tag_configure("normal", foreground="#333333")
        
        # Status Bar
        self.status_bar = tk.Label(content, text=" 就绪", bd=0, relief="flat", anchor="w", 
                                   bg=self.colors["status_bar"], fg="#666", font=("Segoe UI", 9), padx=10, pady=5)
        self.status_bar.pack(fill="x", side="bottom")

        self.menu.selection_set(list(self.menu_items.keys())[0])
        self.set_cols("junk")

    def set_cols(self, mode):
        if mode in ["junk", "social", "custom"]:
            self.tree.configure(show="tree headings")
            self.tree["columns"] = ("size", "path")
            self.tree.heading("#0", text="分类 / 名称", anchor="w")
            self.tree.column("#0", width=380)
            self.tree.heading("size", text="大小", anchor="e")
            self.tree.column("size", width=100)
            self.tree.heading("path", text="路径", anchor="w")
            self.tree.column("path", width=350)
        elif mode == "inst":
            self.tree.configure(show="headings")
            self.tree["columns"] = ("date", "name", "path", "size")
            self.tree.heading("date", text="日期", anchor="w"); self.tree.column("date", width=100)
            self.tree.heading("name", text="文件名", anchor="w"); self.tree.column("name", width=250)
            self.tree.heading("path", text="路径", anchor="w"); self.tree.column("path", width=400)
            self.tree.heading("size", text="大小", anchor="e"); self.tree.column("size", width=100)
        elif mode == "large":
            self.tree.configure(show="headings")
            self.tree["columns"] = ("name", "path", "size")
            self.tree.heading("name", text="文件名", anchor="w"); self.tree.column("name", width=250)
            self.tree.heading("path", text="路径", anchor="w"); self.tree.column("path", width=500)
            self.tree.heading("size", text="大小", anchor="e"); self.tree.column("size", width=100)

    def on_add_path(self):
        from tkinter import filedialog
        path = filedialog.askdirectory()
        if path:
            path = os.path.normpath(path)
            if path not in self.custom_paths:
                self.custom_paths.append(path)
                self.save_custom_paths()
                messagebox.showinfo("成功", f"已添加目录: {path}")
                if self.current_mode == "custom":
                    self.lbl_title.config(text=f"已添加 {len(self.custom_paths)} 个目录")

    def on_menu_change(self, e):
        sel = self.menu.selection()
        if not sel: return
        self.current_mode = self.menu_items[sel[0]]
        self.tree.delete(*self.tree.get_children())
        self.node_map = {}
        self.size_stats = {} # Reset stats
        self.lbl_title.config(text="准备就绪")
        
        # 显示/隐藏添加按钮
        if self.current_mode == "custom":
            self.btn_add_path.pack(side="left")
            self.lbl_title.config(text=f"已添加 {len(self.custom_paths)} 个目录")
        else:
            self.btn_add_path.pack_forget()

        self.btn_action.config(text="开始扫描", bg=self.colors["accent"], state="normal")
        self.set_cols(self.current_mode)
        self.status_bar.config(text=" 就绪")

    def on_scan(self):
        if self.btn_action['text'] == "立即清理":
            self.clean_selected()
            return
            
        if self.current_mode == "custom" and not self.custom_paths:
            messagebox.showwarning("提示", "请先点击'添加目录'，告诉我要扫描哪里。")
            return

        self.tree.delete(*self.tree.get_children())
        self.node_map = {}
        self.size_stats = {} # key: item_id, val: size_in_bytes
        self.total_scan_size = 0
        self.lbl_title.config(text="扫描中...")
        self.btn_action.config(state="disabled", bg="#cccccc")
        
        self.progress.pack(fill="x", before=self.tree_frame, padx=20, pady=(0, 10))
        self.progress.start(10)
        
        threading.Thread(target=self.thread_scan, daemon=True).start()
        self.root.after(20, self.consume_queue)

    def thread_scan(self):
        gen = None
        if self.current_mode == "junk": gen = self.cleaner.scan_generator()
        elif self.current_mode == "social": gen = self.cleaner.scan_social_apps()
        elif self.current_mode == "custom": gen = self.cleaner.scan_custom(self.custom_paths)
        elif self.current_mode == "inst": gen = self.cleaner.scan_installers()
        elif self.current_mode == "large": gen = self.cleaner.scan_large_files()
        
        if gen:
            for item in gen: self.queue.put(item)
        self.queue.put({"type": "done"})

    def consume_queue(self):
        try:
            # 动态调整批处理数量，保证 UI 流畅
            start_time = time.time()
            while time.time() - start_time < 0.05: # 每帧最多处理 50ms
                msg = self.queue.get_nowait()
                m_type = msg.get("type")
                
                if m_type == "status":
                    self.status_bar.config(text=f" {msg['msg']}")
                
                elif m_type == "item":
                    data = msg['data']
                    if self.current_mode in ["junk", "social", "custom"]:
                        self.add_junk_node(data)
                    elif self.current_mode == "inst":
                        tag = self.get_size_tag(data['raw_size'])
                        self.tree.insert("", "end", values=(data['date'], data['name'], data['path'], data['display_size']), tags=(tag,))
                    elif self.current_mode == "large":
                        tag = self.get_size_tag(data['raw_size'])
                        self.tree.insert("", "end", values=(data['name'], data['path'], data['display_size']), tags=(tag,))
                
                elif m_type == "done":
                    self.progress.stop()
                    self.progress.pack_forget()
                    self.lbl_title.config(text="扫描完成")
                    self.status_bar.config(text=" 扫描完成")
                    self.btn_action.config(state="disabled", text="立即清理") 
                    
                    if self.current_mode in ["junk", "social", "custom"]:
                        if self.total_scan_size == 0:
                             self.lbl_title.config(text="系统很干净")
                        else:
                            # 扫描结束后，更新父节点统计并排序
                            self.update_junk_tree_stats()
                            self.lbl_title.config(text=f"发现垃圾: {self.cleaner.format_size(self.total_scan_size)}")
                    else:
                        if len(self.tree.get_children()) > 0:
                            self.update_btn_state() # Trigger check
                    return
        except Empty: pass
        self.root.after(20, self.consume_queue)

    def get_size_tag(self, size):
        if size > 500 * 1024 * 1024: return "huge"
        if size > 50 * 1024 * 1024: return "large"
        return "normal"

    def add_junk_node(self, data):
        # 1. Ensure Category Node
        cat_id = f"cat_{data['cat']}"
        if not self.tree.exists(cat_id):
            self.tree.insert("", "end", iid=cat_id, text=f" {data['cat']}", image=self.icons['sys'], open=True)
            self.size_stats[cat_id] = 0
            
        # 2. Ensure Software Node
        soft_id = f"soft_{data['cat']}_{data['soft']}"
        if not self.tree.exists(soft_id):
            self.tree.insert(cat_id, "end", iid=soft_id, text=f" {data['soft']}", image=self.icons['app'], open=True)
            self.size_stats[soft_id] = 0
            
        # 3. Add Leaf Node
        icon = self.icons['bin'] if data['path'] == "RECYCLE_BIN_SPECIAL" else self.icons['sys']
        import uuid
        uid = str(uuid.uuid4())
        
        tag = self.get_size_tag(data['raw_size'])
        self.tree.insert(soft_id, "end", iid=uid, text=f" {data['detail']}", values=(data['display_size'], data['path']), image=icon, tags=(tag,))
        
        self.node_map[uid] = data
        self.total_scan_size += data['raw_size']
        
        # Accumulate stats
        self.size_stats[cat_id] += data['raw_size']
        self.size_stats[soft_id] += data['raw_size']

    def update_junk_tree_stats(self):
        # 遍历所有分类节点
        cats = self.tree.get_children()
        cat_list = []
        
        for cat_id in cats:
            # 1. 更新软件层级
            softs = self.tree.get_children(cat_id)
            soft_list = []
            for soft_id in softs:
                s_size = self.size_stats.get(soft_id, 0)
                # 更新文本和Size列
                self.tree.set(soft_id, "size", self.cleaner.format_size(s_size))
                # 标记颜色
                tag = self.get_size_tag(s_size)
                self.tree.item(soft_id, tags=(tag,))
                soft_list.append((s_size, soft_id))
            
            # 排序软件 (大 -> 小)
            soft_list.sort(key=lambda x: x[0], reverse=True)
            for i, (sz, sid) in enumerate(soft_list):
                self.tree.move(sid, cat_id, i)
            
            # 2. 更新分类层级
            c_size = self.size_stats.get(cat_id, 0)
            self.tree.set(cat_id, "size", self.cleaner.format_size(c_size))
            cat_list.append((c_size, cat_id))
            
        # 排序分类 (大 -> 小)
        cat_list.sort(key=lambda x: x[0], reverse=True)
        for i, (sz, cid) in enumerate(cat_list):
            self.tree.move(cid, "", i)
            self.tree.item(cid, open=True) # 默认展开

    def on_click_release(self, event):
        item = self.tree.identify_row(event.y)
        if not item: return
        # 级联选择逻辑
        children = self.tree.get_children(item)
        if children:
            current_sel = list(self.tree.selection())
            # 如果点击的是父节点，全选/反选逻辑比较复杂，这里简化为：点击父节点选中所有子节点
            # 实际上 Treeview 多选比较繁琐，这里只做简单的向下选中
            should_select = item in current_sel
            
            queue = list(children)
            while queue:
                child = queue.pop(0)
                if should_select:
                    if child not in current_sel: current_sel.append(child)
                # 递归处理
                grand_children = self.tree.get_children(child)
                if grand_children: queue.extend(grand_children)
                
            self.tree.selection_set(current_sel)
        self.update_btn_state()

    def on_select(self, e):
        self.update_btn_state()

    def update_btn_state(self):
        sel = self.tree.selection()
        has_leaf = False
        if self.current_mode == "junk":
            for s in sel:
                if s in self.node_map: has_leaf = True; break
        else: has_leaf = bool(sel)
        
        if has_leaf: 
            self.btn_action.config(state="normal", bg="#d83b01", fg="white")
        else: 
            self.btn_action.config(state="disabled", bg="#cccccc")

    def clean_selected(self):
        sel = self.tree.selection()
        if not sel: return
        if not messagebox.askyesno("确认", f"确定删除选中的 {len(sel)} 项？"): return
        
        paths = []
        if self.current_mode == "junk":
            for s in sel:
                if s in self.node_map: paths.append(self.node_map[s]['path'])
        elif self.current_mode == "inst":
             for s in sel: paths.append(self.tree.item(s)['values'][2])
        
        self.btn_action.config(state="disabled", text="清理中...")
        self.progress.pack(fill="x", before=self.tree_frame, padx=20, pady=(0, 10))
        self.progress.start(10)
        
        threading.Thread(target=self.thread_clean, args=(paths,), daemon=True).start()
        self.root.after(20, self.consume_clean_queue)

    def thread_clean(self, paths):
        total_freed = 0
        # 使用多线程并行删除，提高 I/O 吞吐量
        # 建议线程数不宜过高，8-16 之间对 SSD 较为理想
        max_workers = min(len(paths), 12) if paths else 1
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有删除任务
            future_to_path = {executor.submit(self.cleaner.delete_item, p): p for p in paths}
            
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    # 获取该路径删除的大小
                    freed_size, errors = future.result()
                    total_freed += freed_size
                    
                    # 实时通知 UI 正在处理的路径
                    p_name = os.path.basename(path) if path != "RECYCLE_BIN_SPECIAL" else "回收站"
                    self.queue.put({"type": "status", "msg": f"已清理: {p_name}"})
                except Exception as e:
                    self.queue.put({"type": "status", "msg": f"错误: 无法处理 {os.path.basename(path)}"})
        
        self.queue.put({"type": "clean_done", "size": total_freed})

    def consume_clean_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg['type'] == "status":
                    self.status_bar.config(text=f" {msg['msg']}")
                elif msg['type'] == "clean_done":
                    self.progress.stop()
                    self.progress.pack_forget()
                    self.status_bar.config(text=" 清理完成")
                    
                    messagebox.showinfo("完成", f"清理结束！释放空间: {self.cleaner.format_size(msg['size'])}")
                    
                    # 刷新界面
                    items_to_delete = []
                    if self.current_mode == "junk":
                        for s in self.tree.selection():
                            if s in self.node_map: items_to_delete.append(s)
                    else:
                        items_to_delete = list(self.tree.selection())
                        
                    for s in items_to_delete:
                        if self.tree.exists(s): self.tree.delete(s)
                        
                    self.btn_action.config(state="normal", text="立即清理")
                    self.lbl_title.config(text="清理完成")
                    return
        except Empty: pass
        self.root.after(20, self.consume_clean_queue)

    def on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if not item in self.tree.selection():
                self.tree.selection_set(item)
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="📂 打开位置", command=lambda: self.open_folder(item))
            menu.post(event.x_root, event.y_root)

    def open_folder(self, item):
        vals = self.tree.item(item)['values']
        if not vals: return
        idx = 1 if self.current_mode in ["junk", "large"] else 2
        path = vals[idx]
        if path == "RECYCLE_BIN_SPECIAL": return
        if os.path.exists(path):
            try:
                if os.path.isfile(path): subprocess.run(['explorer', '/select,', os.path.normpath(path)])
                else: os.startfile(path)
            except: pass

if __name__ == "__main__":
    root = tk.Tk()
    try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = CleanerGUI(root)
    root.mainloop()
