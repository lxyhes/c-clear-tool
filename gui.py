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

class CleanerGUI:
    def __init__(self, root):
        self.root = root
        self.cleaner = SystemCleaner()
        self.queue = Queue()
        self.current_mode = "junk"
        self.custom_paths_file = "custom_paths.txt"
        self.custom_paths = self.load_custom_paths()
        
        # 新增管理器
        self.history = CleanHistory()
        self.config_mgr = ConfigManager()
        self.backup_mgr = BackupManager()
        
        self.node_map = {} 
        self.total_scan_size = 0
        self.size_stats = {}
        
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
            self.menu.insert("", "end", text=f"  {self.icons['box']}  安装包清理"): "inst",
            self.menu.insert("", "end", text=f"  {self.icons['search']}  大文件雷达"): "large",
            self.menu.insert("", "end", text=f"  🔄  重复文件"): "duplicate",
            self.menu.insert("", "end", text=f"  📂  空文件夹"): "empty",
            self.menu.insert("", "end", text=f"  🔗  无效快捷方式"): "shortcut",
            self.menu.insert("", "end", text=f"  🎮  游戏缓存"): "game",
            self.menu.insert("", "end", text=f"  📱  手机备份"): "phone",
            self.menu.insert("", "end", text=f"  🌐  浏览器扩展"): "browser_ext",
            self.menu.insert("", "end", text=f"  📋  剪贴板历史"): "clipboard",
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

        self.tree.tag_configure("huge", foreground="#d83b01", font=("Microsoft YaHei UI", 9, "bold"))
        self.tree.tag_configure("large", foreground="#ea5e00")
        self.tree.tag_configure("normal", foreground="#444")
        self.tree.tag_configure("green", foreground="#107c10")
        
        self.status_bar = tk.Label(content, text="  Ready", bd=0, relief="flat", anchor="w", bg=self.colors["status_bar"], fg="#777", font=("Consolas", 9), padx=15, pady=8)
        self.status_bar.pack(fill="x", side="bottom")

        self.menu.selection_set(list(self.menu_items.keys())[0])
        self.set_cols("junk")

    def set_cols(self, mode):
        if mode in ["junk", "social", "custom", "resign", "duplicate", "empty", "shortcut", "game", "phone", "browser_ext", "clipboard"]:
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
                if self.current_mode in ["custom", "resign"]:
                    count = len(self.custom_paths)
                    self.lbl_title.config(text=f"已添加 {count} 个敏感目录" if self.current_mode == "resign" else f"已添加 {count} 个目录")

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
        self.current_mode = self.menu_items[sel[0]]
        self.tree.delete(*self.tree.get_children())
        self.node_map = {}
        self.size_stats = {}
        self.lbl_title.config(text="准备就绪")
        self.progress_frame.pack_forget()
        
        # 隐藏所有额外按钮
        self.btn_add_path.pack_forget()
        self.btn_backup.pack_forget()
        
        if self.current_mode in ["custom", "resign"]:
            self.btn_add_path.pack(side="left")
            count = len(self.custom_paths)
            self.lbl_title.config(text=f"已添加 {count} 个敏感目录" if self.current_mode == "resign" else f"已添加 {count} 个目录")
        
        if self.current_mode in ["junk", "social", "custom", "resign", "inst", "large", "duplicate", "empty", "shortcut", "game", "phone", "browser_ext", "clipboard"]:
            self.btn_backup.pack(side="left", padx=(0, 8))

        if self.current_mode == "disk":
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
        """双击预览文件列表"""
        if self.current_mode == "settings":
            return
        
        item = self.tree.identify_row(event.y)
        if not item or item not in self.node_map: return
        
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
        if self.current_mode == "custom" and not self.custom_paths:
            messagebox.showwarning("提示", "请先添加扫描目录。\n")
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

    def thread_scan(self):
        gen = None
        if self.current_mode == "junk": gen = self.cleaner.scan_generator()
        elif self.current_mode == "social": gen = self.cleaner.scan_social_apps()
        elif self.current_mode == "resign": gen = self.cleaner.scan_resignation_targets(self.custom_paths)
        elif self.current_mode == "custom": gen = self.cleaner.scan_custom(self.custom_paths)
        elif self.current_mode == "inst": gen = self.cleaner.scan_installers()
        elif self.current_mode == "large": gen = self.cleaner.scan_large_files()
        elif self.current_mode == "duplicate": gen = self.cleaner.scan_duplicate_files()
        elif self.current_mode == "empty": gen = self.cleaner.scan_empty_folders()
        elif self.current_mode == "shortcut": gen = self.cleaner.scan_broken_shortcuts()
        elif self.current_mode == "game": gen = self.cleaner.scan_game_cache()
        elif self.current_mode == "phone": gen = self.cleaner.scan_phone_backups()
        elif self.current_mode == "browser_ext": gen = self.cleaner.scan_browser_extensions_cache()
        elif self.current_mode == "clipboard": gen = self.cleaner.scan_clipboard_data()
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
                    if self.current_mode in ["junk", "social", "custom", "resign", "duplicate", "empty", "shortcut", "game", "phone", "browser_ext", "clipboard"]:
                        self.add_junk_node(data)
                    elif self.current_mode == "inst":
                        tag = self.get_size_tag(data['raw_size'])
                        self.tree.insert("", "end", values=(data['date'], data['name'], data['path'], data['display_size']), tags=(tag,))
                    elif self.current_mode == "large":
                        tag = self.get_size_tag(data['raw_size'])
                        self.tree.insert("", "end", values=(data['name'], data['path'], data['display_size']), tags=(tag,))
                elif m_type == "done":
                    self.progress_frame.pack_forget()
                    if self.current_mode in ["junk", "social", "custom", "resign", "duplicate", "empty", "shortcut", "game", "phone", "browser_ext", "clipboard"]:
                        if self.total_scan_size == 0: self.lbl_title.config(text="系统很干净")
                        else:
                            self.update_junk_tree_stats()
                            self.lbl_title.config(text=f"共发现 {utils.format_size(self.total_scan_size)}")
                    else: 
                        self.lbl_title.config(text="扫描完成")
                        self.update_btn_state()
                    self.btn_action.config(state="disabled", text="立即清理")
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
                    self.btn_action.config(state="normal", text="开始扫描"); self.lbl_title.config(text="操作完成")
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
        idx = 1 if self.current_mode in ["junk", "social", "custom", "resign", "large"] else 2
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
