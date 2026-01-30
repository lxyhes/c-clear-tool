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
    
    def add_record(self, mode, freed_size, items_count, details=None):
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "freed_size": freed_size,
            "items_count": items_count,
            "details": details or []
        }
        self.history["records"].insert(0, record)
        self.history["total_freed"] += freed_size
        self.history["total_items"] += items_count
        # 只保留最近100条记录
        if len(self.history["records"]) > 100:
            self.history["records"] = self.history["records"][:100]
        self.save()
        return record
    
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
