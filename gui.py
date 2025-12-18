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
            "status_bar": "#f0f0f0"
        }
        
        s.configure(".", background=self.colors["bg_main"], font=("Microsoft YaHei UI", 9))
        s.configure("Sidebar.Treeview", background=self.colors["bg_side"], fieldbackground=self.colors["bg_side"], foreground=self.colors["fg_side"], rowheight=50, font=("Microsoft YaHei UI", 10), borderwidth=0)
        s.map("Sidebar.Treeview", background=[('selected', self.colors["sel_side"])], foreground=[('selected', 'black')])
        s.configure("Content.Treeview", background="white", fieldbackground="white", rowheight=35, font=("Microsoft YaHei UI", 9), borderwidth=0)
        s.configure("Content.Treeview.Heading", background="white", foreground="#666", font=("Microsoft YaHei UI", 9, "bold"), relief="flat")
        s.map("Content.Treeview", background=[('selected', '#eef7ff')], foreground=[('selected', 'black')])
        s.configure("Horizontal.TProgressbar", background=self.colors["accent"], troughcolor="#e0e0e0")

    def setup_layout(self):
        self.root.title("C盘深度清理助手 v5.2")
        self.root.geometry("1150x780")
        
        main = tk.Frame(self.root, bg="white")
        main.pack(fill="both", expand=True)
        
        side = tk.Frame(main, bg=self.colors["bg_side"], width=260)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        
        tk.Label(side, text="  Clean Master", bg=self.colors["bg_side"], fg=self.colors["fg_title"], font=("Microsoft YaHei UI", 16, "bold"), pady=35, anchor="w").pack(fill="x")
        
        self.menu = ttk.Treeview(side, style="Sidebar.Treeview", show="tree", selectmode="browse")
        self.menu.pack(fill="both", expand=True, padx=10)
        
        # 使用彩色 3D 符号装饰菜单
        self.menu_items = {
            self.menu.insert("", "end", text=f"  {self.icons['clean']}  智能清理", open=True): "junk",
            self.menu.insert("", "end", text=f"  {self.icons['chat']}  社交专清"): "social",
            self.menu.insert("", "end", text=f"  {self.icons['fire']}  离职专清"): "resign",
            self.menu.insert("", "end", text=f"  {self.icons['folder']}  自定义扫描"): "custom",
            self.menu.insert("", "end", text=f"  {self.icons['box']}  安装包清理"): "inst",
            self.menu.insert("", "end", text=f"  {self.icons['search']}  大文件雷达"): "large"
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
        self.btn_action = tk.Button(self.btn_frame, text="  开始扫描  ", bg=self.colors["accent"], fg="white", font=("Microsoft YaHei UI", 10, "bold"), relief="flat", padx=35, pady=10, cursor="hand2", command=self.on_scan)
        self.btn_action.pack(side="right", padx=(12, 0))
        
        self.progress = ttk.Progressbar(content, style="Horizontal.TProgressbar", mode="indeterminate", length=500)
        
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

        self.tree.tag_configure("huge", foreground="#d83b01", font=("Microsoft YaHei UI", 9, "bold"))
        self.tree.tag_configure("large", foreground="#ea5e00")
        self.tree.tag_configure("normal", foreground="#444")
        
        self.status_bar = tk.Label(content, text="  Ready", bd=0, relief="flat", anchor="w", bg=self.colors["status_bar"], fg="#777", font=("Consolas", 9), padx=15, pady=8)
        self.status_bar.pack(fill="x", side="bottom")

        self.menu.selection_set(list(self.menu_items.keys())[0])
        self.set_cols("junk")

    def set_cols(self, mode):
        if mode in ["junk", "social", "custom", "resign"]:
            self.tree.configure(show="tree headings")
            self.tree["columns"] = ("size", "path")
            self.tree.heading("#0", text="  分类 / 名称", anchor="w"); self.tree.column("#0", width=400)
            self.tree.heading("size", text="大小", anchor="e"); self.tree.column("size", width=120)
            self.tree.heading("path", text="存储路径", anchor="w"); self.tree.column("path", width=350)
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

    def on_menu_change(self, e):
        sel = self.menu.selection()
        if not sel: return
        self.current_mode = self.menu_items[sel[0]]
        self.tree.delete(*self.tree.get_children())
        self.node_map = {}
        self.size_stats = {}
        self.lbl_title.config(text="准备就绪")
        
        if self.current_mode in ["custom", "resign"]:
            self.btn_add_path.pack(side="left")
            count = len(self.custom_paths)
            self.lbl_title.config(text=f"已添加 {count} 个敏感目录" if self.current_mode == "resign" else f"已添加 {count} 个目录")
        else:
            self.btn_add_path.pack_forget()

        self.btn_action.config(text="开始扫描", bg=self.colors["accent"], state="normal")
        self.set_cols(self.current_mode)
        self.status_bar.config(text="  Ready")

    def on_scan(self):
        if self.btn_action['text'] == "立即清理":
            self.clean_selected()
            return
        if self.current_mode == "custom" and not self.custom_paths:
            messagebox.showwarning("提示", "请先添加扫描目录。" )
            return
        self.tree.delete(*self.tree.get_children())
        self.node_map = {}
        self.size_stats = {}
        self.total_scan_size = 0
        self.lbl_title.config(text="正在分析中...")
        self.btn_action.config(state="disabled", bg="#cccccc")
        self.progress.pack(fill="x", before=self.tree_frame, padx=25, pady=(0, 15)); self.progress.start(15)
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
                elif m_type == "item":
                    data = msg['data']
                    if self.current_mode in ["junk", "social", "custom", "resign"]:
                        self.add_junk_node(data)
                    elif self.current_mode == "inst":
                        tag = self.get_size_tag(data['raw_size'])
                        self.tree.insert("", "end", values=(data['date'], data['name'], data['path'], data['display_size']), tags=(tag,))
                    elif self.current_mode == "large":
                        tag = self.get_size_tag(data['raw_size'])
                        self.tree.insert("", "end", values=(data['name'], data['path'], data['display_size']), tags=(tag,))
                elif m_type == "done":
                    self.progress.stop(); self.progress.pack_forget()
                    if self.current_mode in ["junk", "social", "custom", "resign"]:
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
        # 自动分配图标
        cat_icon = self.icons.get('sys')
        if "浏览器" in data['cat']: cat_icon = self.icons.get('secure')
        elif "社交" in data['cat'] or "通讯" in data['cat']: cat_icon = self.icons.get('chat')
        elif "离职" in data['cat']: cat_icon = self.icons.get('fire')
        elif "私钥" in data['cat'] or "凭据" in data['cat']: cat_icon = self.icons.get('key')
        elif "邮件" in data['cat']: cat_icon = self.icons.get('mail')
        elif "指令" in data['cat']: cat_icon = self.icons.get('cmd')

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
        # 文件项使用垃圾桶图标
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
        has_leaf = any(s in self.node_map for s in sel) if self.current_mode in ["junk", "social", "custom", "resign"] else bool(sel)
        if has_leaf: self.btn_action.config(state="normal", bg="#d83b01", fg="white")
        else: self.btn_action.config(state="disabled", bg="#cccccc")

    def clean_selected(self):
        sel = self.tree.selection()
        if not sel: return
        if self.current_mode == "resign":
            warn_msg = "⚠️ 离职专清终极警示 ⚠️\n\n此操作将永久粉碎社交账号库、邮件、凭据和私钥！\n一旦开始，数据将无法找回。\n\n您确定要彻底抹除所有工作痕迹吗？"
            if not messagebox.askyesno("离职安全粉碎", warn_msg, icon='warning'): return
        elif not messagebox.askyesno("确认清理", f"确定永久删除选中的 {len(sel)} 项垃圾？"): return
        
        paths = []
        if self.current_mode in ["junk", "social", "custom", "resign"]:
            for s in sel:
                if s in self.node_map: paths.append(self.node_map[s]['path'])
        else:
             for s in sel: paths.append(self.tree.item(s)['values'][2])
        self.btn_action.config(state="disabled", text="清理中...")
        self.progress.pack(fill="x", before=self.tree_frame, padx=25, pady=(0, 15)); self.progress.start(15)
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
                    self.queue.put({"type": "status", "msg": f"已粉碎: {p_name}"})
                except: pass
        self.queue.put({"type": "clean_done", "size": total_freed})

    def consume_clean_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg['type'] == "status": self.status_bar.config(text=f"  Cleaning: {msg['msg']}")
                elif msg['type'] == "clean_done":
                    self.progress.stop(); self.progress.pack_forget()
                    messagebox.showinfo("清理完成", f"安全清理结束！已释放空间: {utils.format_size(msg['size'])}")
                    for s in list(self.tree.selection()):
                        if self.tree.exists(s): self.tree.delete(s)
                    self.btn_action.config(state="normal", text="开始扫描"); self.lbl_title.config(text="清理完成")
                    self.status_bar.config(text="  Cleaning finished.")
                    return
        except Empty: pass
        self.root.after(20, self.consume_clean_queue)

    def on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if not item in self.tree.selection(): self.tree.selection_set(item)
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="  📂  打开文件位置 ", command=lambda: self.open_folder(item))
            menu.post(event.x_root, event.y_root)

    def open_folder(self, item):
        vals = self.tree.item(item)['values']
        if not vals: return
        idx = 1 if self.current_mode in ["junk", "social", "custom", "resign", "large"] else 2
        path = vals[idx]
        if os.path.exists(path):
            try:
                if os.path.isfile(path): subprocess.run(['explorer', '/select,', os.path.normpath(path)])
                else: os.startfile(path)
            except: pass

if __name__ == "__main__":
    from gui import CleanerGUI
    root = tk.Tk()
    app = CleanerGUI(root)
    root.mainloop()
