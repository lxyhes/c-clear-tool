"""
媒体文件查看器 - 支持按目录分组展示和文件选择清理
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import threading
from concurrent.futures import ThreadPoolExecutor


class MediaViewer:
    """媒体文件查看器，支持目录分组和文件选择"""
    
    def __init__(self, parent_frame, on_delete_callback=None):
        self.parent = parent_frame
        self.on_delete_callback = on_delete_callback
        
        # 缩略图缓存
        self.thumbnail_cache = {}
        
        # 媒体文件数据 {目录路径: [文件列表]}
        self.media_files_by_dir = {}
        
        # 选中的文件 {文件路径: 是否选中}
        self.selected_files = {}
        

        
        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # 创建UI
        self.setup_ui()
        
    def generate_id(self, path):
        """生成安全的 Treeview ID - 使用路径哈希"""
        import hashlib
        # 使用 MD5 哈希生成唯一 ID，避免特殊字符问题
        hash_id = hashlib.md5(path.encode('utf-8')).hexdigest()[:16]
        return f"id_{hash_id}"
        
    def setup_ui(self):
        """创建用户界面"""
        # 工具栏
        self.toolbar = tk.Frame(self.parent, bg="white")
        self.toolbar.pack(fill="x", pady=(0, 5))
        
        # 全选/取消全选按钮
        self.btn_select_all = tk.Button(self.toolbar, text="✓ 全选", relief="flat", 
                                        bg="#f0f0f0", command=self.select_all)
        self.btn_select_all.pack(side="left", padx=(5, 2))
        
        self.btn_deselect_all = tk.Button(self.toolbar, text="✗ 取消全选", relief="flat", 
                                          bg="#f0f0f0", command=self.deselect_all)
        self.btn_deselect_all.pack(side="left", padx=2)
        
        # 删除按钮
        self.btn_delete = tk.Button(self.toolbar, text="🗑️ 删除选中", relief="flat", 
                                    bg="#d83b01", fg="white", command=self.delete_selected)
        self.btn_delete.pack(side="left", padx=(20, 2))
        
        # 统计标签
        self.lbl_stats = tk.Label(self.toolbar, text="", bg="white", fg="#666")
        self.lbl_stats.pack(side="right", padx=10)
        
        # 搜索框
        tk.Label(self.toolbar, text="搜索:", bg="white").pack(side="left", padx=(20, 2))
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(self.toolbar, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=2)
        tk.Button(self.toolbar, text="🔍", relief="flat", bg="#f0f0f0",
                 command=self.filter_files).pack(side="left", padx=2)
        
        # 创建 Treeview（带复选框和目录分组）
        self.tree_frame = tk.Frame(self.parent)
        self.tree_frame.pack(fill="both", expand=True)
        
        # 创建 Treeview
        self.tree = ttk.Treeview(self.tree_frame, show="tree headings", selectmode="none")
        self.tree_v_scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_v_scrollbar.set)
        
        self.tree_v_scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        
        # 配置列
        self.tree["columns"] = ("type", "size", "path")
        self.tree.heading("#0", text="名称")
        self.tree.heading("type", text="类型")
        self.tree.heading("size", text="大小")
        self.tree.heading("path", text="路径")
        
        self.tree.column("#0", width=300)
        self.tree.column("type", width=60)
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("path", width=400)
        
        # 绑定点击事件（用于复选框）
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        
        # 加载复选框图片
        self.load_checkbox_images()
        
    def load_checkbox_images(self):
        """加载复选框图片"""
        # 创建简单的复选框图片
        size = 16
        
        # 未选中
        img_unchecked = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img_unchecked)
        draw.rectangle([1, 1, size-2, size-2], outline='#666666', width=1)
        self.img_unchecked = ImageTk.PhotoImage(img_unchecked)
        
        # 选中
        img_checked = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img_checked)
        draw.rectangle([1, 1, size-2, size-2], fill='#0067c0', outline='#0067c0', width=1)
        draw.line([(4, 8), (7, 12), (12, 4)], fill='white', width=2)
        self.img_checked = ImageTk.PhotoImage(img_checked)
        
        # 部分选中
        img_partial = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img_partial)
        draw.rectangle([1, 1, size-2, size-2], fill='#999999', outline='#666666', width=1)
        self.img_partial = ImageTk.PhotoImage(img_partial)
        
    def set_media_files(self, files):
        """设置媒体文件列表并按目录分组"""
        # 按目录分组
        self.media_files_by_dir = {}
        for file_info in files:
            dir_path = os.path.dirname(file_info['path'])
            if dir_path not in self.media_files_by_dir:
                self.media_files_by_dir[dir_path] = []
            self.media_files_by_dir[dir_path].append(file_info)
            # 初始化选中状态
            if file_info['path'] not in self.selected_files:
                self.selected_files[file_info['path']] = False
        
        self.refresh_display()
        self.update_stats()
        
    def refresh_display(self):
        """刷新显示"""
        # 清空 Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 按目录添加文件
        for dir_path, files in sorted(self.media_files_by_dir.items()):
            if not files:
                continue
            
            # 计算目录总大小
            total_size = sum(f['size'] for f in files)
            dir_name = os.path.basename(dir_path) or dir_path
            
            # 生成安全的目录 ID
            dir_id = self.generate_id(dir_path)
            
            # 添加目录节点
            dir_node = self.tree.insert("", "end", iid=dir_id, 
                                       text=f"📁 {dir_name} ({len(files)}个文件)",
                                       values=("目录", self.format_size(total_size), dir_path),
                                       tags=("directory", dir_path))
            
            # 添加文件节点
            for idx, file_info in enumerate(files):
                self.add_file_node(dir_node, file_info, idx)
            
            # 自动展开目录
            self.tree.item(dir_node, open=True)
        
        # 更新复选框显示
        self.update_checkboxes()
        
    def add_file_node(self, parent, file_info, index=0):
        """添加文件节点"""
        file_path = file_info['path']
        is_selected = self.selected_files.get(file_path, False)
        
        # 确定图标
        icon = "🖼️" if file_info['type'] == '图片' else "🎬"
        
        # 生成安全的文件 ID
        file_id = self.generate_id(file_path)
        
        # 添加节点
        self.tree.insert(parent, "end", iid=file_id,
                        text=f"{icon} {file_info['name']}",
                        values=(file_info['type'], file_info['display_size'], file_path),
                        tags=("file", file_path))
        
    def update_checkboxes(self):
        """更新所有复选框的显示状态"""
        for item_id in self.tree.get_children():
            self.update_dir_checkbox(item_id)
            
    def update_dir_checkbox(self, dir_item_id):
        """更新目录节点的复选框状态"""
        children = self.tree.get_children(dir_item_id)
        if not children:
            return
        
        # 检查子文件的选中状态
        all_selected = True
        any_selected = False
        
        for child_id in children:
            tags = self.tree.item(child_id, 'tags')
            if tags and len(tags) > 1:
                file_path = tags[1]
                if self.selected_files.get(file_path, False):
                    any_selected = True
                else:
                    all_selected = False
        
        # 设置目录节点的复选框图片
        if all_selected and any_selected:
            self.tree.item(dir_item_id, image=self.img_checked)
        elif any_selected:
            self.tree.item(dir_item_id, image=self.img_partial)
        else:
            self.tree.item(dir_item_id, image=self.img_unchecked)
            
    def on_tree_click(self, event):
        """处理 Treeview 点击事件（复选框）"""
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        
        # 获取列
        column = self.tree.identify_column(event.x)
        
        # 点击第一列（复选框区域）时切换选中状态
        if column == '#0' or column == '':
            self.toggle_item_selection(item_id)
            
    def toggle_item_selection(self, item_id):
        """切换项目的选中状态"""
        tags = self.tree.item(item_id, 'tags')
        
        if not tags:
            return
        
        if tags[0] == "directory":
            # 目录节点 - 切换所有子文件
            children = self.tree.get_children(item_id)
            # 检查当前状态
            current_selected = self.tree.item(item_id, 'image') == self.img_checked
            new_state = not current_selected
            
            for child_id in children:
                child_tags = self.tree.item(child_id, 'tags')
                if child_tags and len(child_tags) > 1:
                    file_path = child_tags[1]
                    self.selected_files[file_path] = new_state
                    
        elif tags[0] == "file":
            # 文件节点
            file_path = tags[1]
            self.selected_files[file_path] = not self.selected_files.get(file_path, False)
        
        # 刷新显示
        self.refresh_display()
        self.update_stats()
        
    def on_tree_double_click(self, event):
        """处理 Treeview 双击事件 - 打开文件位置"""
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        
        tags = self.tree.item(item_id, 'tags')
        if not tags:
            return
        
        if tags[0] == "file":
            file_path = tags[1]
            if os.path.exists(file_path):
                import subprocess
                subprocess.run(['explorer', '/select,', file_path])
        elif tags[0] == "directory":
            # 从 tags 中获取目录路径
            dir_path = tags[1]
            if os.path.exists(dir_path):
                os.startfile(dir_path)
                
    def select_all(self):
        """全选所有文件"""
        for file_path in self.selected_files:
            self.selected_files[file_path] = True
        self.refresh_display()
        self.update_stats()
        
    def deselect_all(self):
        """取消全选"""
        for file_path in self.selected_files:
            self.selected_files[file_path] = False
        self.refresh_display()
        self.update_stats()
        
    def get_selected_files(self):
        """获取选中的文件列表"""
        return [path for path, selected in self.selected_files.items() if selected]
        
    def update_stats(self):
        """更新统计信息"""
        selected_count = sum(1 for selected in self.selected_files.values() if selected)
        selected_size = sum(file_info['size'] 
                          for dir_files in self.media_files_by_dir.values() 
                          for file_info in dir_files 
                          if self.selected_files.get(file_info['path'], False))
        
        self.lbl_stats.config(text=f"选中: {selected_count} 个文件 ({self.format_size(selected_size)})")
        
    def delete_selected(self):
        """删除选中的文件"""
        selected_files = self.get_selected_files()
        
        if not selected_files:
            messagebox.showwarning("提示", "请先选择要删除的文件")
            return
        
        total_size = sum(os.path.getsize(f) for f in selected_files if os.path.exists(f))
        
        if messagebox.askyesno("确认删除", 
                              f"确定要删除选中的 {len(selected_files)} 个文件吗？\n"
                              f"总大小: {self.format_size(total_size)}\n\n"
                              f"此操作不可恢复！"):
            
            deleted_count = 0
            failed_files = []
            
            for file_path in selected_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        deleted_count += 1
                        # 从数据结构中移除
                        self.selected_files.pop(file_path, None)
                except Exception as e:
                    failed_files.append((file_path, str(e)))
            
            # 刷新显示
            self.refresh_file_list()
            
            if failed_files:
                messagebox.showwarning("删除完成", 
                                      f"成功删除 {deleted_count} 个文件\n"
                                      f"失败 {len(failed_files)} 个文件")
            else:
                messagebox.showinfo("删除完成", f"成功删除 {deleted_count} 个文件")
            
            # 调用回调函数
            if self.on_delete_callback:
                self.on_delete_callback()
                
    def refresh_file_list(self):
        """刷新文件列表（删除后重新扫描）"""
        # 移除不存在的文件
        for dir_path in list(self.media_files_by_dir.keys()):
            self.media_files_by_dir[dir_path] = [
                f for f in self.media_files_by_dir[dir_path] 
                if os.path.exists(f['path'])
            ]
            if not self.media_files_by_dir[dir_path]:
                del self.media_files_by_dir[dir_path]
        
        self.refresh_display()
        self.update_stats()
        
    def filter_files(self):
        """根据搜索条件过滤文件"""
        search_text = self.search_var.get().lower()
        
        if not search_text:
            self.refresh_display()
            return
        
        # 清空 Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 过滤并显示
        for dir_path, files in sorted(self.media_files_by_dir.items()):
            filtered_files = [f for f in files if search_text in f['name'].lower()]
            if not filtered_files:
                continue
            
            total_size = sum(f['size'] for f in filtered_files)
            dir_name = os.path.basename(dir_path) or dir_path
            
            dir_node = self.tree.insert("", "end", iid=dir_path,
                                       text=f"📁 {dir_name} ({len(filtered_files)}个文件)",
                                       values=("目录", self.format_size(total_size), dir_path),
                                       tags=("directory",))
            
            for file_info in filtered_files:
                self.add_file_node(dir_node, file_info)
        
        self.update_checkboxes()
        
    def format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"
        
    def destroy(self):
        """清理资源"""
        self.executor.shutdown(wait=False)
        # 销毁所有创建的 widget
        if hasattr(self, 'toolbar') and self.toolbar:
            self.toolbar.destroy()
        if hasattr(self, 'tree_frame') and self.tree_frame:
            self.tree_frame.destroy()