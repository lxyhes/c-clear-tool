"""
媒体文件查看器 - 支持多种视图模式（大图标/小图标/列表/详细信息）
"""
import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageOps
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


class MediaViewer:
    """媒体文件查看器，支持多种渲染方式"""
    
    # 视图模式常量
    VIEW_LARGE_ICON = "large_icon"    # 大图标
    VIEW_SMALL_ICON = "small_icon"    # 小图标
    VIEW_LIST = "list"                # 列表
    VIEW_DETAILS = "details"          # 详细信息
    
    def __init__(self, parent_frame, on_select=None, on_double_click=None):
        self.parent = parent_frame
        self.on_select = on_select
        self.on_double_click = on_double_click
        
        # 当前视图模式
        self.current_view = self.VIEW_LARGE_ICON
        
        # 缩略图缓存
        self.thumbnail_cache = {}
        self.icon_cache = {}
        
        # 媒体文件数据
        self.media_files = []
        
        # 创建UI
        self.setup_ui()
        
        # 线程池用于生成缩略图
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    def setup_ui(self):
        """创建用户界面"""
        # 工具栏
        self.toolbar = tk.Frame(self.parent, bg="white")
        self.toolbar.pack(fill="x", pady=(0, 5))
        
        # 视图切换按钮
        tk.Label(self.toolbar, text="视图模式:", bg="white").pack(side="left", padx=(5, 2))
        
        self.view_buttons = {}
        views = [
            (self.VIEW_LARGE_ICON, "🔲 大图标"),
            (self.VIEW_SMALL_ICON, "▫️ 小图标"),
            (self.VIEW_LIST, "📄 列表"),
            (self.VIEW_DETAILS, "📋 详细信息")
        ]
        
        for view_mode, label in views:
            btn = tk.Button(self.toolbar, text=label, relief="flat", bg="#f0f0f0",
                          command=lambda v=view_mode: self.switch_view(v))
            btn.pack(side="left", padx=2)
            self.view_buttons[view_mode] = btn
        
        # 高亮当前视图按钮
        self.highlight_view_button(self.VIEW_LARGE_ICON)
        
        # 搜索框
        tk.Label(self.toolbar, text="  搜索:", bg="white").pack(side="left", padx=(20, 2))
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(self.toolbar, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=2)
        tk.Button(self.toolbar, text="🔍", relief="flat", bg="#f0f0f0",
                 command=self.filter_files).pack(side="left", padx=2)
        
        # 创建 Canvas 和滚动条（用于大图标/小图标视图）
        self.canvas_frame = tk.Frame(self.parent)
        self.canvas = tk.Canvas(self.canvas_frame, bg="white", highlightthickness=0)
        self.v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)
        
        # 创建 Treeview（用于列表/详细信息视图）
        self.tree_frame = tk.Frame(self.parent)
        self.tree = ttk.Treeview(self.tree_frame, show="headings", selectmode="extended")
        self.tree_v_scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_v_scrollbar.set)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        
        # 绑定 Canvas 点击事件
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        
        # 存储 Canvas 上的图标引用
        self.canvas_items = []
        self.selected_items = set()
        
    def highlight_view_button(self, view_mode):
        """高亮当前选中的视图按钮"""
        for mode, btn in self.view_buttons.items():
            if mode == view_mode:
                btn.config(bg="#0067c0", fg="white")
            else:
                btn.config(bg="#f0f0f0", fg="black")
    
    def switch_view(self, view_mode):
        """切换视图模式"""
        self.current_view = view_mode
        self.highlight_view_button(view_mode)
        self.refresh_display()
    
    def refresh_display(self):
        """刷新显示"""
        # 隐藏所有视图
        self.canvas_frame.pack_forget()
        self.tree_frame.pack_forget()
        
        # 根据视图模式显示相应界面
        if self.current_view in [self.VIEW_LARGE_ICON, self.VIEW_SMALL_ICON]:
            self.show_icon_view()
        else:
            self.show_tree_view()
    
    def show_icon_view(self):
        """显示图标视图（大图标或小图标）"""
        self.canvas_frame.pack(fill="both", expand=True)
        self.v_scrollbar.pack(side="right", fill="y")
        self.h_scrollbar.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # 清空 Canvas
        self.canvas.delete("all")
        self.canvas_items = []
        
        # 确定图标大小
        if self.current_view == self.VIEW_LARGE_ICON:
            icon_size = 128
            text_width = 140
            items_per_row = max(1, self.canvas.winfo_width() // text_width)
        else:
            icon_size = 48
            text_width = 200
            items_per_row = max(1, self.canvas.winfo_width() // text_width)
        
        # 异步加载缩略图
        threading.Thread(target=self.load_thumbnails_async, 
                        args=(icon_size,), daemon=True).start()
    
    def load_thumbnails_async(self, icon_size):
        """异步加载缩略图"""
        filtered_files = self.get_filtered_files()
        
        for i, file_info in enumerate(filtered_files):
            thumb = self.get_thumbnail(file_info['path'], icon_size)
            
            if thumb:
                self.parent.after(0, lambda t=thumb, idx=i, fs=icon_size: 
                                  self.draw_thumbnail(t, idx, fs))
    
    def draw_thumbnail(self, thumbnail, index, icon_size):
        """在 Canvas 上绘制缩略图"""
        if self.current_view not in [self.VIEW_LARGE_ICON, self.VIEW_SMALL_ICON]:
            return
        
        files = self.get_filtered_files()
        if index >= len(files):
            return
        
        file_info = files[index]
        
        # 计算位置
        if self.current_view == self.VIEW_LARGE_ICON:
            items_per_row = max(1, self.canvas.winfo_width() // 150)
            x = (index % items_per_row) * 150 + 75
            y = (index // items_per_row) * 180 + 10
            img_y = y + 10
            text_y = y + 145
            max_text_width = 140
        else:
            items_per_row = max(1, self.canvas.winfo_width() // 220)
            x = (index % items_per_row) * 220 + 10
            y = (index // items_per_row) * 60 + 10
            img_y = y + 5
            text_y = y + 30
            max_text_width = 200
        
        # 创建图片
        img_id = self.canvas.create_image(x, img_y, image=thumbnail, anchor="n")
        
        # 截断文件名
        filename = file_info['name']
        if len(filename) > 20:
            filename = filename[:17] + "..."
        
        # 创建文字标签
        text_id = self.canvas.create_text(x, text_y, text=filename, 
                                         anchor="n", width=max_text_width)
        
        # 存储项目信息
        item_id = f"item_{index}"
        self.canvas_items.append({
            'id': item_id,
            'index': index,
            'img_id': img_id,
            'text_id': text_id,
            'file_info': file_info,
            'thumbnail': thumbnail
        })
        
        # 更新滚动区域
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)
    
    def show_tree_view(self):
        """显示树形视图（列表或详细信息）"""
        self.tree_frame.pack(fill="both", expand=True)
        self.tree_v_scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        
        # 清空 Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 配置列
        if self.current_view == self.VIEW_LIST:
            self.tree["columns"] = ("size",)
            self.tree.heading("#0", text="文件名")
            self.tree.heading("size", text="大小")
            self.tree.column("#0", width=400)
            self.tree.column("size", width=100, anchor="e")
        else:  # VIEW_DETAILS
            self.tree["columns"] = ("type", "size", "modified", "path")
            self.tree.heading("#0", text="文件名")
            self.tree.heading("type", text="类型")
            self.tree.heading("size", text="大小")
            self.tree.heading("modified", text="修改时间")
            self.tree.heading("path", text="路径")
            self.tree.column("#0", width=200)
            self.tree.column("type", width=80)
            self.tree.column("size", width=100, anchor="e")
            self.tree.column("modified", width=150)
            self.tree.column("path", width=400)
        
        # 填充数据
        for file_info in self.get_filtered_files():
            if self.current_view == self.VIEW_LIST:
                self.tree.insert("", "end", text=file_info['name'],
                               values=(file_info['display_size'],))
            else:
                import time
                modified = time.strftime("%Y-%m-%d %H:%M", 
                                        time.localtime(file_info.get('mtime', 0)))
                self.tree.insert("", "end", text=file_info['name'],
                               values=(file_info['type'], file_info['display_size'],
                                      modified, file_info['path']))
    
    def get_thumbnail(self, filepath, size):
        """获取缩略图，支持缓存"""
        cache_key = f"{filepath}_{size}"
        if cache_key in self.thumbnail_cache:
            return self.thumbnail_cache[cache_key]
        
        try:
            ext = os.path.splitext(filepath)[1].lower()
            
            # 图片文件 - 生成缩略图
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif']:
                img = Image.open(filepath)
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                
                # 转换为 RGB 模式（处理透明通道）
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode in ('RGBA', 'LA'):
                        background.paste(img, mask=img.split()[-1])
                        img = background
                
                thumbnail = ImageTk.PhotoImage(img)
                self.thumbnail_cache[cache_key] = thumbnail
                return thumbnail
            
            # 视频文件 - 使用默认图标
            else:
                return self.get_default_icon("video", size)
                
        except Exception as e:
            # 出错时返回默认图标
            return self.get_default_icon("file", size)
    
    def get_default_icon(self, icon_type, size):
        """获取默认图标"""
        cache_key = f"{icon_type}_{size}"
        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]
        
        # 创建默认图标
        if icon_type == "image":
            color = (100, 150, 200)
            text = "IMG"
        elif icon_type == "video":
            color = (200, 100, 100)
            text = "VID"
        else:
            color = (150, 150, 150)
            text = "FILE"
        
        img = Image.new('RGB', (size, size), color)
        thumbnail = ImageTk.PhotoImage(img)
        self.icon_cache[cache_key] = thumbnail
        return thumbnail
    
    def get_filtered_files(self):
        """获取过滤后的文件列表"""
        search_text = self.search_var.get().lower()
        if not search_text:
            return self.media_files
        
        return [f for f in self.media_files 
                if search_text in f['name'].lower()]
    
    def filter_files(self):
        """根据搜索条件过滤文件"""
        self.refresh_display()
    
    def set_media_files(self, files):
        """设置媒体文件列表"""
        self.media_files = files
        self.refresh_display()
    
    def on_canvas_click(self, event):
        """处理 Canvas 点击事件"""
        # 获取点击位置的项目
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # 查找点击的项目
        clicked_item = None
        for item in self.canvas_items:
            bbox = self.canvas.bbox(item['img_id'])
            if bbox and bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
                clicked_item = item
                break
        
        if clicked_item:
            if event.state & 0x4:  # Ctrl 键按下
                # 切换选中状态
                if clicked_item['id'] in self.selected_items:
                    self.selected_items.remove(clicked_item['id'])
                    self.canvas.itemconfig(clicked_item['img_id'], outline="")
                else:
                    self.selected_items.add(clicked_item['id'])
            else:
                # 单选
                self.selected_items = {clicked_item['id']}
            
            if self.on_select:
                self.on_select(clicked_item['file_info'])
    
    def on_canvas_double_click(self, event):
        """处理 Canvas 双击事件"""
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        for item in self.canvas_items:
            bbox = self.canvas.bbox(item['img_id'])
            if bbox and bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
                if self.on_double_click:
                    self.on_double_click(item['file_info'])
                break
    
    def on_tree_select(self, event):
        """处理 Treeview 选择事件"""
        if self.on_select:
            selected = self.tree.selection()
            if selected:
                item = self.tree.item(selected[0])
                # 找到对应的文件信息
                for file_info in self.media_files:
                    if file_info['name'] == item['text']:
                        self.on_select(file_info)
                        break
    
    def on_tree_double_click(self, event):
        """处理 Treeview 双击事件"""
        if self.on_double_click:
            selected = self.tree.selection()
            if selected:
                item = self.tree.item(selected[0])
                for file_info in self.media_files:
                    if file_info['name'] == item['text']:
                        self.on_double_click(file_info)
                        break
    
    def destroy(self):
        """清理资源"""
        self.executor.shutdown(wait=False)
