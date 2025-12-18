import os
import time
import winreg
import ctypes
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import format_size

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

    def scan_generator(self):
        # 1. 回收站
        try:
            rb_size = 0
            for drive in range(ord('C'), ord('Z')+1):
                root = f"{chr(drive)}:\$Recycle.Bin"
                if os.path.exists(root): rb_size += self.get_dir_size_fast(root)
            if rb_size > 0:
                yield {"type": "item", "data": {"cat": "特别清理", "soft": "回收站", "detail": "已删除文件", "path": "RECYCLE_BIN_SPECIAL", "raw_size": rb_size, "display_size": format_size(rb_size)}}
        except: pass

        for item in self.base_targets:
            yield {"type": "status", "msg": f"正在扫描: {item['path']}"}
            if os.path.exists(item['path']):
                s = self.get_dir_size_fast(item['path'])
                if s > 0: yield {"type": "item", "data": {"cat": item['cat'], "soft": item['soft'], "detail": item['name'], "path": item['path'], "raw_size": s, "display_size": format_size(s)}}
        
        # AppData 并行扫描
        roots = [self.local_appdata, self.roaming_appdata]
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(self._scan_appdata_root, r) for r in roots]
            for fut in as_completed(futures):
                for r in fut.result(): yield r

    def _scan_appdata_root(self, root):
        res = []
        if not os.path.exists(root): return res
        try:
            with os.scandir(root) as it:
                for entry in it:
                    if not entry.is_dir(): continue
                    try:
                        for dp, dn, fn in os.walk(entry.path):
                            if dp.count(os.sep) - entry.path.count(os.sep) > 3: dn[:]=[]; continue
                            cur = os.path.basename(dp).lower()
                            if any(k in cur for k in self.safe_keywords) and not any(k in cur for k in self.danger_keywords):
                                cat, soft = self.infer_info(entry.name, dp)
                                s = self.get_dir_size_fast(dp)
                                if s > 0:
                                    res.append({"type": "item", "data": {"cat": cat, "soft": soft, "detail": os.path.basename(dp), "path": dp, "raw_size": s, "display_size": format_size(s)}})
                                dn[:] = []
                    except: pass
        except: pass
        return res

    def scan_social_apps(self):
        """优化版：多线程并发扫描社交软件目录"""
        search_paths = []
        # 1. 注册表
        for reg_path, key_name, label in [
            (r"Software\Tencent\WeChat", "FileSavePath", "微信 WeChat"),
            (r"Software\Tencent\QQ2012", "UserDataSavePath", "腾讯 QQ")
        ]:
            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ)
                path, _ = winreg.QueryValueEx(k, key_name)
                if path and os.path.exists(path): search_paths.append((label, path))
                winreg.CloseKey(k)
            except: pass

        # 2. 自动探测
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if bitmask & (1 << i):
                d = f"{chr(ord('A') + i)}:\"
                if ctypes.windll.kernel32.GetDriveTypeW(d) == 3: drives.append(d)

        buf = ctypes.create_unicode_buffer(1024)
        ctypes.windll.shell32.SHGetSpecialFolderPathW(None, buf, 0x0005, False)
        common_bases = [buf.value, os.path.join(os.environ['APPDATA'], "Tencent")]
        
        for d in drives:
            for s in ["Cache", "WeChat Files", "Tencent Files"]:
                p = os.path.join(d, s)
                if os.path.exists(p): common_bases.append(p)

        social_targets = [
            {"name": "微信 WeChat", "root_names": ["WeChat Files", "WeChat"], "junk_subs": ["FileStorage\Cache", "FileStorage\Image", "FileStorage\Video", "FileStorage\File", "FileStorage\CustomEmoji"]},
            {"name": "腾讯 QQ", "root_names": ["Tencent Files", "TencentFiles", "QQ"], "junk_subs": ["Image", "Video", "File", "Audio", "Cache"]}
        ]

        for base in set(common_bases):
            for target in social_targets:
                for r_name in target['root_names']:
                    full = os.path.join(base, r_name)
                    if os.path.exists(full): search_paths.append((target['name'], full))
        
        unique_tasks = {}
        for name, path in search_paths:
            if path not in unique_tasks: unique_tasks[path] = name

        # 核心优化：并发分析所有找到的社交根目录
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self._analyze_social_root, path, name, social_targets) for path, name in unique_tasks.items()]
            for fut in as_completed(futures):
                for item in fut.result(): yield item

    def _analyze_social_root(self, root, name, targets):
        res = []
        target = next((t for t in targets if t['name'] == name), None)
        if not target: return res
        try:
            with os.scandir(root) as it:
                for entry in it:
                    if entry.is_dir() and entry.name not in ["All Users", "Applet", "config"]:
                        for sub in target['junk_subs']:
                            full_sub = os.path.join(entry.path, sub)
                            if os.path.exists(full_sub):
                                s = self.get_dir_size_fast(full_sub)
                                if s > 0:
                                    res.append({"type": "item", "data": {
                                        "cat": target['name'], "soft": entry.name,
                                        "detail": sub.split('\\')[-1], "path": full_sub, 
                                        "raw_size": s, "display_size": format_size(s)
                                    }})
        except: pass
        return res

    def scan_custom(self, paths):
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(self._scan_single_custom, p) for p in paths]
            for fut in as_completed(futures):
                for item in fut.result(): yield item

    def _scan_single_custom(self, base):
        res = []
        if not os.path.exists(base): return res
        try:
            for root, dirs, files in os.walk(base):
                if root.count(os.sep) - base.count(os.sep) > 3: dirs[:] = []; continue
                cur_name = os.path.basename(root).lower()
                if any(k in cur_name for k in self.safe_keywords) and not any(k in cur_name for k in self.danger_keywords):
                    s = self.get_dir_size_fast(root)
                    if s > 0:
                        res.append({"type": "item", "data": {
                            "cat": "自定义目录", "soft": os.path.basename(base),
                            "detail": os.path.relpath(root, base), "path": root,
                            "raw_size": s, "display_size": format_size(s)
                        }})
                        dirs[:] = []
        except: pass
        return res

    def scan_installers(self):
        if not os.path.exists(self.downloads): return
        exts = {'.exe', '.msi', '.iso', '.zip', '.rar', '.7z'}
        now = time.time()
        try:
            with os.scandir(self.downloads) as it:
                for entry in it:
                    if entry.is_file() and os.path.splitext(entry.name)[1].lower() in exts:
                        st = entry.stat()
                        if now - st.st_mtime > 30 * 86400:
                            yield {"type": "item", "data": {"name": entry.name, "path": entry.path, "raw_size": st.st_size, "date": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"), "display_size": format_size(st.st_size)}}
        except: pass

    def scan_large_files(self):
        dirs = [os.path.join(self.user_profile, d) for d in ["Downloads", "Desktop", "Documents", "Videos", "Pictures"]]
        for d in dirs:
            if not os.path.exists(d): continue
            for r, ds, fs in os.walk(d):
                if os.path.basename(r).startswith('.'): ds[:] = []; continue
                for f in fs:
                    fp = os.path.join(r, f)
                    try:
                        sz = os.path.getsize(fp)
                        if sz > 100 * 1024 * 1024: 
                            yield {"type": "item", "data": {"name": f, "path": fp, "raw_size": sz, "display_size": format_size(sz)}}
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
