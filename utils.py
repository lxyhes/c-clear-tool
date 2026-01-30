import os
import ctypes
import sys
import json
from datetime import datetime

# --- 现代彩色 3D 符号库 (高清 3D 渲染) ---
ICONS = {
    'clean': "🧹",
    'chat': "💬",
    'fire': "🔥",
    'folder': "📁",
    'box': "📦",
    'search': "🔎",
    'sys': "💻",
    'app': "🧩",
    'bin': "🗑️",
    'secure': "🛡️",
    'mail': "📧",
    'key': "🔑",
    'cmd': "⌨️",
    'cloud': "☁️",
    'report': "📋",
    'shield': "🎖️",
    'history': "📊",
    'timer': "⏰",
    'backup': "💾",
    'config': "⚙️",
    'music': "🎵",
    'dev': "🛠️",
    'docker': "🐳",
    'npm': "📦",
    'chart': "📈",
    'lock': "🔒",
    'game': "🎮",
    'phone': "📱",
    'link': "🔗",
    'empty': "📂",
    'duplicate': "🔄",
    'clipboard': "📋",
    'browser': "🌐",
    # 新增分类图标
    'video': "🎬",
    'download': "⬇️",
    'tool': "🔧",
    'office': "📄",
    'security': "🔐"
}

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def get_icons():
    return ICONS

def format_time(seconds):
    """格式化剩余时间"""
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        return f"{int(seconds // 60)}分{int(seconds % 60)}秒"
    else:
        return f"{int(seconds // 3600)}时{int((seconds % 3600) // 60)}分"

