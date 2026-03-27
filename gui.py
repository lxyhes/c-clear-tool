import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import uuid
import subprocess

from core import SystemCleaner
import utils
from utils import CleanHistory, ConfigManager, BackupManager
from media_viewer import MediaViewer

class CleanerGUI:
    def __init__(self, root):
        self.root = root
        self.cleaner = SystemCleaner()
        self.queue = Queue()
        self.current_mode = "junk"
        self.custom_paths_file = "custom_paths.txt"
        self.custom_paths = self.load_custom_paths()
        self.deep_scan_var = tk.BooleanVar(value=False)  # 深度扫描选项
        
        # 新增管理器
        self.history = CleanHistory()
        self.config_mgr = ConfigManager()
        self.backup_mgr = BackupManager()
        
        self.node_map = {} 
        self.total_scan_size = 0
        self.size_stats = {}
        
        # 媒体文件查看器
        self.media_viewer = None
        self.media_files_cache = []
        
        self.icons = utils.get_icons()
        self.setup_style()
        self.setup_layout()
        
        if not utils.is_admin():
            self.root.after(100, self.ask_admin)

    def ask_admin(self):
        if messagebox.askyesno("权限提示", "部分清理功能需要管理员权限，是否以管理员身份重新启动？"):
            utils.run_as_admin()
            self.root.destroy()

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

    def setup_style(self):
        s = ttk.Style()
        try: s.theme_use('vista')
        except: s.theme_use('clam')
        
        self.colors = {
            "bg_side": "#f9f9f9", "fg_side": "#333333", "accent": "#0067c0",
            "bg_main": "#ffffff", "sel_side": "#ececec", "fg_title": "#1a1a1a",
            "status_bar": "#f0f0f0", "green": "#107c10", "orange": "#ff8c00"
        }
        
        s.configure(".", background=self.colors["bg_main"], font=("Microsoft YaHei UI", 9))
        s.configure("Sidebar.Treeview", background=self.colors["bg_side"], fieldbackground=self.colors["bg_side"], foreground=self.colors["fg_side"], rowheight=42, font=("Microsoft YaHei UI", 10), borderwidth=0)
        s.map("Sidebar.Treeview", background=[('selected', self.colors["sel_side"])], foreground=[('selected', 'black')])
        s.configure("Content.Treeview", background="white", fieldbackground="white", rowheight=35, font=("Microsoft YaHei UI", 9), borderwidth=0)
        s.configure("Content.Treeview.Heading", background="white", foreground="#666", font=("Microsoft YaHei UI", 9, "bold"), relief="flat")
        s.map("Content.Treeview", background=[('selected', '#eef7ff')], foreground=[('selected', 'black')])
        s.configure("Horizontal.TProgressbar", background=self.colors["accent"], troughcolor="#e0e0e0")
        s.configure("Green.Horizontal.TProgressbar", background=self.colors["green"], troughcolor="#e0e0e0")

    def setup_layout(self):
        self.root.title("C盘深度清理助手 v7.0 (全能版)")
        self.root.geometry("1200x820")
        
        main = tk.Frame(self.root, bg="white")
        main.pack(fill="both", expand=True)
        
        side = tk.Frame(main, bg=self.colors["bg_side"], width=260)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        
        tk.Label(side, text=f"  {self.icons['shield']} Clean Master", bg=self.colors["bg_side"], fg=self.colors["fg_title"], font=("Microsoft YaHei UI", 16, "bold"), pady=25, anchor="w").pack(fill="x")
        
        self.menu = ttk.Treeview(side, style="Sidebar.Treeview", show="tree", selectmode="browse")
        self.menu.pack(fill="both", expand=True, padx=10)
        
        self.menu_items = {
            self.menu.insert("", "end", text=f"  {self.icons['clean']}  智能清理", open=True): "junk",
            self.menu.insert("", "end", text=f"  {self.icons['chat']}  社交专清"): "social",
            self.menu.insert("", "end", text=f"  {self.icons['fire']}  离职专清"): "resign",
            self.menu.insert("", "end", text=f"  {self.icons['folder']}  自定义扫描"): "custom",
            self.menu.insert("", "end", text=f"  📷  媒体文件检测"): "media",
            self.menu.insert("", "end", text=f"  {self.icons['box']}  安装包清理"): "inst",
            self.menu.insert("", "end", text=f"  {self.icons['search']}  大文件雷达"): "large",
            self.menu.insert("", "end", text=f"  🔄  重复文件"): "duplicate",
            self.menu.insert("", "end", text=f"  📂  空文件夹"): "empty",
            self.menu.insert("", "end", text=f"  🔗  无效快捷方式"): "shortcut",
            self.menu.insert("", "end", text=f"  🎮  游戏缓存"): "game",
            self.menu.insert("", "end", text=f"  📱  手机备份"): "phone",
            self.menu.insert("", "end", text=f"  🌐  浏览器扩展"): "browser_ext",
            self.menu.insert("", "end", text=f"  📋  剪贴板历史"): "clipboard",
            self.menu.insert("", "end", text=f"  📊  空间分析"): "space",
            self.menu.insert("", "end", text=f"  {self.icons['chart']}  磁盘概览"): "disk",
            self.menu.insert("", "end", text=f"  {self.icons['history']}  清理历史"): "history",
            self.menu.insert("", "end", text=f"  {self.icons['config']}  设置"): "settings"
        }
        self.menu.bind("<<TreeviewSelect>>", self.on_menu_change)
        
        content = tk.Frame(main, bg="white")
        content.pack(side="right", fill="both", expand=True)
        
        self.header = tk.Frame(content, bg="white", height=100, padx=35, pady=20)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        
        self.lbl_title = tk.Label(self.header, text="准备就绪", font=("Microsoft YaHei UI", 22, "bold"), bg="white", fg="#222")
        self.lbl_title.pack(side="left")
        
        self.btn_frame = tk.Frame(self.header, bg="white")
        self.btn_frame.pack(side="right")

        self.btn_add_path = tk.Button(self.btn_frame, text=" ➕ 添加目录 ", bg="#f0f0f0", fg="#333", font=("Microsoft YaHei UI", 9), relief="flat", padx=15, pady=6, cursor="hand2", command=self.on_add_path)
        self.btn_backup = tk.Button(self.btn_frame, text=" 💾 备份 ", bg="#f0f0f0", fg="#333", font=("Microsoft YaHei UI", 9), relief="flat", padx=15, pady=6, cursor="hand2", command=self.on_backup)
        self.btn_expand_all = tk.Button(self.btn_frame, text=" ⬇️ 全部展开 ", bg="#f0f0f0", fg="#333", font=("Microsoft YaHei UI", 9), relief="flat", padx=15, pady=6, cursor="hand2", command=self.on_expand_all)
        self.btn_collapse_all = tk.Button(self.btn_frame, text=" ⬆️ 全部收起 ", bg="#f0f0f0", fg="#333", font=("Microsoft YaHei UI", 9), relief="flat", padx=15, pady=6, cursor="hand2", command=self.on_collapse_all)
        # 深度扫描复选框
        self.chk_deep_scan = tk.Checkbutton(self.btn_frame, text=" 🔍 深度扫描 ", variable=self.deep_scan_var, 
                                            bg="white", fg="#333", font=("Microsoft YaHei UI", 9), 
                                            selectcolor="white", activebackground="white")
        self.btn_action = tk.Button(self.btn_frame, text="  开始扫描  ", bg=self.colors["accent"], fg="white", font=("Microsoft YaHei UI", 10, "bold"), relief="flat", padx=35, pady=10, cursor="hand2", command=self.on_scan)
        self.btn_action.pack(side="right", padx=(12, 0))

        # 进度条区域（带百分比和剩余时间）
        self.progress_frame = tk.Frame(content, bg="white")
        self.progress = ttk.Progressbar(self.progress_frame, style="Horizontal.TProgressbar", mode="determinate", length=500)
        self.progress.pack(side="left", fill="x", expand=True)
        self.lbl_progress = tk.Label(self.progress_frame, text="", bg="white", fg="#666", font=("Microsoft YaHei UI", 9))
        self.lbl_progress.pack(side="right", padx=(10, 0))
        
        self.tree_frame = tk.Frame(content, bg="white", padx=25, pady=0)
        self.tree_frame.pack(fill="both", expand=True)
        
        self.tree = ttk.Treeview(self.tree_frame, style="Content.Treeview", show="headings", selectmode="extended")
        scroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<ButtonRelease-1>", self.on_click_release)
        self.tree.bind("<Double-1>", self.on_double_click)
        # 空间分析模式支持单击展开/折叠
        self.tree.bind("<Button-1>", self.on_tree_click)

        self.tree.tag_configure("huge", foreground="#d83b01", font=("Microsoft YaHei UI", 9, "bold"))
        self.tree.tag_configure("large", foreground="#ea5e00")
        self.tree.tag_configure("normal", foreground="#444")
        self.tree.tag_configure("green", foreground="#107c10")
        
        self.status_bar = tk.Label(content, text="  Ready", bd=0, relief="flat", anchor="w", bg=self.colors["status_bar"], fg="#777", font=("Consolas", 9), padx=15, pady=8)
        self.status_bar.pack(fill="x", side="bottom")

        self.menu.selection_set(list(self.menu_items.keys())[0])
        self.set_cols("junk")

    def set_cols(self, mode):
        if mode in ["junk", "social", "custom", "resign", "duplicate", "empty", "shortcut", "game", "phone", "browser_ext", "clipboard", "space"]:
            self.tree.configure(show="tree headings")
            self.tree["columns"] = ("size", "path")
            self.tree.heading("#0", text="  分类 / 名称", anchor="w"); self.tree.column("#0", width=400)
            self.tree.heading("size", text="大小", anchor="e"); self.tree.column("size", width=120)
            self.tree.heading("path", text="存储路径", anchor="w"); self.tree.column("path", width=400)
        elif mode == "inst":
            self.tree.configure(show="headings")
            self.tree["columns"] = ("date", "name", "path", "size")
            self.tree.heading("date", text="修改日期"); self.tree.column("date", width=120)
            self.tree.heading("name", text="安装包文件名"); self.tree.column("name", width=280)
            self.tree.heading("path", text="文件位置"); self.tree.column("path", width=400)
            self.tree.heading("size", text="占用空间"); self.tree.column("size", width=120, anchor="e")
        elif mode == "large":
            self.tree.configure(show="headings")
            self.tree["columns"] = ("name", "path", "size")
            self.tree.heading("name", text="超大文件名"); self.tree.column("name", width=280)
            self.tree.heading("path", text="详细路径"); self.tree.column("path", width=500)
            self.tree.heading("size", text="文件体积"); self.tree.column("size", width=120, anchor="e")
        elif mode == "disk":
            self.tree.configure(show="headings")
            self.tree["columns"] = ("drive", "total", "used", "free", "percent")
            self.tree.heading("drive", text="分区"); self.tree.column("drive", width=80)
            self.tree.heading("total", text="总容量"); self.tree.column("total", width=120)
            self.tree.heading("used", text="已使用"); self.tree.column("used", width=120)
            self.tree.heading("free", text="可用空间"); self.tree.column("free", width=120)
            self.tree.heading("percent", text="使用率"); self.tree.column("percent", width=150)
        elif mode == "history":
            self.tree.configure(show="headings")
            self.tree["columns"] = ("time", "mode", "freed", "items")
            self.tree.heading("time", text="清理时间"); self.tree.column("time", width=180)
            self.tree.heading("mode", text="清理模式"); self.tree.column("mode", width=150)
            self.tree.heading("freed", text="释放空间"); self.tree.column("freed", width=150)
            self.tree.heading("items", text="清理项数"); self.tree.column("items", width=100)
        elif mode == "settings":
            self.tree.configure(show="headings")
            self.tree["columns"] = ("option", "value", "action")
            self.tree.heading("option", text="设置项"); self.tree.column("option", width=200)
            self.tree.heading("value", text="当前值"); self.tree.column("value", width=300)
            self.tree.heading("action", text="操作"); self.tree.column("action", width=150)

    def on_add_path(self):
        path = filedialog.askdirectory()
        if path:
            path = os.path.normpath(path)
            if path not in self.custom_paths:
                self.custom_paths.append(path)
                self.save_custom_paths()
                # 刷新标题
                if self.current_mode in ["custom", "resign", "media"]:
                    count = len(self.custom_paths)
                    if self.current_mode == "resign":
                        self.lbl_title.config(text=f"已添加 {count} 个敏感目录")
                    elif self.current_mode == "media":
                        self.lbl_title.config(text=f"已添加 {count} 个媒体目录")
                    else:
                        self.lbl_title.config(text=f"已添加 {count} 个目录")
                # 刷新 tree 显示
                self.refresh_custom_paths_display()
    
    def refresh_custom_paths_display(self):
        """刷新已添加目录的显示"""
        if self.current_mode not in ["custom", "resign", "media"]:
            return
        
        # 清空 tree
        self.tree.delete(*self.tree.get_children())
        
        # 设置列标题
        self.tree.configure(show="tree headings")
        self.tree["columns"] = ("path", "action")
        self.tree.heading("#0", text="已添加的目录")
        self.tree.heading("path", text="路径")
        self.tree.heading("action", text="操作")
        self.tree.column("#0", width=150)
        self.tree.column("path", width=500)
        self.tree.column("action", width=80)
        
        # 显示已添加的目录
        if self.custom_paths:
            for i, path in enumerate(self.custom_paths):
                item_id = f"path_{i}"
                self.tree.insert("", "end", iid=item_id, text=f"📁 {os.path.basename(path)}", 
                                values=(path, "双击删除"))
        else:
            self.tree.insert("", "end", text="请点击「添加目录」按钮添加扫描目录", values=("", ""))

    def on_expand_all(self):
        """全部展开树节点"""
        def expand_recursive(item):
            self.tree.item(item, open=True)
            for child in self.tree.get_children(item):
                expand_recursive(child)
        
        for item in self.tree.get_children():
            expand_recursive(item)
        
        # 空间分析模式下同时更新节点展开状态标记
        if self.current_mode == "space":
            for item_id in self.node_map:
                self.node_map[item_id]["is_expanded"] = True

    def on_collapse_all(self):
        """全部收起树节点"""
        def collapse_recursive(item):
            self.tree.item(item, open=False)
            for child in self.tree.get_children(item):
                collapse_recursive(child)
        
        for item in self.tree.get_children():
            collapse_recursive(item)
        
        # 空间分析模式下同时更新节点展开状态标记
        if self.current_mode == "space":
            for item_id in self.node_map:
                self.node_map[item_id]["is_expanded"] = False

    def on_backup(self):
        """备份选中项目"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择要备份的项目")
            return
        
        paths = []
        if self.current_mode in ["junk", "social", "custom", "resign"]:
            for s in sel:
                if s in self.node_map: paths.append(self.node_map[s]['path'])
        else:
            for s in sel: 
                vals = self.tree.item(s)['values']
                if vals and len(vals) > 2: paths.append(vals[2] if self.current_mode == "inst" else vals[1])
        
        if not paths:
            messagebox.showwarning("提示", "没有可备份的项目")
            return
        
        self.btn_backup.config(state="disabled", text=" 备份中... ")
        
        def do_backup():
            result = self.backup_mgr.create_backup(paths)
            self.root.after(0, lambda: self.on_backup_done(result))
        
        threading.Thread(target=do_backup, daemon=True).start()
    
    def on_backup_done(self, result):
        self.btn_backup.config(state="normal", text=" 💾 备份 ")
        if result:
            messagebox.showinfo("备份完成", f"备份已保存到:\n{result}")
        else:
            messagebox.showerror("备份失败", "备份过程中出现错误")

    def on_menu_change(self, e):
        sel = self.menu.selection()
        if not sel: return
        
        # 如果之前有 MediaViewer，清理它
        if self.media_viewer:
            self.media_viewer.destroy()
            self.media_viewer = None
            # 重新显示 tree_frame
            self.tree_frame.pack(fill="both", expand=True, padx=25, pady=0)
        
        self.current_mode = self.menu_items[sel[0]]
        self.tree.delete(*self.tree.get_children())
        self.node_map = {}
        self.size_stats = {}
        self.lbl_title.config(text="准备就绪")
        self.progress_frame.pack_forget()
        
        # 隐藏所有额外按钮
        self.btn_add_path.pack_forget()
        self.btn_backup.pack_forget()
        self.btn_expand_all.pack_forget()
        self.btn_collapse_all.pack_forget()
        self.chk_deep_scan.pack_forget()
        
        if self.current_mode in ["custom", "resign", "media"]:
            self.btn_add_path.pack(side="left")
            count = len(self.custom_paths)
            if self.current_mode == "resign":
                self.lbl_title.config(text=f"已添加 {count} 个敏感目录")
            elif self.current_mode == "media":
                self.lbl_title.config(text=f"已添加 {count} 个媒体目录")
            else:
                self.lbl_title.config(text=f"已添加 {count} 个目录")
            # 仅在自定义扫描模式下显示深度扫描选项
            if self.current_mode == "custom":
                self.chk_deep_scan.pack(side="left", padx=(0, 8))
            
            # 显示已添加的目录列表
            self.tree.configure(show="tree headings")
            self.tree["columns"] = ("path", "action")
            if self.custom_paths:
                self.tree.heading("#0", text="已添加的目录")
                self.tree.heading("path", text="路径")
                self.tree.heading("action", text="操作")
                self.tree.column("#0", width=150)
                self.tree.column("path", width=500)
                self.tree.column("action", width=80)
                for i, path in enumerate(self.custom_paths):
                    item_id = f"path_{i}"
                    self.tree.insert("", "end", iid=item_id, text=f"📁 {os.path.basename(path)}", 
                                    values=(path, "双击删除"))
            else:
                self.tree.heading("#0", text="提示")
                self.tree.heading("path", text="说明")
                self.tree.heading("action", text="")
                self.tree.column("#0", width=400)
                self.tree.column("path", width=400)
                self.tree.insert("", "end", text="请点击「添加目录」按钮添加扫描目录", values=("", ""))
        
        if self.current_mode in ["junk", "social", "custom", "resign", "media", "inst", "large", "duplicate", "empty", "shortcut", "game", "phone", "browser_ext", "clipboard", "space"]:
            self.btn_backup.pack(side="left", padx=(0, 8))
        
        # 树形结构模式下显示展开/收起按钮
        if self.current_mode in ["junk", "social", "custom", "resign", "media", "duplicate", "empty", "shortcut", "game", "phone", "browser_ext", "clipboard", "space"]:
            self.btn_expand_all.pack(side="left", padx=(0, 4))
            self.btn_collapse_all.pack(side="left", padx=(0, 8))

        if self.current_mode == "space":
            self.btn_action.config(text="开始分析", bg=self.colors["accent"], state="normal")
            # 检查是否有缓存
            cache_file = os.path.join(os.environ['TEMP'], 'ccleaner_space_cache.json')
            if os.path.exists(cache_file):
                import time
                mtime = os.path.getmtime(cache_file)
                age_minutes = (time.time() - mtime) / 60
                if age_minutes < 60:
                    self.lbl_title.config(text=f"C盘空间分析 - 缓存可用（{int(age_minutes)}分钟前）")
                else:
                    self.lbl_title.config(text="C盘空间分析 - 缓存已过期")
            else:
                self.lbl_title.config(text="C盘空间分析 - 找出占用大户")
        elif self.current_mode == "disk":
            self.btn_action.config(text="刷新", bg=self.colors["accent"], state="normal")
            self.show_disk_overview()
        elif self.current_mode == "history":
            self.btn_action.config(text="清空历史", bg=self.colors["orange"], state="normal")
            self.show_history()
        elif self.current_mode == "settings":
            self.btn_action.config(text="保存设置", bg=self.colors["green"], state="normal")
            self.show_settings()
        else:
            self.btn_action.config(text="开始扫描", bg=self.colors["accent"], state="normal")

        self.set_cols(self.current_mode)
        self.status_bar.config(text="  Ready")

    def show_disk_overview(self):
        """显示磁盘概览"""
        self.tree.delete(*self.tree.get_children())
        disks = self.cleaner.get_disk_usage()
        for d in disks:
            tag = "huge" if d["percent"] > 90 else ("large" if d["percent"] > 70 else "green")
            percent_bar = "█" * int(d["percent"] / 5) + "░" * (20 - int(d["percent"] / 5))
            self.tree.insert("", "end", values=(
                d["drive"],
                utils.format_size(d["total"]),
                utils.format_size(d["used"]),
                utils.format_size(d["free"]),
                f"{percent_bar} {d['percent']}%"
            ), tags=(tag,))
        
        stats = self.history.get_stats()
        self.lbl_title.config(text=f"累计释放: {utils.format_size(stats['total_freed'])}")

    def show_history(self):
        """显示清理历史"""
        self.tree.delete(*self.tree.get_children())
        records = self.history.get_records(50)
        mode_names = {"junk": "智能清理", "social": "社交专清", "resign": "离职专清", "custom": "自定义扫描", "inst": "安装包清理", "large": "大文件清理"}
        for r in records:
            self.tree.insert("", "end", values=(
                r["time"],
                mode_names.get(r["mode"], r["mode"]),
                utils.format_size(r["freed_size"]),
                f"{r['items_count']} 项"
            ))
        
        stats = self.history.get_stats()
        self.lbl_title.config(text=f"历史记录 ({stats['record_count']} 条)")

    def show_settings(self):
        """显示设置页面"""
        self.tree.delete(*self.tree.get_children())
        
        # 备份设置
        backups = self.backup_mgr.list_backups()
        backup_info = f"{len(backups)} 个备份" if backups else "无备份"
        self.tree.insert("", "end", iid="backup_list", values=("备份管理", backup_info, "查看备份"))
        
        # 导入导出配置
        self.tree.insert("", "end", iid="export_config", values=("导出配置", "自定义路径和设置", "导出"))
        self.tree.insert("", "end", iid="import_config", values=("导入配置", "从文件导入配置", "导入"))
        
        # 自定义路径数量
        self.tree.insert("", "end", iid="custom_paths", values=("自定义扫描路径", f"{len(self.custom_paths)} 个目录", "管理"))
        
        # 清理历史统计
        stats = self.history.get_stats()
        self.tree.insert("", "end", iid="history_stats", values=("累计清理统计", f"释放 {utils.format_size(stats['total_freed'])} / {stats['total_items']} 项", ""))
        
        # 一键锁屏
        self.tree.insert("", "end", iid="lock_screen", values=("🔒 一键锁屏", "清理后锁定电脑", "立即锁屏"))
        
        # 清理后自动锁屏设置
        auto_lock = self.config_mgr.config.get("auto_lock_after_clean", False)
        self.tree.insert("", "end", iid="auto_lock", values=("清理后自动锁屏", "已启用" if auto_lock else "已禁用", "切换"))
        
        self.lbl_title.config(text="设置")
        
        # 绑定双击事件处理设置操作
        self.tree.bind("<Double-1>", self.on_settings_action)

    def on_settings_action(self, event):
        """处理设置页面的操作"""
        if self.current_mode != "settings": 
            self.on_double_click(event)
            return
        
        item = self.tree.identify_row(event.y)
        if not item: return
        
        if item == "backup_list":
            self.show_backup_list()
        elif item == "export_config":
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON文件", "*.json")])
            if path:
                # 同步自定义路径到配置
                self.config_mgr.config["custom_paths"] = self.custom_paths
                if self.config_mgr.export_config(path):
                    messagebox.showinfo("成功", f"配置已导出到:\n{path}")
                else:
                    messagebox.showerror("失败", "导出配置失败")
        elif item == "import_config":
            path = filedialog.askopenfilename(filetypes=[("JSON文件", "*.json")])
            if path:
                if self.config_mgr.import_config(path):
                    # 同步导入的自定义路径
                    self.custom_paths = self.config_mgr.config.get("custom_paths", [])
                    self.save_custom_paths()
                    messagebox.showinfo("成功", "配置已导入")
                    self.show_settings()
                else:
                    messagebox.showerror("失败", "导入配置失败")
        elif item == "custom_paths":
            self.show_custom_paths_manager()
        elif item == "lock_screen":
            if messagebox.askyesno("确认", "确定要立即锁定屏幕吗？"):
                self.cleaner.lock_screen()
        elif item == "auto_lock":
            current = self.config_mgr.config.get("auto_lock_after_clean", False)
            self.config_mgr.config["auto_lock_after_clean"] = not current
            self.config_mgr.save()
            self.show_settings()

    def show_backup_list(self):
        """显示备份列表窗口"""
        win = tk.Toplevel(self.root)
        win.title("备份管理")
        win.geometry("600x400")
        
        tree = ttk.Treeview(win, columns=("name", "size", "time"), show="headings")
        tree.heading("name", text="备份文件"); tree.column("name", width=250)
        tree.heading("size", text="大小"); tree.column("size", width=100)
        tree.heading("time", text="创建时间"); tree.column("time", width=150)
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        backups = self.backup_mgr.list_backups()
        for b in backups:
            tree.insert("", "end", values=(b["name"], utils.format_size(b["size"]), b["time"]))
        
        def open_backup_folder():
            if os.path.exists(self.backup_mgr.backup_dir):
                os.startfile(self.backup_mgr.backup_dir)
        
        btn = tk.Button(win, text="打开备份文件夹", command=open_backup_folder)
        btn.pack(pady=10)

    def show_custom_paths_manager(self):
        """显示自定义路径管理窗口"""
        win = tk.Toplevel(self.root)
        win.title("自定义扫描路径管理")
        win.geometry("600x400")
        
        listbox = tk.Listbox(win, font=("Microsoft YaHei UI", 10))
        listbox.pack(fill="both", expand=True, padx=10, pady=10)
        
        for p in self.custom_paths:
            listbox.insert("end", p)
        
        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=10)
        
        def add_path():
            path = filedialog.askdirectory()
            if path and path not in self.custom_paths:
                self.custom_paths.append(path)
                listbox.insert("end", path)
                self.save_custom_paths()
        
        def remove_path():
            sel = listbox.curselection()
            if sel:
                idx = sel[0]
                self.custom_paths.pop(idx)
                listbox.delete(idx)
                self.save_custom_paths()
        
        tk.Button(btn_frame, text="添加路径", command=add_path).pack(side="left", padx=5)
        tk.Button(btn_frame, text="删除选中", command=remove_path).pack(side="left", padx=5)

    def on_double_click(self, event):
        """双击预览文件列表、展开空间分析目录或删除自定义路径"""
        if self.current_mode == "settings":
            return
        
        item = self.tree.identify_row(event.y)
        if not item:
            return
        
        # 在 custom、resign、media 模式下，双击删除目录
        if self.current_mode in ["custom", "resign", "media"]:
            if item.startswith("path_"):
                idx = int(item.split("_")[1])
                if 0 <= idx < len(self.custom_paths):
                    path = self.custom_paths[idx]
                    if messagebox.askyesno("确认", f"确定要从列表中删除此目录吗？\n\n{path}"):
                        self.custom_paths.pop(idx)
                        self.save_custom_paths()
                        # 刷新显示
                        count = len(self.custom_paths)
                        if self.current_mode == "resign":
                            self.lbl_title.config(text=f"已添加 {count} 个敏感目录")
                        elif self.current_mode == "media":
                            self.lbl_title.config(text=f"已添加 {count} 个媒体目录")
                        else:
                            self.lbl_title.config(text=f"已添加 {count} 个目录")
                        self.refresh_custom_paths_display()
                return
        
        if item not in self.node_map: 
            # 空间分析模式下处理展开
            if self.current_mode == "space":
                self.toggle_space_expand(item)
            return
        
        # 空间分析模式特殊处理
        if self.current_mode == "space":
            data = self.node_map.get(item, {})
            if data.get("has_children") and not data.get("is_expanded"):
                self.expand_space_node(item)
                return
        
        data = self.node_map[item]
        path = data.get("path", "")
        if not path or path.endswith("_SPECIAL") or not os.path.exists(path): return
        
        # 显示预览窗口
        self.show_preview_window(path, data.get("detail", ""))

    def show_preview_window(self, path, title):
        """显示文件预览窗口"""
        win = tk.Toplevel(self.root)
        win.title(f"预览: {title}")
        win.geometry("700x500")
        
        # 文件列表
        tree = ttk.Treeview(win, columns=("name", "size"), show="headings")
        tree.heading("name", text="文件名"); tree.column("name", width=450)
        tree.heading("size", text="大小"); tree.column("size", width=100, anchor="e")
        
        scroll = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scroll.pack(side="right", fill="y", padx=(0, 10), pady=10)
        
        # 获取文件列表
        files = self.cleaner.get_file_list(path, limit=200)
        total_size = sum(f["size"] for f in files)
        
        for f in files:
            tree.insert("", "end", values=(f["name"], utils.format_size(f["size"])))
        
        # 底部信息
        info = tk.Label(win, text=f"共 {len(files)} 个文件，总计 {utils.format_size(total_size)}", font=("Microsoft YaHei UI", 9), fg="#666")
        info.pack(pady=5)

    def on_scan(self):
        if self.current_mode == "space":
            # 检查是否是"清除缓存并重新分析"
            if self.btn_action['text'] == "清除缓存":
                self.cleaner.clear_space_cache()
                messagebox.showinfo("提示", "空间分析缓存已清除")
                self.btn_action.config(text="开始分析")
                self.lbl_title.config(text="C盘空间分析 - 缓存已清除")
                return
            # 检查是否有缓存，如果有提供清除选项
            cache_file = os.path.join(os.environ['TEMP'], 'ccleaner_space_cache.json')
            if os.path.exists(cache_file) and self.btn_action['text'] == "开始分析":
                import time
                mtime = os.path.getmtime(cache_file)
                age_minutes = (time.time() - mtime) / 60
                if age_minutes < 60 and messagebox.askyesno("缓存可用", f"发现{int(age_minutes)}分钟前的分析缓存，是否直接使用？\n\n选择'是'：秒开缓存结果\n选择'否'：重新扫描（较慢）"):
                    pass  # 继续正常扫描流程，会使用缓存
                else:
                    # 清除过期缓存
                    self.cleaner.clear_space_cache()
            
            # 正常扫描流程
            self.tree.delete(*self.tree.get_children())
            self.node_map = {}
            self.size_stats = {}
            self.total_scan_size = 0
            self.lbl_title.config(text="正在分析中...")
            self.btn_action.config(state="disabled", bg="#cccccc")
            
            # 显示进度条
            self.progress["value"] = 0
            self.progress["mode"] = "determinate"
            self.lbl_progress.config(text="准备中...")
            self.progress_frame.pack(fill="x", before=self.tree_frame, padx=25, pady=(0, 15))
            
            threading.Thread(target=self.thread_scan, daemon=True).start()
            self.root.after(20, self.consume_queue)
            return
        
        if self.current_mode == "disk":
            self.show_disk_overview()
            return
        if self.current_mode == "history":
            if messagebox.askyesno("确认", "确定要清空所有清理历史记录吗？"):
                self.history.history = {"records": [], "total_freed": 0, "total_items": 0}
                self.history.save()
                self.show_history()
            return
        if self.current_mode == "settings":
            messagebox.showinfo("提示", "设置已自动保存")
            return
        
        if self.btn_action['text'] == "立即清理":
            self.clean_selected()
            return
        if self.current_mode in ["custom", "media"] and not self.custom_paths:
            messagebox.showwarning("提示", "请先添加扫描目录。\n")
            return
        
        # 媒体文件检测模式 - 使用 MediaViewer
        if self.current_mode == "media":
            self.start_media_scan()
            return
        
        self.tree.delete(*self.tree.get_children())
        self.node_map = {}
        self.size_stats = {}
        self.total_scan_size = 0
        
        self.lbl_title.config(text="正在分析中...")
        self.btn_action.config(state="disabled", bg="#cccccc")
        
        # 显示进度条
        self.progress["value"] = 0
        self.progress["mode"] = "determinate"
        self.lbl_progress.config(text="准备中...")
        self.progress_frame.pack(fill="x", before=self.tree_frame, padx=25, pady=(0, 15))
        
        threading.Thread(target=self.thread_scan, daemon=True).start()
        self.root.after(20, self.consume_queue)

    def start_media_scan(self):
        """开始媒体文件扫描 - 使用 MediaViewer"""
        # 清空之前的显示
        self.tree.delete(*self.tree.get_children())
        
        # 隐藏默认的 tree_frame，显示 MediaViewer
        self.tree_frame.pack_forget()
        
        # 如果 MediaViewer 已存在，先销毁
        if self.media_viewer:
            self.media_viewer.destroy()
            self.media_viewer = None
        
        # 创建 MediaViewer
        self.media_viewer = MediaViewer(
            self.tree_frame,
            on_delete_callback=self.on_media_deleted
        )
        
        self.lbl_title.config(text="正在扫描媒体文件...")
        self.btn_action.config(state="disabled", bg="#cccccc")
        
        # 显示进度条
        self.progress["value"] = 0
        self.progress["mode"] = "determinate"
        self.lbl_progress.config(text="准备中...")
        self.progress_frame.pack(fill="x", before=self.tree_frame, padx=25, pady=(0, 15))
        
        # 清空缓存
        self.media_files_cache = []
        
        # 启动扫描线程
        threading.Thread(target=self.thread_media_scan, daemon=True).start()
        self.root.after(20, self.consume_media_queue)

    def thread_media_scan(self):
        """媒体文件扫描线程"""
        gen = self.cleaner.scan_media_files(self.custom_paths)
        if gen:
            for item in gen:
                self.queue.put(item)
        self.queue.put({"type": "done"})

    def consume_media_queue(self):
        """处理媒体文件扫描队列"""
        try:
            while True:
                msg = self.queue.get_nowait()
                m_type = msg.get("type")
                
                if m_type == "progress":
                    current = msg.get("current", 0)
                    total = msg.get("total", 1)
                    percent = min(100, int(current / max(total, 1) * 100))
                    self.progress["value"] = percent
                    self.lbl_progress.config(text=f"{percent}%")
                    
                elif m_type == "item":
                    data = msg['data']
                    cat = data.get('cat', '')
                    # 只收集图片和视频文件（不包括统计信息）
                    if '图片' in cat or '视频' in cat:
                        file_info = {
                            'name': data['detail'],
                            'path': data['path'],
                            'size': data['raw_size'],
                            'display_size': data['display_size'],
                            'type': '图片' if '图片' in cat else '视频',
                            'mtime': os.path.getmtime(data['path']) if os.path.exists(data['path']) else 0
                        }
                        self.media_files_cache.append(file_info)
                        
                elif m_type == "done":
                    self.progress_frame.pack_forget()
                    
                    # 更新 MediaViewer
                    if self.media_viewer:
                        self.media_viewer.set_media_files(self.media_files_cache)
                    
                    total = len(self.media_files_cache)
                    if total == 0:
                        self.lbl_title.config(text="未找到图片或视频文件")
                    else:
                        total_size = sum(f['size'] for f in self.media_files_cache)
                        self.lbl_title.config(text=f"扫描完成 - 共发现 {total} 个媒体文件 ({utils.format_size(total_size)})")
                    
                    self.btn_action.config(text="重新扫描", state="normal", bg=self.colors["accent"])
                    self.status_bar.config(text="  扫描完成 - 支持按目录分组查看和选择删除")
                    return
                    
        except Empty:
            pass
        
        self.root.after(20, self.consume_media_queue)

    def on_media_deleted(self):
        """媒体文件删除后的回调"""
        # 刷新显示
        if self.media_viewer:
            self.media_viewer.refresh_file_list()
            self.update_media_stats()
    
    def update_media_stats(self):
        """更新媒体文件统计"""
        if not self.media_viewer:
            return
        
        selected_files = self.media_viewer.get_selected_files()
        remaining_count = len(self.media_viewer.media_files_by_dir)
        
        total_files = sum(len(files) for files in self.media_viewer.media_files_by_dir.values())
        
        self.lbl_title.config(text=f"媒体文件检测 - 共 {total_files} 个文件，选中 {len(selected_files)} 个")

    def thread_scan(self):
        gen = None
        if self.current_mode == "junk": gen = self.cleaner.scan_generator()
        elif self.current_mode == "social": gen = self.cleaner.scan_social_apps()
        elif self.current_mode == "resign": gen = self.cleaner.scan_resignation_targets(self.custom_paths)
        elif self.current_mode == "custom": 
            # 根据深度扫描选项选择扫描方法
            if self.deep_scan_var.get():
                gen = self.cleaner.scan_custom_deep(self.custom_paths)
            else:
                gen = self.cleaner.scan_custom(self.custom_paths)
        elif self.current_mode == "media": gen = self.cleaner.scan_media_files(self.custom_paths)
        elif self.current_mode == "inst": gen = self.cleaner.scan_installers()
        elif self.current_mode == "large": gen = self.cleaner.scan_large_files()
        elif self.current_mode == "duplicate": gen = self.cleaner.scan_duplicate_files()
        elif self.current_mode == "empty": gen = self.cleaner.scan_empty_folders()
        elif self.current_mode == "shortcut": gen = self.cleaner.scan_broken_shortcuts()
        elif self.current_mode == "game": gen = self.cleaner.scan_game_cache()
        elif self.current_mode == "phone": gen = self.cleaner.scan_phone_backups()
        elif self.current_mode == "browser_ext": gen = self.cleaner.scan_browser_extensions_cache()
        elif self.current_mode == "clipboard": gen = self.cleaner.scan_clipboard_data()
        elif self.current_mode == "space": gen = self.cleaner.analyze_c_drive_full()
        if gen:
            for item in gen: self.queue.put(item)
        self.queue.put({"type": "done"})

    def consume_queue(self):
        try:
            start_time = time.time()
            while time.time() - start_time < 0.05:
                msg = self.queue.get_nowait()
                m_type = msg.get("type")
                if m_type == "status":
                    self.status_bar.config(text=f"  Scanning: {msg['msg']}")
                elif m_type == "progress":
                    # 更新进度条
                    current = msg.get("current", 0)
                    total = msg.get("total", 1)
                    scan_start = msg.get("start_time", time.time())
                    
                    percent = min(100, int(current / max(total, 1) * 100))
                    self.progress["value"] = percent
                    
                    # 计算剩余时间
                    elapsed = time.time() - scan_start
                    if current > 0 and elapsed > 0:
                        eta = (elapsed / current) * (total - current)
                        self.lbl_progress.config(text=f"{percent}% - 剩余 {utils.format_time(eta)}")
                    else:
                        self.lbl_progress.config(text=f"{percent}%")
                        
                elif m_type == "item":
                    data = msg['data']
                    if self.current_mode == "space":
                        self.add_space_analysis_node(data)
                    elif self.current_mode in ["junk", "social", "custom", "resign", "duplicate", "empty", "shortcut", "game", "phone", "browser_ext", "clipboard"]:
                        self.add_junk_node(data)
                    elif self.current_mode == "media":
                        # 媒体文件检测结果显示
                        cat = data.get('cat', '')
                        if '图片' in cat or '视频' in cat:
                            tag = self.get_size_tag(data['raw_size'])
                            icon = "🖼️" if '图片' in cat else "🎬"
                            self.tree.insert("", "end", text=f"{icon} {data['detail']}", 
                                           values=(data['display_size'], data['path']), tags=(tag,))
                        elif '统计' in cat:
                            # 统计信息用特殊颜色显示
                            self.tree.insert("", "end", text=f"📊 {data['detail']}", 
                                           values=(data['display_size'], ""), tags=("summary",))
                    elif self.current_mode == "inst":
                        tag = self.get_size_tag(data['raw_size'])
                        self.tree.insert("", "end", values=(data['date'], data['name'], data['path'], data['display_size']), tags=(tag,))
                    elif self.current_mode == "large":
                        tag = self.get_size_tag(data['raw_size'])
                        self.tree.insert("", "end", values=(data['name'], data['path'], data['display_size']), tags=(tag,))
                elif m_type == "done":
                    self.progress_frame.pack_forget()
                    if self.current_mode == "space":
                        self.update_space_tree_stats()
                        total_items = len(self.tree.get_children())
                        # 区分是否是缓存加载
                        cache_file = os.path.join(os.environ['TEMP'], 'ccleaner_space_cache.json')
                        if os.path.exists(cache_file):
                            self.lbl_title.config(text=f"C盘空间分析完成（缓存）- 共 {total_items} 个目录")
                            self.btn_action.config(text="清除缓存", state="normal", bg="#d83b01")
                        else:
                            self.lbl_title.config(text=f"C盘空间分析完成 - 共 {total_items} 个目录")
                            self.btn_action.config(text="重新分析", state="normal", bg=self.colors["accent"])
                    elif self.current_mode == "media":
                        # 媒体文件扫描完成
                        total_items = len(self.tree.get_children())
                        if total_items == 0:
                            self.lbl_title.config(text="未找到图片或视频文件")
                        else:
                            self.lbl_title.config(text=f"扫描完成 - 共发现 {total_items} 个媒体文件")
                        self.btn_action.config(text="重新扫描", state="normal", bg=self.colors["accent"])
                    elif self.current_mode in ["junk", "social", "custom", "resign", "duplicate", "empty", "shortcut", "game", "phone", "browser_ext", "clipboard"]:
                        if self.total_scan_size == 0:
                            self.lbl_title.config(text="系统很干净")
                            self.btn_action.config(state="disabled", text="开始扫描", bg=self.colors["accent"])
                        else:
                            self.update_junk_tree_stats()
                            self.lbl_title.config(text=f"共发现 {utils.format_size(self.total_scan_size)}")
                            self.btn_action.config(text="立即清理")
                            self.update_btn_state()
                    else:
                        self.lbl_title.config(text="扫描完成")
                        self.update_btn_state()
                    self.status_bar.config(text="  Scan completed.")
                    return
        except Empty: pass
        self.root.after(20, self.consume_queue)

    def get_size_tag(self, size):
        if size > 500 * 1024 * 1024: return "huge"
        if size > 50 * 1024 * 1024: return "large"
        return "normal"

    def add_junk_node(self, data):
        cat_icon = self.icons.get('sys')
        if "浏览器" in data['cat']: cat_icon = self.icons.get('secure')
        elif "社交" in data['cat'] or "通讯" in data['cat']: cat_icon = self.icons.get('chat')
        elif "离职" in data['cat']: cat_icon = self.icons.get('fire')
        elif "凭据" in data['cat'] or "开发" in data['cat']: cat_icon = self.icons.get('key')
        elif "邮件" in data['cat']: cat_icon = self.icons.get('mail')
        elif "云端" in data['cat']: cat_icon = self.icons.get('cloud')
        elif "音乐" in data['cat']: cat_icon = self.icons.get('music')
        elif "视频" in data['cat']: cat_icon = self.icons.get('video')
        elif "下载" in data['cat']: cat_icon = self.icons.get('download')
        elif "工具" in data['cat']: cat_icon = self.icons.get('tool')
        elif "办公" in data['cat']: cat_icon = self.icons.get('office')
        elif "系统安全" in data['cat']: cat_icon = self.icons.get('security')
        elif "开发" in data['cat']: cat_icon = self.icons.get('dev')

        cat_id = f"cat_{data['cat']}"
        if not self.tree.exists(cat_id):
            self.tree.insert("", "end", iid=cat_id, text=f"  {cat_icon}  {data['cat']}", open=True)
            self.size_stats[cat_id] = 0
        soft_id = f"soft_{data['cat']}_{data['soft']}"
        if not self.tree.exists(soft_id):
            self.tree.insert(cat_id, "end", iid=soft_id, text=f"  {self.icons['app']}  {data['soft']}", open=True)
            self.size_stats[soft_id] = 0
        uid = str(uuid.uuid4())
        tag = self.get_size_tag(data['raw_size'])
        self.tree.insert(soft_id, "end", iid=uid, text=f"  {self.icons['bin']}  {data['detail']}", values=(data['display_size'], data['path']), tags=(tag,))
        self.node_map[uid] = data
        self.total_scan_size += data['raw_size']
        self.size_stats[cat_id] += data['raw_size']
        self.size_stats[soft_id] += data['raw_size']

    def add_space_analysis_node(self, data, parent=""):
        """添加空间分析节点（树状结构）"""
        name = data.get("name", "Unknown")
        size = data.get("size", 0)
        path = data.get("path", "")
        is_system = data.get("is_system", False)
        has_children = data.get("has_children", False)
        
        # 确定图标
        if is_system:
            icon = "🔒"
        elif size > 10 * 1024 * 1024 * 1024:  # > 10GB
            icon = "🔴"
        elif size > 1024 * 1024 * 1024:  # > 1GB
            icon = "🟠"
        elif size > 100 * 1024 * 1024:  # > 100MB
            icon = "🟡"
        else:
            icon = "🟢"
        
        # 生成可视化条 - 使用最大50GB作为参考
        max_ref = 50 * 1024 * 1024 * 1024
        filled = int(size / max_ref * 20) if max_ref > 0 else 0
        filled = min(filled, 20)
        bar = "█" * filled + "░" * (20 - filled)
        
        # 创建节点文本
        display_text = f"  {icon} {bar} {name}"
        if is_system:
            display_text += " [系统目录]"
        
        # 插入节点
        uid = str(uuid.uuid4())
        tag = "huge" if size > 10 * 1024 * 1024 * 1024 else ("large" if size > 1024 * 1024 * 1024 else "normal")
        
        node = self.tree.insert(parent, "end", iid=uid, text=display_text, 
                               values=(utils.format_size(size), path), tags=(tag,))
        
        self.node_map[uid] = {
            "path": path, 
            "detail": name, 
            "raw_size": size,
            "has_children": has_children,
            "is_expanded": False
        }
        self.total_scan_size = max(self.total_scan_size, size)  # 记录最大大小用于参考
        
        # 如果有子节点但未展开，添加一个占位符用于显示展开按钮
        if has_children and not parent:  # 只在根目录级别预加载
            # 展开时动态加载
            pass
        
        return uid

    def expand_space_node(self, item_id):
        """展开空间分析的节点，动态加载子目录"""
        if item_id not in self.node_map:
            return
        
        data = self.node_map[item_id]
        path = data.get("path", "")
        
        if not path or not os.path.isdir(path):
            return
        
        # 标记为已展开
        self.node_map[item_id]["is_expanded"] = True
        
        # 显示加载中
        self.tree.item(item_id, text=self.tree.item(item_id, "text") + " [加载中...]")
        self.root.update()
        
        # 在新线程中加载子目录
        def load_subdirs():
            from core import DiskSpaceAnalyzer
            analyzer = DiskSpaceAnalyzer()
            subdirs = analyzer.scan_subdir(path)
            
            # 在主线程中更新UI
            self.root.after(0, lambda: self._insert_subdirs(item_id, subdirs))
        
        threading.Thread(target=load_subdirs, daemon=True).start()
    
    def _insert_subdirs(self, parent_id, subdirs):
        """插入子目录到树中"""
        # 移除"[加载中...]"标记
        current_text = self.tree.item(parent_id, "text")
        current_text = current_text.replace(" [加载中...]", "")
        self.tree.item(parent_id, text=current_text)
        
        # 插入子节点
        for subdir in subdirs[:20]:  # 最多显示20个子目录
            self.add_space_analysis_node(subdir, parent=parent_id)
        
        # 展开节点
        self.tree.item(parent_id, open=True)
    
    def toggle_space_expand(self, item_id):
        """切换空间分析节点的展开/折叠状态"""
        if not item_id:
            return
        
        if item_id in self.node_map:
            data = self.node_map[item_id]
            if data.get("has_children"):
                if data.get("is_expanded"):
                    # 折叠
                    self.tree.item(item_id, open=False)
                    self.node_map[item_id]["is_expanded"] = False
                else:
                    # 展开
                    self.expand_space_node(item_id)
    
    def update_space_tree_stats(self):
        """更新空间分析树的统计信息"""
        # 按大小重新排序根节点
        root_items = []
        for item_id in self.tree.get_children():
            size = self.node_map.get(item_id, {}).get("raw_size", 0)
            root_items.append((size, item_id))
        
        root_items.sort(key=lambda x: x[0], reverse=True)
        for i, (size, item_id) in enumerate(root_items):
            self.tree.move(item_id, "", i)
            # 更新显示，添加排名
            current_text = self.tree.item(item_id, "text")
            if not current_text.startswith("  🥇") and not current_text.startswith("  🥈") and not current_text.startswith("  🥉"):
                if i == 0:
                    new_text = "  🥇" + current_text[2:]
                elif i == 1:
                    new_text = "  🥈" + current_text[2:]
                elif i == 2:
                    new_text = "  🥉" + current_text[2:]
                else:
                    new_text = f"  {i+1:2d}" + current_text[2:]
                self.tree.item(item_id, text=new_text)

    def update_junk_tree_stats(self):
        cats = self.tree.get_children()
        cat_list = []
        for cat_id in cats:
            softs = self.tree.get_children(cat_id)
            soft_list = []
            for soft_id in softs:
                s_size = self.size_stats.get(soft_id, 0)
                self.tree.set(soft_id, "size", utils.format_size(s_size))
                self.tree.item(soft_id, tags=(self.get_size_tag(s_size),))
                soft_list.append((s_size, soft_id))
            soft_list.sort(key=lambda x: x[0], reverse=True)
            for i, (sz, sid) in enumerate(soft_list): self.tree.move(sid, cat_id, i)
            c_size = self.size_stats.get(cat_id, 0)
            self.tree.set(cat_id, "size", utils.format_size(c_size))
            cat_list.append((c_size, cat_id))
        cat_list.sort(key=lambda x: x[0], reverse=True)
        for i, (sz, cid) in enumerate(cat_list): self.tree.move(cid, "", i)

    def on_tree_click(self, event):
        """处理树形控件的单击事件"""
        # 获取点击的区域
        region = self.tree.identify_region(event.x, event.y)
        item = self.tree.identify_row(event.y)
        
        if not item:
            return
        
        # 空间分析模式下，点击展开图标展开/折叠
        if self.current_mode == "space":
            # 检查是否点击了展开图标区域
            if region == "tree":
                column = self.tree.identify_column(event.x)
                if column == "#0":  # 第一列（展开图标所在列）
                    if item in self.node_map:
                        data = self.node_map[item]
                        if data.get("has_children"):
                            # 切换展开状态
                            if self.tree.item(item, "open"):
                                self.tree.item(item, open=False)
                            else:
                                if not data.get("is_expanded"):
                                    self.expand_space_node(item)
                                else:
                                    self.tree.item(item, open=True)
    
    def on_click_release(self, event):
        item = self.tree.identify_row(event.y)
        if not item: return
        children = self.tree.get_children(item)
        if children:
            current_sel = list(self.tree.selection())
            should_select = item in current_sel
            queue = list(children)
            while queue:
                child = queue.pop(0)
                if should_select and child not in current_sel: current_sel.append(child)
                grand = self.tree.get_children(child)
                if grand: queue.extend(grand)
            self.tree.selection_set(current_sel)
        self.update_btn_state()

    def on_select(self, e): self.update_btn_state()

    def update_btn_state(self):
        sel = self.tree.selection()
        tree_modes = ["junk", "social", "custom", "resign", "duplicate", "empty", "shortcut", "game", "phone", "browser_ext", "clipboard"]
        has_leaf = any(s in self.node_map for s in sel) if self.current_mode in tree_modes else bool(sel)
        if has_leaf: self.btn_action.config(state="normal", bg="#d83b01", fg="white")
        else: self.btn_action.config(state="disabled", bg="#cccccc")

    def clean_selected(self):
        sel = self.tree.selection()
        if not sel: return
        
        # 1. 离职专清二次警示
        if self.current_mode == "resign":
            warn_msg = "⚠️ 终极警示 ⚠️\n\n此模式将执行【数据粉碎】清理，聊天记录和私钥将永久消失且无法恢复。\n\n确定要彻底抹除吗？"
            if not messagebox.askyesno("离职安全粉碎", warn_msg, icon='warning'): return
        elif not messagebox.askyesno("确认清理", f"确定永久删除选中的 {len(sel)} 项垃圾？"):
            return
        
        # 2. 进程占用检测与解锁
        apps_to_check = list(set([self.node_map[s]['cat'] for s in sel if s in self.node_map]))
        active_apps = self.cleaner.detect_active_processes(apps_to_check)
        if active_apps:
            if messagebox.askyesno("进程占用", f"检测到以下程序正在运行，必须关闭后才能彻底清理：\n\n{', '.join(active_apps)}\n\n是否强制关闭并继续？"):
                self.cleaner.kill_processes(active_apps)
                time.sleep(1)
            else: return

        # 3. 开始清理/粉碎
        paths = []
        tree_modes = ["junk", "social", "custom", "resign", "duplicate", "empty", "shortcut", "game", "phone", "browser_ext", "clipboard"]
        if self.current_mode in tree_modes:
            for s in sel:
                if s in self.node_map: paths.append(self.node_map[s]['path'])
        else:
            for s in sel: 
                vals = self.tree.item(s)['values']
                if vals and len(vals) > 2:
                    paths.append(vals[2] if self.current_mode == "inst" else vals[1])
        
        self.btn_action.config(state="disabled", text="粉碎中..." if self.current_mode == "resign" else "清理中...")
        self.progress["value"] = 0
        self.progress["mode"] = "determinate"
        self.lbl_progress.config(text="0%")
        self.progress_frame.pack(fill="x", before=self.tree_frame, padx=25, pady=(0, 15))
        
        threading.Thread(target=self.thread_clean, args=(paths,), daemon=True).start()
        self.root.after(20, self.consume_clean_queue)

    def thread_clean(self, paths):
        total_freed = 0
        total = len(paths)
        max_workers = min(total, 12) if paths else 1
        completed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            clean_func = self.cleaner.shred_item if self.current_mode == "resign" else self.cleaner.delete_item
            future_to_path = {executor.submit(clean_func, p): p for p in paths}
            for future in as_completed(future_to_path):
                try:
                    freed, _ = future.result()
                    total_freed += freed
                    completed += 1
                    p_name = os.path.basename(future_to_path[future])
                    action = "已粉碎" if self.current_mode == "resign" else "已清理"
                    self.queue.put({"type": "status", "msg": f"{action}: {p_name}"})
                    self.queue.put({"type": "clean_progress", "current": completed, "total": total})
                except: pass
        self.queue.put({"type": "clean_done", "size": total_freed, "count": len(paths)})

    def consume_clean_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg['type'] == "status": 
                    self.status_bar.config(text=f"  Action: {msg['msg']}")
                elif msg['type'] == "clean_progress":
                    percent = int(msg['current'] / max(msg['total'], 1) * 100)
                    self.progress["value"] = percent
                    self.lbl_progress.config(text=f"{percent}% ({msg['current']}/{msg['total']})")
                elif msg['type'] == "clean_done":
                    self.progress_frame.pack_forget()
                    
                    # 记录清理历史
                    self.history.add_record(self.current_mode, msg['size'], msg['count'])
                    
                    info = f"清理结束！已释放空间: {utils.format_size(msg['size'])}"
                    if self.current_mode == "resign":
                        report_p = self.cleaner.generate_report(msg['size'], msg['count'])
                        if report_p: info += f"\n\n已为您在桌面生成安全审计报告。"
                    
                    messagebox.showinfo("完成", info)
                    for s in list(self.tree.selection()):
                        if self.tree.exists(s): self.tree.delete(s)

                    # 检查是否还有剩余项
                    remaining_items = len([n for n in self.node_map.keys() if self.tree.exists(n)])
                    if remaining_items > 0:
                        self.btn_action.config(text="立即清理")
                        self.lbl_title.config(text=f"剩余 {remaining_items} 项待清理")
                        self.update_btn_state()
                    else:
                        self.btn_action.config(state="normal", text="开始扫描", bg=self.colors["accent"])
                        self.lbl_title.config(text="操作完成")

                    self.status_bar.config(text="  Operation finished.")
                    
                    # 检查是否需要自动锁屏
                    if self.config_mgr.config.get("auto_lock_after_clean", False):
                        if messagebox.askyesno("锁屏", "清理完成，是否立即锁定屏幕？"):
                            self.cleaner.lock_screen()
                    
                    # 离职模式特殊处理：询问是否锁屏
                    elif self.current_mode == "resign":
                        if messagebox.askyesno("离职专清", "数据已粉碎完成，是否立即锁定屏幕？"):
                            self.cleaner.lock_screen()
                    return
        except Empty: pass
        self.root.after(20, self.consume_clean_queue)

    def on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if not item in self.tree.selection(): self.tree.selection_set(item)
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="  📂  打开文件位置 ", command=lambda: self.open_folder(item))
            if item in self.node_map:
                menu.add_command(label="  🔍  预览文件列表 ", command=lambda: self.show_preview_window(self.node_map[item]['path'], self.node_map[item].get('detail', '')))
                menu.add_separator()
                menu.add_command(label="  💾  备份此项 ", command=lambda: self.backup_single(item))
            menu.post(event.x_root, event.y_root)

    def backup_single(self, item):
        """备份单个项目"""
        if item not in self.node_map: return
        path = self.node_map[item]['path']
        if not path or path.endswith("_SPECIAL"): return
        
        result = self.backup_mgr.create_backup([path])
        if result:
            messagebox.showinfo("备份完成", f"备份已保存到:\n{result}")
        else:
            messagebox.showerror("备份失败", "备份过程中出现错误")

    def open_folder(self, item):
        vals = self.tree.item(item)['values']
        if not vals: return
        
        # 根据不同模式获取路径的索引
        if self.current_mode in ["junk", "social", "custom", "resign", "large"]:
            idx = 1
        elif self.current_mode in ["media", "inst"]:
            idx = 1
        else:
            idx = 2
        
        # 获取路径并打开文件夹
        if len(vals) > idx:
            path = vals[idx]
            if path and os.path.exists(path):
                if os.path.isfile(path):
                    # 如果是文件，打开所在文件夹并选中文件
                    subprocess.run(['explorer', '/select,', path])
                else:
                    # 如果是文件夹，直接打开
                    os.startfile(path)
            else:
                messagebox.showwarning("提示", "文件或目录不存在")

    def save_to_cache(self):
        """保存当前扫描结果到缓存"""
        cache_key = '_'.join(self.custom_paths) if self.custom_paths else ''
        self.scan_cache.set(self.current_mode, cache_key, {
            'large_files': self.large_files_cache,
            'node_map': self.node_map,
            'total_size': self.total_scan_size
        })

    def load_from_cache(self, cache_data):
        """从缓存加载扫描结果"""
        self.tree.delete(*self.tree.get_children())
        self.large_files_cache = cache_data.get('large_files', [])
        self.node_map = cache_data.get('node_map', {})
        self.total_scan_size = cache_data.get('total_size', 0)
        
        for f in self.large_files_cache:
            tag = self.get_size_tag(f['raw_size'])
            self.tree.insert("", "end", values=(f['name'], f['path'], f['display_size']), tags=(tag,))
        
        self.lbl_title.config(text=f"共发现 {len(self.large_files_cache)} 个大文件（缓存）")
        self.btn_action.config(state="normal", text="移动/删除", bg=self.colors["accent"])
        self.status_bar.config(text="  Loaded from cache.")
        path = vals[idx] if len(vals) > idx else None
        if path and os.path.exists(path):
            try:
                if os.path.isfile(path): subprocess.run(['explorer', '/select,', os.path.normpath(path)])
                else: os.startfile(path)
            except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = CleanerGUI(root)
    root.mainloop()
