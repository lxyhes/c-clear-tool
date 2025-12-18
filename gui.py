import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import uuid

from core import SystemCleaner
import utils

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
        self.size_stats = {}
        
        self.icons = utils.get_icons()
        self.setup_style()
        self.setup_layout()
        
        if not utils.is_admin():
            self.root.after(100, self.ask_admin)

    def ask_admin(self):
        if messagebox.askyesno("权限请求", "本工具需要管理员权限才能清理系统垃圾。\n是否重新以管理员身份运行？"):
            utils.run_as_admin()
            self.root.destroy()
            import sys
            sys.exit()

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
            "bg_side": "#f3f3f3", "fg_side": "#444444", "accent": "#0067c0",
            "bg_main": "#ffffff", "sel_side": "#e9e9e9", "fg_title": "#202020",
            "status_bar": "#f0f0f0"
        }
        
        s.configure(".", background=self.colors["bg_main"], font=("Segoe UI Variable Display", 9))
        s.configure("Sidebar.Treeview", background=self.colors["bg_side"], fieldbackground=self.colors["bg_side"], foreground=self.colors["fg_side"], rowheight=45, font=("Segoe UI", 11), borderwidth=0)
        s.map("Sidebar.Treeview", background=[('selected', self.colors["sel_side"])], foreground=[('selected', 'black')])
        s.configure("Content.Treeview", background="white", fieldbackground="white", rowheight=32, font=("Segoe UI", 10), borderwidth=0)
        s.configure("Content.Treeview.Heading", background="white", foreground="#666", font=("Segoe UI", 9, "bold"), relief="flat")
        s.map("Content.Treeview", background=[('selected', '#e5f3ff')], foreground=[('selected', 'black')])
        s.configure("Horizontal.TProgressbar", background=self.colors["accent"], troughcolor="#e0e0e0")

    def setup_layout(self):
        self.root.title("C盘深度清理 v5.0 (模块化增强版)")
        self.root.geometry("1100x750")
        
        main = tk.Frame(self.root, bg="white")
        main.pack(fill="both", expand=True)
        
        side = tk.Frame(main, bg=self.colors["bg_side"], width=240)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        
        tk.Label(side, text="Clean Master", bg=self.colors["bg_side"], fg=self.colors["fg_title"], font=("Segoe UI", 16, "bold"), pady=30, anchor="w", padx=25).pack(fill="x")
        
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
        
        content = tk.Frame(main, bg="white")
        content.pack(side="right", fill="both", expand=True)
        
        self.header = tk.Frame(content, bg="white", height=90, padx=30, pady=15)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        
        self.lbl_title = tk.Label(self.header, text="准备就绪", font=("Segoe UI Variable Display", 20, "bold"), bg="white", fg="#333")
        self.lbl_title.pack(side="left")
        
        self.btn_frame = tk.Frame(self.header, bg="white")
        self.btn_frame.pack(side="right")

        self.btn_add_path = tk.Button(self.btn_frame, text="添加目录", bg="#666", fg="white", font=("Segoe UI", 9), relief="flat", padx=15, pady=5, cursor="hand2", command=self.on_add_path)
        self.btn_action = tk.Button(self.btn_frame, text="开始扫描", bg=self.colors["accent"], fg="white", font=("Segoe UI", 10, "bold"), relief="flat", padx=30, pady=8, cursor="hand2", command=self.on_scan)
        self.btn_action.pack(side="right", padx=(10, 0))
        
        self.progress = ttk.Progressbar(content, style="Horizontal.TProgressbar", mode="indeterminate", length=500)
        
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

        self.tree.tag_configure("huge", foreground="#d83b01", font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("large", foreground="#ea5e00")
        self.tree.tag_configure("normal", foreground="#333333")
        
        self.status_bar = tk.Label(content, text=" 就绪", bd=0, relief="flat", anchor="w", bg=self.colors["status_bar"], fg="#666", font=("Segoe UI", 9), padx=10, pady=5)
        self.status_bar.pack(fill="x", side="bottom")

        self.menu.selection_set(list(self.menu_items.keys())[0])
        self.set_cols("junk")

    def set_cols(self, mode):
        if mode in ["junk", "social", "custom"]:
            self.tree.configure(show="tree headings")
            self.tree["columns"] = ("size", "path")
            self.tree.heading("#0", text="分类 / 名称", anchor="w"); self.tree.column("#0", width=380)
            self.tree.heading("size", text="大小", anchor="e"); self.tree.column("size", width=100)
            self.tree.heading("path", text="路径", anchor="w"); self.tree.column("path", width=350)
        elif mode == "inst":
            self.tree.configure(show="headings")
            self.tree["columns"] = ("date", "name", "path", "size")
            self.tree.heading("date", text="日期"); self.tree.column("date", width=100)
            self.tree.heading("name", text="文件名"); self.tree.column("name", width=250)
            self.tree.heading("path", text="路径"); self.tree.column("path", width=400)
            self.tree.heading("size", text="大小", anchor="e"); self.tree.column("size", width=100)
        elif mode == "large":
            self.tree.configure(show="headings")
            self.tree["columns"] = ("name", "path", "size")
            self.tree.heading("name", text="文件名"); self.tree.column("name", width=250)
            self.tree.heading("path", text="路径"); self.tree.column("path", width=500)
            self.tree.heading("size", text="大小", anchor="e"); self.tree.column("size", width=100)

    def on_add_path(self):
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
        self.size_stats = {}
        self.lbl_title.config(text="准备就绪")
        
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
            messagebox.showwarning("提示", "请先添加目录。" )
            return
        self.tree.delete(*self.tree.get_children())
        self.node_map = {}
        self.size_stats = {}
        self.total_scan_size = 0
        self.lbl_title.config(text="扫描中...")
        self.btn_action.config(state="disabled", bg="#cccccc")
        self.progress.pack(fill="x", before=self.tree_frame, padx=20, pady=(0, 10)); self.progress.start(10)
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
            start_time = time.time()
            while time.time() - start_time < 0.05:
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
                    self.progress.stop(); self.progress.pack_forget()
                    self.lbl_title.config(text="扫描完成")
                    if self.current_mode in ["junk", "social", "custom"]:
                        if self.total_scan_size == 0: self.lbl_title.config(text="系统很干净")
                        else: 
                            self.update_junk_tree_stats()
                            self.lbl_title.config(text=f"发现垃圾: {utils.format_size(self.total_scan_size)}")
                    else: self.update_btn_state()
                    return
        except Empty: pass
        self.root.after(20, self.consume_queue)

    def get_size_tag(self, size):
        if size > 500 * 1024 * 1024: return "huge"
        if size > 50 * 1024 * 1024: return "large"
        return "normal"

    def add_junk_node(self, data):
        cat_id = f"cat_{data['cat']}"
        if not self.tree.exists(cat_id):
            self.tree.insert("", "end", iid=cat_id, text=f" {data['cat']}", image=self.icons['sys'], open=True)
            self.size_stats[cat_id] = 0
        soft_id = f"soft_{data['cat']}_{data['soft']}"
        if not self.tree.exists(soft_id):
            self.tree.insert(cat_id, "end", iid=soft_id, text=f" {data['soft']}", image=self.icons['app'], open=True)
            self.size_stats[soft_id] = 0
        uid = str(uuid.uuid4())
        tag = self.get_size_tag(data['raw_size'])
        self.tree.insert(soft_id, "end", iid=uid, text=f" {data['detail']}", values=(data['display_size'], data['path']), image=self.icons['bin'], tags=(tag,))
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
        has_leaf = any(s in self.node_map for s in sel) if self.current_mode in ["junk", "social", "custom"] else bool(sel)
        if has_leaf: self.btn_action.config(state="normal", bg="#d83b01", fg="white")
        else: self.btn_action.config(state="disabled", bg="#cccccc")

    def clean_selected(self):
        sel = self.tree.selection()
        if not sel: return
        if not messagebox.askyesno("确认", f"确定删除选中的 {len(sel)} 项？"): return
        paths = []
        if self.current_mode in ["junk", "social", "custom"]:
            for s in sel:
                if s in self.node_map: paths.append(self.node_map[s]['path'])
        else:
             for s in sel: paths.append(self.tree.item(s)['values'][2])
        self.btn_action.config(state="disabled", text="清理中...")
        self.progress.pack(fill="x", before=self.tree_frame, padx=20, pady=(0, 10)); self.progress.start(10)
        threading.Thread(target=self.thread_clean, args=(paths,), daemon=True).start()
        self.root.after(20, self.consume_clean_queue)

    def thread_clean(self, paths):
        total_freed = 0
        max_workers = min(len(paths), 12) if paths else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {executor.submit(self.cleaner.delete_item, p): p for p in paths}
            for future in as_completed(future_to_path):
                try: 
                    freed, _ = future.result()
                    total_freed += freed
                    p_name = os.path.basename(future_to_path[future])
                    self.queue.put({"type": "status", "msg": f"已清理: {p_name}"})
                except: pass
        self.queue.put({"type": "clean_done", "size": total_freed})

    def consume_clean_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg['type'] == "status": self.status_bar.config(text=f" {msg['msg']}")
                elif msg['type'] == "clean_done":
                    self.progress.stop(); self.progress.pack_forget()
                    messagebox.showinfo("完成", f"清理结束！释放空间: {utils.format_size(msg['size'])}")
                    for s in list(self.tree.selection()):
                        if self.tree.exists(s): self.tree.delete(s)
                    self.btn_action.config(state="normal", text="立即清理"); self.lbl_title.config(text="清理完成")
                    return
        except Empty: pass
        self.root.after(20, self.consume_clean_queue)

    def on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if not item in self.tree.selection(): self.tree.selection_set(item)
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="📂 打开位置", command=lambda: self.open_folder(item))
            menu.post(event.x_root, event.y_root)

    def open_folder(self, item):
        vals = self.tree.item(item)['values']
        if not vals: return
        idx = 1 if self.current_mode in ["junk", "social", "custom", "large"] else 2
        path = vals[idx]
        if os.path.exists(path):
            try:
                if os.path.isfile(path): subprocess.run(['explorer', '/select,', os.path.normpath(path)])
                else: os.startfile(path)
            except: pass