# --- 清理历史记录管理 ---
class CleanHistory:
    def __init__(self):
        self.history_file = os.path.join(os.environ['USERPROFILE'], '.ccleaner_history.json')
        self.history = self.load()
    
    def load(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {"records": [], "total_freed": 0, "total_items": 0}
    
    def save(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except: pass
    
    def add_record(self, mode, freed_size, items_count, details=None, backup_path=None):
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "freed_size": freed_size,
            "items_count": items_count,
            "details": details or [],
            "backup_path": backup_path,  # 备份文件路径，用于恢复
            "restorable": backup_path is not None
        }
        self.history["records"].insert(0, record)
        self.history["total_freed"] += freed_size
        self.history["total_items"] += items_count
        # 只保留最近100条记录
        if len(self.history["records"]) > 100:
            self.history["records"] = self.history["records"][:100]
        self.save()
        return record

    def get_restorable_records(self):
        """获取可恢复的记录"""
        return [r for r in self.history["records"] if r.get("restorable", False) and r.get("backup_path")]
    
    def get_records(self, limit=20):
        return self.history["records"][:limit]
    
    def get_stats(self):
        return {
            "total_freed": self.history["total_freed"],
            "total_items": self.history["total_items"],
            "record_count": len(self.history["records"])
        }
    
    def get_trend_data(self, days=30):
        """获取最近N天的清理趋势数据"""
        from collections import defaultdict
        daily = defaultdict(lambda: {"size": 0, "count": 0})
        for r in self.history["records"]:
            date = r["time"].split(" ")[0]
            daily[date]["size"] += r["freed_size"]
            daily[date]["count"] += r["items_count"]
        return dict(daily)

# --- 配置管理 ---
class ConfigManager:
    def __init__(self):
        self.config_file = os.path.join(os.environ['USERPROFILE'], '.ccleaner_config.json')
        self.config = self.load()
    
    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {
            "custom_paths": [],
            "schedule": {"enabled": False, "interval": "weekly", "day": 0, "hour": 3},
            "backup": {"enabled": False, "path": ""},
            "last_scan": None
        }
    
    def save(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except: pass
    
    def export_config(self, path):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except: return False
    
    def import_config(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                imported = json.load(f)
                self.config.update(imported)
                self.save()
            return True
        except: return False

# --- 备份管理 ---
class BackupManager:
    def __init__(self):
        self.backup_dir = os.path.join(os.environ['USERPROFILE'], 'CCleaner_Backups')
    
    def create_backup(self, paths, callback=None):
        """创建备份压缩包"""
        import zipfile
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"backup_{timestamp}.zip")
        
        try:
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i, path in enumerate(paths):
                    if callback: callback(i + 1, len(paths), os.path.basename(path))
                    if os.path.isfile(path):
                        zf.write(path, os.path.basename(path))
                    elif os.path.isdir(path):
                        for root, dirs, files in os.walk(path):
                            for file in files:
                                fp = os.path.join(root, file)
                                arcname = os.path.relpath(fp, os.path.dirname(path))
                                try: zf.write(fp, arcname)
                                except: pass
            return backup_path
        except Exception as e:
            return None
    
    def list_backups(self):
        if not os.path.exists(self.backup_dir): return []
        backups = []
        for f in os.listdir(self.backup_dir):
            if f.endswith('.zip'):
                fp = os.path.join(self.backup_dir, f)
                backups.append({
                    "name": f,
                    "path": fp,
                    "size": os.path.getsize(fp),
                    "time": datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M")
                })
        return sorted(backups, key=lambda x: x["time"], reverse=True)

# --- 文件类型分析 ---
class FileAnalyzer:
    """文件类型统计分析"""
    
    FILE_TYPES = {
        '文档': ['.doc', '.docx', '.pdf', '.txt', '.rtf', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp'],
        '图片': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.psd', '.ai'],
        '视频': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.rmvb'],
        '音频': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.ape'],
        '压缩包': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.iso'],
        '安装包': ['.exe', '.msi', '.apk', '.dmg', '.deb', '.rpm'],
        '代码': ['.py', '.js', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt'],
        '数据库': ['.db', '.sqlite', '.mdb', '.accdb'],
        '其他': []
    }
    
    TYPE_COLORS = {
        '文档': '#4472C4',
        '图片': '#FFC000',
        '视频': '#ED7D31',
        '音频': '#70AD47',
        '压缩包': '#5B9BD5',
        '安装包': '#C55A11',
        '代码': '#264478',
        '数据库': '#A5A5A5',
        '其他': '#999999'
    }
    
    @classmethod
    def get_file_type(cls, filename):
        """获取文件类型"""
        ext = os.path.splitext(filename)[1].lower()
        for type_name, extensions in cls.FILE_TYPES.items():
            if ext in extensions:
                return type_name
        return '其他'
    
    @classmethod
    def analyze_files(cls, files):
        """分析文件类型统计"""
        stats = {}
        total_size = 0
        for f in files:
            file_type = cls.get_file_type(f.get('name', ''))
            size = f.get('size', 0)
            if file_type not in stats:
                stats[file_type] = {'count': 0, 'size': 0}
            stats[file_type]['count'] += 1
            stats[file_type]['size'] += size
            total_size += size
        
        # 转换为列表并按大小排序
        result = []
        for type_name, data in stats.items():
            result.append({
                'type': type_name,
                'count': data['count'],
                'size': data['size'],
                'percent': round(data['size'] / total_size * 100, 2) if total_size > 0 else 0,
                'color': cls.TYPE_COLORS.get(type_name, '#999999')
            })
        return sorted(result, key=lambda x: x['size'], reverse=True)

# --- 白名单管理 ---
class WhitelistManager:
    """白名单管理器"""
    
    def __init__(self):
        self.whitelist_file = os.path.join(os.environ['USERPROFILE'], '.ccleaner_whitelist.json')
        self.whitelist = self.load()
    
    def load(self):
        """加载白名单"""
        if os.path.exists(self.whitelist_file):
            try:
                with open(self.whitelist_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {
            'paths': [],
            'patterns': [
                '*.backup',
                '*.bak',
                '*_backup',
                '重要文档',
                'backup',
                'important'
            ],
            'extensions': [
                '.backup',
                '.bak',
                '.save'
            ]
        }
    
    def save(self):
        """保存白名单"""
        try:
            with open(self.whitelist_file, 'w', encoding='utf-8') as f:
                json.dump(self.whitelist, f, ensure_ascii=False, indent=2)
        except: pass
    
    def is_whitelisted(self, path):
        """检查路径是否在白名单中"""
        # 检查完整路径
        if path in self.whitelist['paths']:
            return True
        
        # 检查父目录
        for wp in self.whitelist['paths']:
            if path.startswith(wp + os.sep) or wp.startswith(path + os.sep):
                return True
        
        # 检查文件名模式
        filename = os.path.basename(path)
        for pattern in self.whitelist['patterns']:
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return True
        
        # 检查扩展名
        ext = os.path.splitext(path)[1].lower()
        if ext in self.whitelist['extensions']:
            return True
        
        return False
    
    def add_path(self, path):
        """添加路径到白名单"""
        if path not in self.whitelist['paths']:
            self.whitelist['paths'].append(path)
            self.save()
    
    def remove_path(self, path):
        """从白名单移除路径"""
        if path in self.whitelist['paths']:
            self.whitelist['paths'].remove(path)
            self.save()
    
    def add_pattern(self, pattern):
        """添加文件名模式"""
        if pattern not in self.whitelist['patterns']:
            self.whitelist['patterns'].append(pattern)
            self.save()

# 扩展导入 fnmatch
import fnmatch

# --- 智能推荐引擎 ---
class RecommendationEngine:
    """基于清理历史的智能推荐引擎"""
    
    def __init__(self, history_mgr):
        self.history = history_mgr
    
    def get_recommendations(self, cleaner):
        """获取清理推荐"""
        recommendations = []
        
        # 1. 基于历史记录的推荐
        records = self.history.get_records(20)
        if records:
            # 统计最常清理的模式
            mode_count = {}
            for r in records:
                mode = r['mode']
                if mode not in mode_count:
                    mode_count[mode] = {'count': 0, 'freed': 0}
                mode_count[mode]['count'] += 1
                mode_count[mode]['freed'] += r['freed_size']
            
            # 推荐清理次数多且释放空间多的模式
            for mode, data in sorted(mode_count.items(), key=lambda x: -x[1]['count']):
                if data['count'] >= 2:
                    recommendations.append({
                        'type': 'frequent_clean',
                        'mode': mode,
                        'priority': 'high',
                        'reason': f"最近已清理 {data['count']} 次，累计释放 {format_size(data['freed'])}",
                        'icon': '🔄'
                    })
        
        # 2. 检查系统临时文件
        import os
        temp_size = 0
        temp_paths = [os.environ['TEMP'], os.path.join(os.environ['SystemRoot'], 'Temp')]
        for p in temp_paths:
            if os.path.exists(p):
                try:
                    for item in os.listdir(p):
                        item_path = os.path.join(p, item)
                        try:
                            if os.path.isfile(item_path):
                                temp_size += os.path.getsize(item_path)
                        except: pass
                except: pass
        
        if temp_size > 500 * 1024 * 1024:  # 超过500MB
            recommendations.append({
                'type': 'temp_files',
                'mode': 'junk',
                'priority': 'medium',
                'reason': f"系统临时文件占用 {format_size(temp_size)}",
                'icon': '🗑️'
            })
        
        # 3. 检查下载文件夹中的安装包
        downloads = os.path.join(os.environ['USERPROFILE'], 'Downloads')
        if os.path.exists(downloads):
            installer_count = 0
            installer_size = 0
            installer_exts = ['.exe', '.msi', '.iso']
            try:
                for f in os.listdir(downloads):
                    if os.path.splitext(f)[1].lower() in installer_exts:
                        fp = os.path.join(downloads, f)
                        try:
                            s = os.path.getsize(fp)
                            installer_size += s
                            installer_count += 1
                        except: pass
            except: pass
            
            if installer_count > 0 and installer_size > 100 * 1024 * 1024:
                recommendations.append({
                    'type': 'installers',
                    'mode': 'inst',
                    'priority': 'low',
                    'reason': f"发现 {installer_count} 个安装包，占用 {format_size(installer_size)}",
                    'icon': '📦'
                })
        
        # 4. 检查回收站
        try:
            rb_size = 0
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if bitmask & (1 << i):
                    drive = chr(ord('A') + i) + ":/"
                    rb_path = os.path.join(drive, "$Recycle.Bin")
                    if os.path.exists(rb_path):
                        try:
                            for root, dirs, files in os.walk(rb_path):
                                for f in files:
                                    try:
                                        fp = os.path.join(root, f)
                                        rb_size += os.path.getsize(fp)
                                    except: pass
                        except: pass
            
            if rb_size > 500 * 1024 * 1024:
                recommendations.append({
                    'type': 'recycle_bin',
                    'mode': 'junk',
                    'priority': 'medium',
                    'reason': f"回收站占用 {format_size(rb_size)}",
                    'icon': '♻️'
                })
        except: pass
        
        return recommendations[:10]  # 最多返回10条推荐

# --- 扫描结果缓存 ---
class ScanCache:
    """扫描结果缓存管理器"""
    
    def __init__(self):
        self.cache_file = os.path.join(os.environ['USERPROFILE'], '.ccleaner_scan_cache.json')
        self.cache_data = self.load()
        self.cache_ttl = 3600  # 缓存有效期1小时
    
    def load(self):
        """加载缓存数据"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 清理过期缓存
                    current_time = time.time()
                    valid_cache = {}
                    for key, value in data.items():
                        if current_time - value.get('timestamp', 0) < 3600:  # 1小时内有效
                            valid_cache[key] = value
                    return valid_cache
            except: pass
        return {}
    
    def save(self):
        """保存缓存数据"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
        except: pass
    
    def get(self, mode, key=""):
        """获取缓存数据"""
        cache_key = f"{mode}_{key}"
        if cache_key in self.cache_data:
            cache_entry = self.cache_data[cache_key]
            # 检查是否过期
            if time.time() - cache_entry.get('timestamp', 0) < self.cache_ttl:
                return cache_entry.get('data')
            else:
                # 删除过期缓存
                del self.cache_data[cache_key]
                self.save()
        return None
    
    def set(self, mode, key="", data=None):
        """设置缓存数据"""
        cache_key = f"{mode}_{key}"
        self.cache_data[cache_key] = {
            'timestamp': time.time(),
            'data': data or []
        }
        self.save()
    
    def clear(self, mode=None):
        """清除缓存"""
        if mode:
            # 清除特定模式的缓存
            keys_to_remove = [k for k in self.cache_data.keys() if k.startswith(f"{mode}_")]
            for key in keys_to_remove:
                del self.cache_data[key]
        else:
            # 清除所有缓存
            self.cache_data = {}
        self.save()
    
    def get_cache_info(self):
        """获取缓存信息"""
        current_time = time.time()
        info = {
            'total_entries': len(self.cache_data),
            'valid_entries': 0,
            'expired_entries': 0,
            'total_size': 0
        }
        
        for key, value in self.cache_data.items():
            if current_time - value.get('timestamp', 0) < self.cache_ttl:
                info['valid_entries'] += 1
            else:
                info['expired_entries'] += 1
            info['total_size'] += len(str(value))
        
        return info
