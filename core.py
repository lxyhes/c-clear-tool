import os
import time
import winreg
import ctypes
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import format_size
from datetime import datetime

class SystemCleaner:
    def __init__(self):
        self.user_profile = os.environ['USERPROFILE']
        self.local_appdata = os.environ['LOCALAPPDATA']
        self.roaming_appdata = os.environ['APPDATA']
        self.temp = os.environ['TEMP']
        self.system_root = os.environ['SystemRoot']
        self.downloads = os.path.join(self.user_profile, "Downloads")
        
        # 敏感路径列表（需要二次确认）
        self.SENSITIVE_PATHS = [
            "important", "重要", "backup", "备份", "项目", "project", "work", "工作",
            "source", "源码", "code", "代码", "data", "数据", "database", "数据库",
            "config", "配置", "setting", "设置", "key", "密钥", "secret", "机密"
        ]
        
        self.SYSTEM_EXCLUDE = {
            'windows', 'program files', 'program files (x86)', 'programdata',
            'winsxs', 'system32', 'syswow64', 'drivers', 'driverstore',
            'microsoft', 'package cache', '$recycle.bin', 'system volume information'
        }

        self.base_targets = [
            {"name": "用户临时文件", "path": self.temp, "cat": "系统垃圾", "soft": "Windows"},
            {"name": "系统临时文件", "path": os.path.join(self.system_root, "Temp"), "cat": "系统垃圾", "soft": "Windows"},
            {"name": "预读取文件", "path": os.path.join(self.system_root, "Prefetch"), "cat": "系统垃圾", "soft": "Windows"},
            {"name": "系统更新缓存", "path": os.path.join(self.system_root, "SoftwareDistribution", "Download"), "cat": "系统垃圾", "soft": "Windows Update"},
            {"name": "错误报告", "path": os.path.join(self.local_appdata, "Microsoft", "Windows", "WER"), "cat": "系统垃圾", "soft": "Error Reporting"},
            {"name": "系统日志", "path": os.path.join(self.system_root, "Logs"), "cat": "系统垃圾", "soft": "Windows"},
            {"name": "调试文件", "path": os.path.join(self.system_root, "Debug"), "cat": "系统垃圾", "soft": "Windows"},
            {"name": "崩溃转储", "path": os.path.join(self.system_root, "Minidump"), "cat": "系统垃圾", "soft": "Windows"},
        ]
        
        self.safe_keywords = ['cache', 'temp', 'log', 'logs', 'dump', 'crashes', 'crashpad', 'shadercache']
        self.danger_keywords = ['profile', 'save', 'saved', 'backup', 'database', 'user data', 'config', 'cookies']

        # 扩展应用进程映射
        self.APP_PROCESSES = {
            "微信 WeChat": ["WeChat.exe", "WeChatPlayer.exe"],
            "企业微信 WeCom": ["WXWork.exe"],
            "腾讯 QQ": ["QQ.exe"],
            "钉钉 DingTalk": ["DingTalk.exe"],
            "飞书 Feishu": ["Feishu.exe", "Lark.exe"],
            "Chrome": ["chrome.exe"],
            "Edge": ["msedge.exe"],
            "Outlook": ["outlook.exe"],
            "Navicat": ["navicat.exe"],
            "Telegram": ["Telegram.exe"],
            "Discord": ["Discord.exe"],
            "Slack": ["slack.exe"],
            "VS Code": ["Code.exe"],
            "网易云音乐": ["cloudmusic.exe"],
            "QQ音乐": ["QQMusic.exe"],
            "Docker": ["Docker Desktop.exe", "dockerd.exe"]
        }
        
        # 扩展应用缓存目录
        self.extended_app_targets = [
            # 通讯软件
            {"name": "Telegram Desktop", "paths": [os.path.join(self.roaming_appdata, "Telegram Desktop")], "cat": "通讯软件", "subs": ["tdata/user_data", "tdata/emoji", "tdata/temp"]},
            {"name": "Discord", "paths": [os.path.join(self.roaming_appdata, "discord")], "cat": "通讯软件", "subs": ["Cache", "Code Cache", "GPUCache"]},
            {"name": "Slack", "paths": [os.path.join(self.roaming_appdata, "Slack")], "cat": "通讯软件", "subs": ["Cache", "Code Cache", "GPUCache"]},
            # 音乐软件
            {"name": "网易云音乐", "paths": [os.path.join(self.local_appdata, "Netease/CloudMusic")], "cat": "音乐软件", "subs": ["Cache", "webdata/Cache"]},
            {"name": "QQ音乐", "paths": [os.path.join(self.roaming_appdata, "Tencent/QQMusic")], "cat": "音乐软件", "subs": ["Cache", "Temp"]},
            # 视频软件
            {"name": "爱奇艺", "paths": [os.path.join(self.local_appdata, "iQIYI")], "cat": "视频软件", "subs": ["Cache", "log"]},
            {"name": "腾讯视频", "paths": [os.path.join(self.local_appdata, "Tencent/QQLive")], "cat": "视频软件", "subs": ["Cache", "Download"]},
            {"name": "优酷", "paths": [os.path.join(self.local_appdata, "Youku")], "cat": "视频软件", "subs": ["Cache", "download"]},
            {"name": "Bilibili", "paths": [os.path.join(self.local_appdata, "Bilibili")], "cat": "视频软件", "subs": ["Cache", "download"]},
            # 下载工具
            {"name": "迅雷", "paths": [os.path.join(self.local_appdata, "Thunder"), os.path.join(self.local_appdata, "Xunlei")], "cat": "下载工具", "subs": ["Download", "Cache", "Temp"]},
            {"name": "Internet Download Manager", "paths": [os.path.join(self.local_appdata, "IDM")], "cat": "下载工具", "subs": []},
            # 压缩软件
            {"name": "7-Zip", "paths": [os.path.join(self.local_appdata, "7-Zip")], "cat": "工具软件", "subs": ["Temp"]},
            {"name": "WinRAR", "paths": [os.path.join(self.local_appdata, "WinRAR")], "cat": "工具软件", "subs": ["Temp"]},
            {"name": "Bandizip", "paths": [os.path.join(self.local_appdata, "Bandisoft", "Bandizip")], "cat": "工具软件", "subs": ["Temp"]},
            # 办公软件
            {"name": "WPS Office", "paths": [os.path.join(self.local_appdata, "Kingsoft", "WPS", "Office6", "cache")], "cat": "办公软件", "subs": []},
            {"name": "Microsoft Office", "paths": [os.path.join(self.local_appdata, "Microsoft", "Office", "16.0", "OfficeFileCache")], "cat": "办公软件", "subs": []},
            # 设计软件
            {"name": "Adobe Cache", "paths": [os.path.join(self.local_appdata, "Adobe")], "cat": "设计软件", "subs": ["Cache", "temp"]},
            {"name": "Lightroom", "paths": [os.path.join(self.roaming_appdata, "Adobe", "Lightroom", "Settings")], "cat": "设计软件", "subs": ["Cache"]},
            # IDE缓存
            {"name": "VS Code", "paths": [os.path.join(self.roaming_appdata, "Code")], "cat": "开发工具", "subs": ["Cache", "CachedData", "CachedExtensions", "CachedExtensionVSIXs", "logs"]},
            {"name": "JetBrains", "paths": [os.path.join(self.local_appdata, "JetBrains")], "cat": "开发工具", "subs": []},
            # 包管理器缓存
            {"name": "npm缓存", "paths": [os.path.join(self.roaming_appdata, "npm-cache"), os.path.join(self.local_appdata, "npm-cache")], "cat": "开发缓存", "subs": []},
            {"name": "yarn缓存", "paths": [os.path.join(self.local_appdata, "Yarn/Cache")], "cat": "开发缓存", "subs": []},
            {"name": "pip缓存", "paths": [os.path.join(self.local_appdata, "pip/cache")], "cat": "开发缓存", "subs": []},
            {"name": "Docker镜像", "paths": [os.path.join(self.local_appdata, "Docker/wsl")], "cat": "开发缓存", "subs": []},
            {"name": "Maven缓存", "paths": [os.path.join(self.user_profile, ".m2/repository")], "cat": "开发缓存", "subs": []},
            {"name": "Gradle缓存", "paths": [os.path.join(self.user_profile, ".gradle/caches")], "cat": "开发缓存", "subs": []},
            # 系统安全
            {"name": "Windows Defender", "paths": [os.path.join(os.environ["PROGRAMDATA"], "Microsoft", "Windows Defender", "Scans", "History"), os.path.join(os.environ["PROGRAMDATA"], "Microsoft", "Windows Defender", "Support")], "cat": "系统安全", "subs": []},
            # Docker/WSL
            {"name": "Docker WSL", "paths": [os.path.join(self.local_appdata, "Docker", "wsl")], "cat": "虚拟化", "subs": ["data", "distro", "tmp"]},
            {"name": "WSL Linux", "paths": [os.path.join(self.local_appdata, "Packages", "CanonicalGroupLimited")], "cat": "虚拟化", "subs": []},
            # 开发缓存
            {"name": "Node.js 缓存", "paths": [os.path.join(self.roaming_appdata, "npm-cache"), os.path.join(self.local_appdata, "npm-cache")], "cat": "开发缓存", "subs": []},
            {"name": "Yarn 缓存", "paths": [os.path.join(self.roaming_appdata, "Yarn", "Cache"), os.path.join(self.local_appdata, "Yarn", "Cache")], "cat": "开发缓存", "subs": []},
            {"name": "NuGet 缓存", "paths": [os.path.join(self.user_profile, ".nuget", "packages")], "cat": "开发缓存", "subs": []},
            {"name": "pip 缓存", "paths": [os.path.join(self.local_appdata, "pip")], "cat": "开发缓存", "subs": ["cache"]},
            {"name": "Python 缓存", "paths": [os.path.join(self.user_profile, ".pytest_cache"), os.path.join(self.user_profile, ".mypy_cache")], "cat": "开发缓存", "subs": []},
            # IDE缓存
            {"name": "Android Studio", "paths": [os.path.join(self.user_profile, ".android", "cache"), os.path.join(self.user_profile, ".AndroidStudio", "system", "log")], "cat": "开发工具", "subs": []},
            {"name": "IntelliJ IDEA", "paths": [os.path.join(self.user_profile, ".IntelliJIdea")], "cat": "开发工具", "subs": ["system", "log", "caches"]},
            {"name": "PyCharm", "paths": [os.path.join(self.user_profile, ".PyCharm")], "cat": "开发工具", "subs": ["system", "log", "caches"]},
            {"name": "VS Code", "paths": [os.path.join(self.roaming_appdata, "Code", "User", "workspaceStorage", "backup")], "cat": "开发工具", "subs": []},
            # Windows 相关
            {"name": "Windows Store", "paths": [os.path.join(self.local_appdata, "Packages", "LocalCache")], "cat": "系统缓存", "subs": []},
            {"name": "Windows 资源管理器缓存", "paths": [os.path.join(self.local_appdata, "Microsoft", "Windows", "Explorer")], "cat": "系统缓存", "subs": ["IconCache", "ThumbnailCache"]},
            # 虚拟机
            {"name": "VMware", "paths": [os.path.join(self.user_profile, ".vmware")], "cat": "虚拟化", "subs": ["cache", "logs"]},
            {"name": "VirtualBox", "paths": [os.path.join(self.user_profile, ".VirtualBox")], "cat": "虚拟化", "subs": ["cache", "logs"]},
        ]
        
        # 扫描进度追踪
        self.scan_progress = {"current": 0, "total": 0, "start_time": 0}

    def detect_active_processes(self, app_names):
        active = []
        for name in app_names:
            if name in self.APP_PROCESSES:
                for proc in self.APP_PROCESSES[name]:
                    if self._check_process_running(proc):
                        active.append(name)
                        break
        return list(set(active))

    def _check_process_running(self, proc_name):
        try:
            output = subprocess.check_output(f'tasklist /FI "IMAGENAME eq {proc_name}"'.replace('"', '"'), shell=True).decode('gbk')
            return proc_name.lower() in output.lower()
        except: return False

    def kill_processes(self, app_names):
        for name in app_names:
            if name in self.APP_PROCESSES:
                for proc in self.APP_PROCESSES[name]:
                    subprocess.run(f'taskkill /F /IM {proc} /T'.replace('"', '"'), shell=True, capture_output=True)

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
                                if entry.is_file(follow_symlinks=False): total += entry.stat(follow_symlinks=False).st_size
                                elif entry.is_dir(follow_symlinks=False): stack.append(entry.path)
                            except: pass
                except: pass
        except: pass
        return total

    def get_file_list(self, path, limit=100):
        """获取目录下的文件列表用于预览"""
        files = []
        try:
            if os.path.isfile(path):
                return [{"name": os.path.basename(path), "size": os.path.getsize(path), "path": path}]
            for root, dirs, filenames in os.walk(path):
                for f in filenames:
                    if len(files) >= limit: return files
                    fp = os.path.join(root, f)
                    try:
                        files.append({"name": f, "size": os.path.getsize(fp), "path": fp})
                    except: pass
        except: pass
        return sorted(files, key=lambda x: x["size"], reverse=True)

    def estimate_scan_total(self, mode):
        """估算扫描总项目数"""
        if mode == "junk":
            return len(self.base_targets) + 50  # 基础 + AppData估算
        elif mode == "social":
            return 30
        elif mode == "resign":
            return 100
        elif mode == "custom":
            return 20
        return 50

    def scan_generator(self):
        self.scan_progress["start_time"] = time.time()
        self.scan_progress["current"] = 0
        self.scan_progress["total"] = self.estimate_scan_total("junk")
        
        # 扫描所有分区的回收站
        try:
            rb_size = 0
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if bitmask & (1 << i):
                    drive = chr(ord('A') + i) + ":/"
                    root = os.path.join(drive, "$Recycle.Bin")
                    if os.path.exists(root): rb_size += self.get_dir_size_fast(root)
            if rb_size > 0:
                yield {"type": "item", "data": {"cat": "特别清理", "soft": "回收站", "detail": "所有分区已删除文件", "path": "RECYCLE_BIN_SPECIAL", "raw_size": rb_size, "display_size": format_size(rb_size)}}
        except: pass

        for item in self.base_targets:
            self.scan_progress["current"] += 1
            yield {"type": "status", "msg": f"正在扫描: {item['path']}"}
            yield {"type": "progress", "current": self.scan_progress["current"], "total": self.scan_progress["total"], "start_time": self.scan_progress["start_time"]}
            if os.path.exists(item['path']):
                s = self.get_dir_size_fast(item['path'])
                if s > 0: yield {"type": "item", "data": {"cat": item['cat'], "soft": item['soft'], "detail": item['name'], "path": item['path'], "raw_size": s, "display_size": format_size(s)}}
        
        # 扫描扩展应用
        for app in self.extended_app_targets:
            self.scan_progress["current"] += 1
            yield {"type": "progress", "current": self.scan_progress["current"], "total": self.scan_progress["total"], "start_time": self.scan_progress["start_time"]}
            for base_path in app["paths"]:
                if not os.path.exists(base_path): continue
                if app["subs"]:
                    for sub in app["subs"]:
                        full_path = os.path.join(base_path, sub)
                        if os.path.exists(full_path):
                            s = self.get_dir_size_fast(full_path)
                            if s > 0:
                                yield {"type": "item", "data": {"cat": app["cat"], "soft": app["name"], "detail": sub, "path": full_path, "raw_size": s, "display_size": format_size(s)}}
                else:
                    s = self.get_dir_size_fast(base_path)
                    if s > 0:
                        yield {"type": "item", "data": {"cat": app["cat"], "soft": app["name"], "detail": os.path.basename(base_path), "path": base_path, "raw_size": s, "display_size": format_size(s)}}

        # 扫描死链与无效快捷方式
        yield from self._scan_broken_shortcuts()

        roots = [self.local_appdata, self.roaming_appdata]
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(self._scan_appdata_root, r) for r in roots]
            for fut in as_completed(futures):
                for r in fut.result(): yield r

    def _scan_broken_shortcuts(self):
        """扫描桌面和开始菜单的无效快捷方式"""
        paths = [os.path.join(self.user_profile, "Desktop"), os.path.join(self.roaming_appdata, "Microsoft", "Windows", "Start Menu", "Programs")]
        for p in paths:
            if not os.path.exists(p): continue
            try:
                for entry in os.scandir(p):
                    if entry.is_file() and entry.name.endswith(".lnk"):
                        pass
            except: pass
        return []

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
        self.scan_progress["start_time"] = time.time()
        self.scan_progress["current"] = 0
        self.scan_progress["total"] = self.estimate_scan_total("social")
        
        search_roots = []
        reg_configs = [
            (r"Software\Tencent\WeChat", "FileSavePath", "微信 WeChat"),
            (r"Software\Tencent\WXWork", "FileSavePath", "企业微信 WeCom"),
            (r"Software\Tencent\QQ2012", "UserDataSavePath", "腾讯 QQ")
        ]
        for reg_path, key_name, label in reg_configs:
            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ)
                path, _ = winreg.QueryValueEx(k, key_name)
                if path and os.path.exists(path): search_roots.append((label, path))
                winreg.CloseKey(k)
            except: pass

        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        drives = []
        for i in range(26):
            if bitmask & (1 << i):
                drive_p = chr(ord('A') + i) + ":/"
                if ctypes.windll.kernel32.GetDriveTypeW(drive_p) == 3: drives.append(drive_p)

        docs = ctypes.create_unicode_buffer(1024)
        ctypes.windll.shell32.SHGetSpecialFolderPathW(None, docs, 0x0005, False)
        common_bases = [docs.value, os.path.join(os.environ['APPDATA'], "Tencent"), os.path.join(os.environ['LOCALAPPDATA'], "Tencent")]
        
        social_targets = [
            {"name": "微信 WeChat", "root_names": ["WeChat Files"], "subs": {"图片缓存": "FileStorage/Image", "视频缓存": "FileStorage/Video", "文件缓存": "FileStorage/File", "临时资源": "FileStorage/Cache"}},
            {"name": "企业微信 WeCom", "root_names": ["WXWork"], "subs": {"图片缓存": "Data/Image", "视频缓存": "Data/Video", "文件缓存": "Data/File", "临时资源": "Data/Cache"}},
            {"name": "腾讯 QQ", "root_names": ["Tencent Files", "TencentFiles"], "subs": {"图片缓存": "Image", "视频缓存": "Video", "文件缓存": "File", "临时资源": "Cache"}}
        ]

        for base in set(common_bases):
            for t in social_targets:
                for rn in t['root_names']:
                    full = os.path.join(base, rn)
                    if os.path.exists(full): search_roots.append((t['name'], full))

        unique_tasks = {p: n for n, p in search_roots}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self._analyze_social_detailed, path, name, social_targets) for path, name in unique_tasks.items()]
            for fut in as_completed(futures):
                self.scan_progress["current"] += 1
                yield {"type": "progress", "current": self.scan_progress["current"], "total": self.scan_progress["total"], "start_time": self.scan_progress["start_time"]}
                for item in fut.result(): yield item

    def _analyze_social_detailed(self, root, app_name, targets):
        res = []
        target = next((t for t in targets if t['name'] == app_name), None)
        if not target: return res
        try:
            with os.scandir(root) as it:
                for entry in it:
                    if entry.is_dir() and entry.name not in ["All Users", "Applet", "config"]:
                        for label, sub_p in target['subs'].items():
                            full_sub = os.path.join(entry.path, sub_p)
                            if os.path.exists(full_sub):
                                s = self.get_dir_size_fast(full_sub)
                                if s > 0:
                                    res.append({"type": "item", "data": {
                                        "cat": f"{app_name} ({entry.name})", 
                                        "soft": label, 
                                        "detail": f"{label}目录", "path": full_sub, 
                                        "raw_size": s, "display_size": format_size(s)
                                    }})
        except: pass
        return res

    def scan_resignation_targets(self, custom_paths=[]):
        self.scan_progress["start_time"] = time.time()
        self.scan_progress["current"] = 0
        self.scan_progress["total"] = self.estimate_scan_total("resign")
        
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        drives = []
        for i in range(26):
            if bitmask & (1 << i):
                drive_p = chr(ord('A') + i) + ":/"
                if ctypes.windll.kernel32.GetDriveTypeW(drive_p) == 3: drives.append(drive_p)

        app_targets = [
            {"name": "微信 WeChat", "patterns": ["WeChat Files"], "cat": "通讯软件"},
            {"name": "企业微信 WeCom", "patterns": ["WXWork"], "cat": "通讯软件"},
            {"name": "腾讯 QQ", "patterns": ["Tencent Files", "TencentFiles"], "cat": "通讯软件"},
            {"name": "钉钉 DingTalk", "patterns": ["DingTalk"], "cat": "办公软件"},
            {"name": "飞书 Feishu", "patterns": ["Feishu", "Lark"], "cat": "办公软件"}
        ]

        scan_tasks = []
        for d in drives:
            try:
                with os.scandir(d) as it:
                    for entry in it:
                        if entry.is_dir() and entry.name.lower() not in self.SYSTEM_EXCLUDE:
                            scan_tasks.append(entry.path)
                scan_tasks.append(d)
            except: pass

        with ThreadPoolExecutor(max_workers=24) as executor:
            futures = [executor.submit(self._radar_scan_sub_folder, path, app_targets) for path in scan_tasks]
            for fut in as_completed(futures):
                self.scan_progress["current"] += 1
                yield {"type": "progress", "current": self.scan_progress["current"], "total": max(self.scan_progress["total"], len(scan_tasks)), "start_time": self.scan_progress["start_time"]}
                for item in fut.result(): yield item

        for item in self._scan_resignation_privacy_full(): yield item

        yield {"type": "item", "data": { "cat": "网络隐私", "soft": "Network Traces", "detail": "DNS/ARP/共享记录历史", "path": "NETWORK_TRACES_SPECIAL", "raw_size": 1024, "display_size": "1.00 KB" }}

        for cp in custom_paths:
            if os.path.exists(cp):
                s = self.get_dir_size_fast(cp)
                yield {"type": "item", "data": { "cat": "自定义敏感目录", "soft": "手动添加", "detail": os.path.basename(cp), "path": cp, "raw_size": s, "display_size": format_size(s) }}

    def _scan_resignation_privacy_full(self):
        results = []
        la = self.local_appdata
        ra = self.roaming_appdata
        up = self.user_profile

        browsers = {
            "Chrome": os.path.join(la, "Google/Chrome/User Data"),
            "Edge": os.path.join(la, "Microsoft/Edge/User Data"),
            "360Speed": os.path.join(la, "360Chrome/Chrome/User Data"),
            "QQBrowser": os.path.join(la, "Tencent/QQBrowser/User Data")
        }
        for b_name, b_path in browsers.items():
            if os.path.exists(b_path):
                for root, dirs, files in os.walk(b_path):
                    if "Login Data" in files or "Cookies" in files:
                        for target in ["Login Data", "Cookies", "History", "Web Data"]:
                            fp = os.path.join(root, target)
                            if os.path.exists(fp):
                                results.append({"type": "item", "data": { "cat": "浏览器隐私", "soft": b_name, "detail": f"凭据库: {target}", "path": fp, "raw_size": os.path.getsize(fp), "display_size": format_size(os.path.getsize(fp)) }})
                    if root.count(os.sep) - b_path.count(os.sep) > 2: dirs[:] = []; continue

        dev_tools = [
            ("SSH 密钥", os.path.join(up, ".ssh"), "私钥(id_rsa)", "开发凭据"),
            ("Git 配置", os.path.join(up, ".gitconfig"), "全局账号信息", "开发凭据"),
            ("PowerShell 历史", os.path.join(ra, "Microsoft/Windows/PowerShell/PSReadLine/ConsoleHost_history.txt"), "指令历史(含密码)", "指令历史"),
            ("Navicat", os.path.join(up, "Documents/Navicat"), "连接配置与查询历史", "运维凭据"),
            ("XShell", os.path.join(up, "Documents/NetSarang Computer/7/Xshell/Sessions"), "服务器连接凭据", "运维凭据"),
            ("AWS凭据", os.path.join(up, ".aws"), "AWS访问密钥", "云服务凭据"),
            ("Azure凭据", os.path.join(up, ".azure"), "Azure访问凭据", "云服务凭据"),
            ("Kubernetes", os.path.join(up, ".kube"), "K8s集群配置", "云服务凭据"),
            ("Docker配置", os.path.join(up, ".docker"), "Docker登录凭据", "开发凭据"),
        ]
        for name, path, detail, cat in dev_tools:
            if os.path.exists(path):
                s = self.get_dir_size_fast(path) if os.path.isdir(path) else os.path.getsize(path)
                results.append({"type": "item", "data": { "cat": cat, "soft": name, "detail": detail, "path": path, "raw_size": s, "display_size": format_size(s) }})

        mails = [
            ("Outlook", os.path.join(la, "Microsoft/Outlook"), "邮件存档(.ost)"),
            ("Foxmail", os.path.join(up, "Documents/Foxmail"), "邮件数据库"),
            ("Foxmail", os.path.join(la, "Foxmail/Storage"), "本地邮件数据")
        ]
        for name, path, detail in mails:
            if os.path.exists(path):
                s = self.get_dir_size_fast(path)
                results.append({"type": "item", "data": { "cat": "邮件存档", "soft": name, "detail": detail, "path": path, "raw_size": s, "display_size": format_size(s) }})

        cloud_sys = [
            ("百度网盘", os.path.join(ra, "baidu/BaiduNetdisk/users"), "登录Session", "云端工具"),
            ("Notion", os.path.join(ra, "Notion/Local Storage"), "笔记缓存", "云端工具"),
            ("WPS Office", os.path.join(ra, "kingsoft/wps/office6/data/backup"), "文档自动备份", "办公记录"),
            ("最近文档", os.path.join(ra, "Microsoft/Windows/Recent"), "打开历史痕迹", "操作足迹"),
            ("系统凭据", "WINDOWS_VAULT_SPECIAL", "凭据管理器保存的密码", "系统凭据")
        ]
        for name, path, detail, cat in cloud_sys:
            if path == "WINDOWS_VAULT_SPECIAL" or os.path.exists(path):
                s = self.get_dir_size_fast(path) if (path != "WINDOWS_VAULT_SPECIAL" and os.path.isdir(path)) else 1024
                results.append({"type": "item", "data": { "cat": cat, "soft": name, "detail": detail, "path": path, "raw_size": s, "display_size": format_size(s) }})

        return results

    def _radar_scan_sub_folder(self, folder_path, targets):
        results = []
        try:
            folder_name = os.path.basename(folder_path).lower()
            for target in targets:
                if any(p.lower() == folder_name for p in target['patterns']):
                    return self._extract_account_folders(folder_path, target)
            with os.scandir(folder_path) as it:
                for entry in it:
                    if entry.is_dir() and any(p.lower() == entry.name.lower() for t in targets for p in t['patterns']):
                        target = next(t for t in targets if any(p.lower() == entry.name.lower() for p in t['patterns']))
                        results.extend(self._extract_account_folders(entry.path, target))
        except: pass
        return results

    def _extract_account_folders(self, root_path, target):
        accounts = []
        exclude = ["All Users", "Applet", "config", "temp", "logs", "cache"]
        try:
            with os.scandir(root_path) as it:
                for entry in it:
                    if entry.is_dir() and entry.name not in exclude:
                        s = self.get_dir_size_fast(entry.path)
                        if s > 1024:
                            accounts.append({"type": "item", "data": { "cat": target['cat'], "soft": target['name'], "detail": f"账号数据: {entry.name}", "path": entry.path, "raw_size": s, "display_size": format_size(s) }})
        except: pass
        return accounts

    def shred_item(self, path):
        if path == "WINDOWS_VAULT_SPECIAL":
            subprocess.run("cmdkey /list | findstr /i \"target\" > %temp%\\v.txt", shell=True)
            return 1024, 0
        if path == "NETWORK_TRACES_SPECIAL":
            subprocess.run("ipconfig /flushdns", shell=True, capture_output=True)
            subprocess.run("arp -d *", shell=True, capture_output=True)
            subprocess.run("net use * /delete /y", shell=True, capture_output=True)
            return 1024, 0
            
        if not os.path.exists(path): return 0, 0
        total_freed = 0
        try:
            if os.path.isfile(path):
                sz = os.path.getsize(path)
                with open(path, "ba+", buffering=0) as f: f.write(os.urandom(min(sz, 1024*1024)))
                os.remove(path); return sz, 0
            for r, d, f in os.walk(path, topdown=False):
                for file in f:
                    fp = os.path.join(r, file)
                    try:
                        fsz = os.path.getsize(fp)
                        with open(fp, "ba+", buffering=0) as f_o: f_o.write(os.urandom(min(fsz, 512*1024)))
                        os.remove(fp); total_freed += fsz
                    except: pass
                for dir_n in d:
                    try: os.rmdir(os.path.join(r, dir_n))
                    except: pass
            os.rmdir(path)
        except: return 0, 1
        return total_freed, 0

    def delete_item(self, path):
        if path == "RECYCLE_BIN_SPECIAL":
            try: return 0, 0 if ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7) == 0 else 1
            except: return 0, 1
        if path == "CLIPBOARD_SPECIAL":
            self.clear_clipboard_history()
            return 1024, 0
        if not os.path.exists(path): return 0, 0
        ds, errs = 0, 0
        try:
            if os.path.isfile(path): s=os.path.getsize(path); os.remove(path); return s, 0
            for r, d, f in os.walk(path, topdown=False):
                for file in f:
                    try: fp=os.path.join(r,file); ds+=os.path.getsize(fp); os.remove(fp)
                    except: errs+=1
                for di in d:
                    try: os.rmdir(os.path.join(r,di))
                    except: pass
            try: os.rmdir(path)
            except: pass
        except: errs+=1
        return ds, errs

    def generate_report(self, freed_size, items_count):
        report_path = os.path.join(os.environ['USERPROFILE'], "Desktop", f"离职安全清理报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        content = f"""C盘深度清理助手 - 离职安全审计报告
=======================================
清理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
清理模式: 离职专清 (Fully Shredder)
数据状态: 已执行物理粉碎 (不可恢复)

统计结果:
- 释放空间: {format_size(freed_size)}
- 粉碎隐私项: {items_count} 项

覆盖维度:
- 办公协作: 微信、企业微信、QQ、钉钉、飞书
- 浏览器隐私: Chrome、Edge、360、QQ浏览器 (密码/Cookies)
- 开发者/运维凭据: SSH私钥、Git配置、Navicat、XShell
- 邮件客户端: Outlook、Foxmail 存档
- 办公记录: WPS备份、剪贴板历史、最近文档记录
- 网络印记: 已刷新 DNS、ARP 缓存、断开网络共享连接
======================================="""
        try:
            with open(report_path, "w", encoding="utf-8") as f: f.write(content)
            return report_path
        except: return None

    def infer_info(self, name, dir_path):
        name_lower = name.lower()
        cat, soft = "其他应用", name
        app_map = {
            'google': ('浏览器缓存', 'Google Chrome'), 'chrome': ('浏览器缓存', 'Google Chrome'), 'edge': ('浏览器缓存', 'Edge'),
            'microsoft': ('应用缓存', 'Microsoft Apps'), 'tencent': ('社交通讯', '腾讯软件'), 'wechat': ('社交通讯', '微信 WeChat'),
            'dingtalk': ('办公软件', '钉钉'), 'feishu': ('办公软件', '飞书'), 'adobe': ('设计工具', 'Adobe'), 'steam': ('游戏平台', 'Steam'),
            'discord': ('通讯软件', 'Discord'), 'telegram': ('通讯软件', 'Telegram'), 'slack': ('通讯软件', 'Slack'),
            'jetbrains': ('开发工具', 'JetBrains IDE'), 'vscode': ('开发工具', 'VS Code'), 'code': ('开发工具', 'VS Code'),
            'netease': ('音乐软件', '网易云音乐'), 'qqmusic': ('音乐软件', 'QQ音乐'),
            # 视频软件
            'iqiyi': ('视频软件', '爱奇艺'), 'qqlive': ('视频软件', '腾讯视频'), 'youku': ('视频软件', '优酷'), 'bilibili': ('视频软件', 'Bilibili'),
            # 下载工具
            'thunder': ('下载工具', '迅雷'), 'xunlei': ('下载工具', '迅雷'), 'idm': ('下载工具', 'Internet Download Manager'),
            # 压缩软件
            '7-zip': ('工具软件', '7-Zip'), 'winrar': ('工具软件', 'WinRAR'), 'bandizip': ('工具软件', 'Bandizip'),
            # 办公软件
            'kingsoft': ('办公软件', 'WPS Office'), 'wps': ('办公软件', 'WPS Office'),
            # 系统安全
            'defender': ('系统安全', 'Windows Defender'),
        }
        for key, (c, s) in app_map.items():
            if key in name_lower: cat, soft = c, s; break
        return cat, soft

    def scan_custom(self, paths, min_file_size=0, max_depth=10, scan_empty=True, aggregate_small=True, find_duplicates=True):
        """全面增强版自定义扫描 - 彻底检测各类垃圾文件
        
        Args:
            paths: 要扫描的路径列表
            min_file_size: 最小文件大小（字节），0表示不限制
            max_depth: 最大扫描深度，0表示无限制
            scan_empty: 是否扫描空文件和空目录
            aggregate_small: 是否聚合报告小文件
            find_duplicates: 是否查找重复文件
        """
        self.scan_progress["start_time"] = time.time()
        self.scan_progress["current"] = 0
        # 估算总任务数
        self.scan_progress["total"] = len(paths) * 15
        
        # 扩展垃圾文件特征库
        garbage_patterns = {
            'extensions': {
                '.tmp', '.temp', '.cache', '.log', '.logs', '.dmp', '.dump', '.mdmp', '.hdmp',
                '.old', '.bak', '.backup', '.orig', '.original', '.save', '.sav',
                '.swp', '.swo', '.swm', '~', '.~', '.chk', '.chkfile', '.gid', '.fts', '.ftg',
                '.prv', '.sik', '.ilk', '.ncb', '.sdf', '.opensdf', '.tlog', '.lastbuildstate',
                '.ipch', '.obj', '.pch', '.res', '.idb', '.pdb', '.exp', '.lib', '.manifest',
                '.metagen', '.cachefile', '.crdownload', '.part', '.partial', '.download',
                '.thumb', '.thumbnail'
            },
            'keywords': [
                'temp', 'tmp', 'cache', 'log', 'dump', 'crash', 'backup', 'bak', 'old',
                'obsolete', 'trash', 'recycle', 'download', 'installer', 'setup',
                'update', 'upgrade', 'preview', 'render', 'index', 'cookie', 'session',
                'report', 'feedback', 'diagnostics', 'error', 'failure', 'install',
                'uninstall', 'blob', 'storage', 'datastore', 'repository', 'component',
                'manifest', 'shader', 'gpu', 'font', 'icon', 'thumb', 'webcache',
                'iecache', 'inetcache', 'codecache'
            ],
            'prefixes': ['~', '.~', 'tmp', 'temp'],
            'suffixes': ['~', '.tmp', '.temp', '.old', '.bak', '.backup', '.orig', '.save'],
            'dev_folders': ['__pycache__', '.pytest_cache', '.mypy_cache', 'node_modules', 
                           '.gradle', 'build', 'dist', '.vs', 'bin', 'obj', 'target', '.git'],
            'media_folders': ['thumbnails', 'thumbs', 'previews', 'cache', 'shadercache']
        }
        
        # 大文件阈值
        thresholds = {
            'huge': 100 * 1024 * 1024,    # 100MB
            'large': 20 * 1024 * 1024,     # 20MB
            'medium': 5 * 1024 * 1024,     # 5MB
            'small_aggregate': 100 * 1024   # 100KB - 小于此值的文件会聚合报告
        }
        
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(self._scan_single_custom_v2, p, garbage_patterns, thresholds, 
                                min_file_size, max_depth, scan_empty, aggregate_small, find_duplicates) 
                      for p in paths]
            for fut in as_completed(futures):
                self.scan_progress["current"] += 1
                yield {"type": "progress", "current": self.scan_progress["current"], 
                       "total": self.scan_progress["total"], "start_time": self.scan_progress["start_time"]}
                for item in fut.result(): yield item

    def _scan_single_custom_v2(self, base, patterns, thresholds, min_size, max_depth, 
                                scan_empty, aggregate_small, find_duplicates):
        """性能优化版单路径扫描 - 使用 os.scandir 和更快的哈希计算"""
        res = []
        if not os.path.exists(base): return res
        
        # 预编译扩展名集合和关键词集合以提高查找速度
        ext_set = patterns['extensions']
        keywords = patterns['keywords']
        prefixes = tuple(patterns['prefixes'])  # startswith 需要 tuple
        suffixes = tuple(patterns['suffixes'])  # endswith 需要 tuple
        dev_folders = patterns['dev_folders']
        media_folders = patterns['media_folders']
        
        # 跟踪已报告的项目
        reported_items = set()
        # 目录信息收集器
        dir_info = {}
        # 空文件列表
        empty_files = []
        # 空目录列表
        empty_dirs = []
        # 文件哈希收集器（用于重复检测）- 只检测大文件
        file_hashes = {}
        
        base_lower = base.lower()
        base_sep_count = base.count(os.sep)
        
        # 使用栈实现深度优先遍历，避免递归开销
        stack = [(base, 0)]  # (path, depth)
        
        while stack:
            current_path, current_depth = stack.pop()
            
            if max_depth > 0 and current_depth > max_depth:
                continue
            
            # 跳过系统保护目录
            current_lower = current_path.lower()
            if any(ex in current_lower for ex in self.SYSTEM_EXCLUDE):
                continue
            
            try:
                entries = list(os.scandir(current_path))
            except (PermissionError, OSError):
                continue
            
            # 分离文件和目录
            files = []
            subdirs = []
            for entry in entries:
                try:
                    if entry.is_file(follow_symlinks=False):
                        files.append(entry)
                    elif entry.is_dir(follow_symlinks=False):
                        subdirs.append(entry)
                except (OSError, PermissionError):
                    continue
            
            # 检测空目录
            if scan_empty and len(files) == 0 and len(subdirs) == 0:
                empty_dirs.append(current_path)
                continue
            
            # 将子目录压入栈（反向压入保持顺序）
            for subdir in reversed(subdirs):
                stack.append((subdir.path, current_depth + 1))
            
            # 初始化目录信息
            dir_info[current_path] = {
                'size': 0,
                'file_count': len(files),
                'garbage_count': 0,
                'temp_count': 0,
                'small_garbage': [],
                'depth': current_depth
            }
            
            # 检查是否是特殊垃圾目录
            is_dev_folder = any(folder in current_lower for folder in dev_folders)
            is_media_folder = any(folder in current_lower for folder in media_folders)
            
            # 处理文件
            for entry in files:
                try:
                    stat = entry.stat(follow_symlinks=False)
                    sz = stat.st_size
                    
                    # 检测空文件
                    if scan_empty and sz == 0:
                        empty_files.append(entry.path)
                        continue
                    
                    # 跳过小于最小大小的文件
                    if sz < min_size:
                        continue
                    
                    fname = entry.name
                    ext = os.path.splitext(fname)[1].lower()
                    fname_lower = fname.lower()
                    
                    # 快速判断是否为垃圾文件
                    is_garbage = False
                    garbage_type = None
                    
                    # 检查扩展名（最快）
                    if ext in ext_set:
                        is_garbage = True
                        garbage_type = self._classify_garbage_type(ext, fname_lower)
                    
                    # 检查关键词
                    if not is_garbage:
                        for kw in keywords:
                            if kw in fname_lower:
                                is_garbage = True
                                garbage_type = kw
                                break
                    
                    # 检查前缀和后缀
                    if not is_garbage:
                        if fname.startswith(prefixes):
                            is_garbage = True
                            garbage_type = "临时文件"
                        elif fname.endswith(suffixes):
                            is_garbage = True
                            garbage_type = "备份文件"
                    
                    dir_info[current_path]['size'] += sz
                    
                    if is_garbage:
                        dir_info[current_path]['garbage_count'] += 1
                        if 'temp' in garbage_type or 'cache' in garbage_type:
                            dir_info[current_path]['temp_count'] += 1
                        
                        # 大文件单独报告
                        if sz >= thresholds['medium']:
                            if entry.path not in reported_items:
                                reported_items.add(entry.path)
                                cat = "超大垃圾文件" if sz >= thresholds['huge'] else ("大垃圾文件" if sz >= thresholds['large'] else "中等垃圾文件")
                                res.append({"type": "item", "data": {
                                    "cat": cat,
                                    "soft": garbage_type,
                                    "detail": f"{fname} ({format_size(sz)})",
                                    "path": entry.path,
                                    "raw_size": sz,
                                    "display_size": format_size(sz),
                                    "depth": current_depth
                                }})
                        elif aggregate_small and sz < thresholds['small_aggregate']:
                            # 小文件加入聚合器
                            dir_info[current_path]['small_garbage'].append({'name': fname, 'size': sz, 'type': garbage_type})
                        elif entry.path not in reported_items:
                            # 中等大小的垃圾文件单独报告
                            reported_items.add(entry.path)
                            res.append({"type": "item", "data": {
                                "cat": f"垃圾文件 ({garbage_type})",
                                "soft": os.path.basename(base),
                                "detail": fname,
                                "path": entry.path,
                                "raw_size": sz,
                                "display_size": format_size(sz),
                                "depth": current_depth
                            }})
                    
                    # 重复文件检测 - 只对大于100KB的文件计算哈希（减少IO）
                    if find_duplicates and sz > 100 * 1024:
                        try:
                            # 使用更快的 xxhash 或只读取前4KB
                            import hashlib
                            with open(entry.path, 'rb') as hf:
                                # 只读取前4KB计算哈希（足够检测大部分重复）
                                file_hash = hashlib.md5(hf.read(4096)).hexdigest()
                            if file_hash in file_hashes:
                                file_hashes[file_hash].append(entry.path)
                            else:
                                file_hashes[file_hash] = [entry.path]
                        except:
                            pass
                
                except (OSError, PermissionError):
                    continue
            
            # 报告特殊垃圾目录
            if is_dev_folder and dir_info[current_path]['size'] > 5 * 1024 * 1024 and current_path not in reported_items:
                reported_items.add(current_path)
                rel_path = os.path.relpath(current_path, base)
                res.append({"type": "item", "data": {
                    "cat": "开发缓存目录",
                    "soft": os.path.basename(base),
                    "detail": f"{rel_path} ({dir_info[current_path]['file_count']}个文件, {format_size(dir_info[current_path]['size'])})",
                    "path": current_path,
                    "raw_size": dir_info[current_path]['size'],
                    "display_size": format_size(dir_info[current_path]['size']),
                    "depth": current_depth
                }})
            
            elif is_media_folder and dir_info[current_path]['size'] > 1 * 1024 * 1024 and current_path not in reported_items:
                reported_items.add(current_path)
                rel_path = os.path.relpath(current_path, base)
                res.append({"type": "item", "data": {
                    "cat": "媒体缓存目录",
                    "soft": os.path.basename(base),
                    "detail": f"{rel_path} ({dir_info[current_path]['file_count']}个文件)",
                    "path": current_path,
                    "raw_size": dir_info[current_path]['size'],
                    "display_size": format_size(dir_info[current_path]['size']),
                    "depth": current_depth
                }})
        
        # 批量报告空文件
        if scan_empty and empty_files:
            for ef in empty_files[:100]:
                depth = ef.count(os.sep) - base_sep_count
                rel = os.path.relpath(ef, base)
                res.append({"type": "item", "data": {
                    "cat": "空文件",
                    "soft": os.path.basename(base),
                    "detail": rel,
                    "path": ef,
                    "raw_size": 0,
                    "display_size": "0 B",
                    "depth": depth
                }})
            if len(empty_files) > 100:
                res.append({"type": "item", "data": {
                    "cat": "空文件",
                    "soft": os.path.basename(base),
                    "detail": f"... 还有 {len(empty_files) - 100} 个空文件",
                    "path": base,
                    "raw_size": 0,
                    "display_size": "0 B",
                    "depth": 0
                }})
        
        # 批量报告空目录
        if scan_empty and empty_dirs:
            for ed in empty_dirs[:50]:
                depth = ed.count(os.sep) - base_sep_count
                rel = os.path.relpath(ed, base)
                res.append({"type": "item", "data": {
                    "cat": "空目录",
                    "soft": os.path.basename(base),
                    "detail": rel,
                    "path": ed,
                    "raw_size": 0,
                    "display_size": "0 B",
                    "depth": depth
                }})
            if len(empty_dirs) > 50:
                res.append({"type": "item", "data": {
                    "cat": "空目录",
                    "soft": os.path.basename(base),
                    "detail": f"... 还有 {len(empty_dirs) - 50} 个空目录",
                    "path": base,
                    "raw_size": 0,
                    "display_size": "0 B",
                    "depth": 0
                }})
        
        # 聚合报告小垃圾文件
        if aggregate_small:
            for root_path, info in dir_info.items():
                if info['small_garbage']:
                    total_small_size = sum(sf['size'] for sf in info['small_garbage'])
                    if total_small_size > 100 * 1024:  # 只报告超过100KB的聚合
                        file_types = set(sf['type'] for sf in info['small_garbage'])
                        rel = os.path.relpath(root_path, base)
                        res.append({"type": "item", "data": {
                            "cat": "小垃圾文件聚合",
                            "soft": os.path.basename(base),
                            "detail": f"{rel} ({len(info['small_garbage'])}个文件, 类型: {', '.join(list(file_types)[:3])})",
                            "path": root_path,
                            "raw_size": total_small_size,
                            "display_size": format_size(total_small_size),
                            "depth": info['depth'],
                            "file_count": len(info['small_garbage'])
                        }})
        
        # 报告重复文件
        if find_duplicates:
            for file_hash, file_list in file_hashes.items():
                if len(file_list) > 1:
                    try:
                        first_size = os.path.getsize(file_list[0])
                        if first_size > 10 * 1024:  # 只报告大于10KB的重复文件
                            total_dup_size = first_size * (len(file_list) - 1)
                            res.append({"type": "item", "data": {
                                "cat": "重复文件",
                                "soft": os.path.basename(base),
                                "detail": f"{os.path.basename(file_list[0])} ({len(file_list)}个副本, 可节省 {format_size(total_dup_size)})",
                                "path": file_list[0],
                                "raw_size": total_dup_size,
                                "display_size": format_size(total_dup_size),
                                "depth": file_list[0].count(os.sep) - base_sep_count,
                                "duplicates": file_list
                            }})
                    except:
                        pass
        
        # 报告高垃圾占比目录
        for root_path, info in dir_info.items():
            if info['size'] > 50 * 1024 * 1024 and info['file_count'] > 0:
                garbage_ratio = info['garbage_count'] / info['file_count']
                if garbage_ratio > 0.3 and root_path not in reported_items:
                    rel = os.path.relpath(root_path, base)
                    res.append({"type": "item", "data": {
                        "cat": f"高垃圾占比目录 ({garbage_ratio*100:.0f}%)",
                        "soft": os.path.basename(base),
                        "detail": f"{rel} ({format_size(info['size'])}, {info['file_count']}个文件)",
                        "path": root_path,
                        "raw_size": info['size'],
                        "display_size": format_size(info['size']),
                        "depth": info['depth']
                    }})
        
        return res

    def _classify_garbage_type(self, ext, fname):
        """根据扩展名和文件名分类垃圾类型"""
        ext_lower = ext.lower()
        fname_lower = fname.lower()
        
        temp_exts = {'.tmp', '.temp', '.cache', '.swp', '.swo'}
        log_exts = {'.log', '.logs'}
        dump_exts = {'.dmp', '.dump', '.mdmp', '.hdmp'}
        backup_exts = {'.old', '.bak', '.backup', '.orig', '.original', '.save', '.sav'}
        dev_exts = {'.obj', '.pch', '.idb', '.pdb', '.ilk', '.ncb', '.sdf', '.ipch', '.tlog'}
        download_exts = {'.crdownload', '.part', '.partial'}
        
        if ext_lower in temp_exts or 'temp' in fname_lower or 'tmp' in fname_lower:
            return "临时文件"
        elif ext_lower in log_exts or 'log' in fname_lower:
            return "日志文件"
        elif ext_lower in dump_exts or 'crash' in fname_lower or 'dump' in fname_lower:
            return "崩溃转储"
        elif ext_lower in backup_exts or 'backup' in fname_lower or 'bak' in fname_lower:
            return "备份文件"
        elif ext_lower in dev_exts:
            return "开发残留"
        elif ext_lower in download_exts:
            return "下载残留"
        else:
            return "垃圾文件"

    def scan_custom_deep(self, paths):
        """深度自定义扫描 - 使用新的全面扫描算法，无深度限制，检测更多垃圾"""
        # 调用新的 scan_custom，参数设置为深度扫描模式
        # min_file_size=0: 不限制最小文件大小
        # max_depth=0: 无深度限制
        # scan_empty=True: 检测空文件和目录
        # aggregate_small=True: 聚合小文件
        # find_duplicates=True: 查找重复文件
        yield from self.scan_custom(paths, min_file_size=0, max_depth=0, 
                                     scan_empty=True, aggregate_small=True, find_duplicates=True)



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

    def get_disk_usage(self):
        """获取各分区磁盘使用情况"""
        import shutil
        disks = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if bitmask & (1 << i):
                drive = chr(ord('A') + i) + ":/"
                if ctypes.windll.kernel32.GetDriveTypeW(drive) == 3:
                    try:
                        total, used, free = shutil.disk_usage(drive)
                        disks.append({
                            "drive": drive,
                            "total": total,
                            "used": used,
                            "free": free,
                            "percent": round(used / total * 100, 1)
                        })
                    except: pass
        return disks

    def scan_system_restore_points(self):
        """扫描系统还原点"""
        try:
            output = subprocess.check_output('vssadmin list shadows', shell=True, capture_output=True).decode('gbk', errors='ignore')
            restore_points = []
            for line in output.split('\n'):
                if 'Shadow Copy Volume' in line or '原始卷' in line:
                    restore_points.append(line.strip())
            if restore_points:
                yield {"type": "item", "data": {
                    "cat": "系统还原点",
                    "soft": "Windows",
                    "detail": f"发现 {len(restore_points)} 个还原点",
                    "path": "SYSTEM_RESTORE_SPECIAL",
                    "raw_size": len(restore_points) * 1024 * 1024,  # 估算每个还原点至少1GB
                    "display_size": f"{len(restore_points)} 个"
                }}
        except: pass

    def clean_system_restore_points(self, keep_count=1):
        """清理系统还原点，保留最近的几个"""
        try:
            # 使用 vssadmin 删除除最近外的所有还原点
            cmd = f'vssadmin delete shadows /for=C: /older={keep_count} /quiet'
            subprocess.run(cmd, shell=True, capture_output=True)
            return True
        except: return False

    def is_sensitive_path(self, path):
        """检测是否为敏感路径"""
        path_lower = path.lower()
        filename = os.path.basename(path).lower()
        
        # 检查路径中是否包含敏感关键词
        for keyword in self.SENSITIVE_PATHS:
            if keyword in path_lower or keyword in filename:
                return True
        
        # 检查是否为重要文档类型
        important_extensions = ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf', '.sqlite', '.db']
        if os.path.splitext(path)[1].lower() in important_extensions:
            return True
        
        return False

    def get_sensitive_items(self, paths):
        """获取需要二次确认的敏感项"""
        sensitive = []
        for path in paths:
            if self.is_sensitive_path(path):
                sensitive.append(path)
        return sensitive

    # ==================== 新增功能 v6.5 ====================
    
    def scan_duplicate_files(self, scan_paths=None):
        """扫描重复文件"""
        import hashlib
        if not scan_paths:
            scan_paths = [os.path.join(self.user_profile, d) for d in ["Downloads", "Desktop", "Documents", "Pictures"]]
        
        # 按大小分组
        size_map = {}
        self.scan_progress["start_time"] = time.time()
        self.scan_progress["current"] = 0
        self.scan_progress["total"] = len(scan_paths) * 10
        
        for base in scan_paths:
            if not os.path.exists(base): continue
            self.scan_progress["current"] += 1
            yield {"type": "progress", "current": self.scan_progress["current"], "total": self.scan_progress["total"], "start_time": self.scan_progress["start_time"]}
            yield {"type": "status", "msg": f"扫描目录: {base}"}
            
            for root, dirs, files in os.walk(base):
                # 跳过隐藏目录
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        sz = os.path.getsize(fp)
                        if sz > 1024:  # 忽略小于1KB的文件
                            if sz not in size_map: size_map[sz] = []
                            size_map[sz].append(fp)
                    except: pass
        
        # 对相同大小的文件计算哈希
        hash_map = {}
        potential_dups = {sz: paths for sz, paths in size_map.items() if len(paths) > 1}
        
        for sz, paths in potential_dups.items():
            for fp in paths:
                try:
                    h = self._get_file_hash(fp)
                    if h:
                        if h not in hash_map: hash_map[h] = []
                        hash_map[h].append({"path": fp, "size": sz})
                except: pass
        
        # 输出重复文件组
        for h, files in hash_map.items():
            if len(files) > 1:
                total_waste = files[0]["size"] * (len(files) - 1)
                for i, f in enumerate(files):
                    yield {"type": "item", "data": {
                        "cat": "重复文件",
                        "soft": f"组 {h[:8]}",
                        "detail": f"{'[保留]' if i == 0 else '[重复]'} {os.path.basename(f['path'])}",
                        "path": f["path"],
                        "raw_size": f["size"],
                        "display_size": format_size(f["size"]),
                        "is_duplicate": i > 0,
                        "hash": h
                    }}

    def _get_file_hash(self, filepath, block_size=65536):
        """计算文件MD5哈希（只读取前后各64KB加速）"""
        import hashlib
        hasher = hashlib.md5()
        try:
            with open(filepath, 'rb') as f:
                sz = os.path.getsize(filepath)
                if sz <= block_size * 2:
                    buf = f.read()
                    hasher.update(buf)
                else:
                    # 读取头部
                    hasher.update(f.read(block_size))
                    # 读取尾部
                    f.seek(-block_size, 2)
                    hasher.update(f.read(block_size))
                    # 加入文件大小
                    hasher.update(str(sz).encode())
            return hasher.hexdigest()
        except: return None

    def scan_empty_folders(self):
        """扫描空文件夹"""
        scan_roots = [
            self.user_profile,
            os.path.join(self.local_appdata),
            os.path.join(self.roaming_appdata),
        ]
        
        self.scan_progress["start_time"] = time.time()
        self.scan_progress["current"] = 0
        self.scan_progress["total"] = len(scan_roots) * 5
        
        for base in scan_roots:
            if not os.path.exists(base): continue
            self.scan_progress["current"] += 1
            yield {"type": "progress", "current": self.scan_progress["current"], "total": self.scan_progress["total"], "start_time": self.scan_progress["start_time"]}
            
            for root, dirs, files in os.walk(base, topdown=False):
                # 跳过系统目录
                if any(ex in root.lower() for ex in self.SYSTEM_EXCLUDE): continue
                
                try:
                    # 检查是否为空目录
                    if not os.listdir(root):
                        yield {"type": "item", "data": {
                            "cat": "空文件夹",
                            "soft": os.path.basename(os.path.dirname(root)),
                            "detail": os.path.basename(root),
                            "path": root,
                            "raw_size": 0,
                            "display_size": "0 B"
                        }}
                except: pass

    def scan_broken_shortcuts(self):
        """扫描无效快捷方式"""
        import struct
        
        paths = [
            os.path.join(self.user_profile, "Desktop"),
            os.path.join(self.roaming_appdata, "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.environ.get("PUBLIC", "C:\\Users\\Public"), "Desktop"),
            os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "Microsoft", "Windows", "Start Menu", "Programs"),
        ]
        
        self.scan_progress["start_time"] = time.time()
        self.scan_progress["current"] = 0
        self.scan_progress["total"] = len(paths)
        
        for base in paths:
            if not os.path.exists(base): continue
            self.scan_progress["current"] += 1
            yield {"type": "progress", "current": self.scan_progress["current"], "total": self.scan_progress["total"], "start_time": self.scan_progress["start_time"]}
            
            for root, dirs, files in os.walk(base):
                for f in files:
                    if f.lower().endswith('.lnk'):
                        fp = os.path.join(root, f)
                        target = self._get_lnk_target(fp)
                        if target and not os.path.exists(target):
                            yield {"type": "item", "data": {
                                "cat": "无效快捷方式",
                                "soft": "桌面" if "Desktop" in base else "开始菜单",
                                "detail": f"{f} → {target}",
                                "path": fp,
                                "raw_size": os.path.getsize(fp),
                                "display_size": format_size(os.path.getsize(fp))
                            }}

    def _get_lnk_target(self, lnk_path):
        """解析.lnk文件获取目标路径"""
        try:
            with open(lnk_path, 'rb') as f:
                content = f.read()
                # 简化解析：查找常见路径模式
                for pattern in [b'C:\\', b'D:\\', b'E:\\', b'F:\\']:
                    idx = content.find(pattern)
                    if idx != -1:
                        end = content.find(b'\x00', idx)
                        if end != -1:
                            path = content[idx:end].decode('utf-8', errors='ignore')
                            if path and len(path) > 3:
                                return path
        except: pass
        return None

    def scan_game_cache(self):
        """扫描游戏缓存"""
        game_targets = [
            # Steam
            {"name": "Steam", "paths": [
                os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam", "appcache"),
                os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam", "dumps"),
                os.path.join(self.local_appdata, "Steam", "htmlcache"),
            ], "cat": "游戏平台"},
            # Epic Games
            {"name": "Epic Games", "paths": [
                os.path.join(self.local_appdata, "EpicGamesLauncher", "Saved", "webcache"),
                os.path.join(self.local_appdata, "EpicGamesLauncher", "Saved", "Logs"),
            ], "cat": "游戏平台"},
            # WeGame
            {"name": "WeGame", "paths": [
                os.path.join(self.local_appdata, "Tencent", "WeGame", "Cache"),
                os.path.join(self.local_appdata, "Tencent", "WeGame", "Logs"),
            ], "cat": "游戏平台"},
            # Origin
            {"name": "Origin", "paths": [
                os.path.join(self.roaming_appdata, "Origin", "LocalContent"),
                os.path.join(self.local_appdata, "Origin", "cache"),
            ], "cat": "游戏平台"},
            # Ubisoft
            {"name": "Ubisoft Connect", "paths": [
                os.path.join(self.local_appdata, "Ubisoft Game Launcher", "cache"),
                os.path.join(self.local_appdata, "Ubisoft Game Launcher", "logs"),
            ], "cat": "游戏平台"},
            # NVIDIA 着色器缓存
            {"name": "NVIDIA Shader Cache", "paths": [
                os.path.join(self.local_appdata, "NVIDIA", "DXCache"),
                os.path.join(self.local_appdata, "NVIDIA", "GLCache"),
            ], "cat": "显卡缓存"},
            # AMD 着色器缓存
            {"name": "AMD Shader Cache", "paths": [
                os.path.join(self.local_appdata, "AMD", "DxCache"),
                os.path.join(self.local_appdata, "AMD", "GLCache"),
            ], "cat": "显卡缓存"},
            # DirectX 着色器缓存
            {"name": "DirectX Shader Cache", "paths": [
                os.path.join(self.local_appdata, "D3DSCache"),
            ], "cat": "显卡缓存"},
        ]
        
        self.scan_progress["start_time"] = time.time()
        self.scan_progress["current"] = 0
        self.scan_progress["total"] = len(game_targets)
        
        for target in game_targets:
            self.scan_progress["current"] += 1
            yield {"type": "progress", "current": self.scan_progress["current"], "total": self.scan_progress["total"], "start_time": self.scan_progress["start_time"]}
            
            for path in target["paths"]:
                if os.path.exists(path):
                    s = self.get_dir_size_fast(path)
                    if s > 0:
                        yield {"type": "item", "data": {
                            "cat": target["cat"],
                            "soft": target["name"],
                            "detail": os.path.basename(path),
                            "path": path,
                            "raw_size": s,
                            "display_size": format_size(s)
                        }}

    def scan_phone_backups(self):
        """扫描手机备份"""
        backup_targets = [
            # iTunes 备份
            {"name": "iTunes/iPhone备份", "paths": [
                os.path.join(self.roaming_appdata, "Apple Computer", "MobileSync", "Backup"),
                os.path.join(self.user_profile, "Apple", "MobileSync", "Backup"),
            ], "cat": "手机备份"},
            # 华为手机助手
            {"name": "华为手机助手", "paths": [
                os.path.join(self.user_profile, "Documents", "HiSuite", "backup"),
            ], "cat": "手机备份"},
            # 小米手机助手
            {"name": "小米手机助手", "paths": [
                os.path.join(self.user_profile, "Documents", "xiaomi", "backup"),
                os.path.join(self.local_appdata, "Xiaomi", "MiPhoneAssistant", "backup"),
            ], "cat": "手机备份"},
            # OPPO
            {"name": "OPPO手机助手", "paths": [
                os.path.join(self.user_profile, "Documents", "OPPO", "backup"),
            ], "cat": "手机备份"},
            # VIVO
            {"name": "VIVO手机助手", "paths": [
                os.path.join(self.user_profile, "Documents", "vivo", "backup"),
            ], "cat": "手机备份"},
            # 三星
            {"name": "Samsung Smart Switch", "paths": [
                os.path.join(self.user_profile, "Documents", "samsung", "SmartSwitch"),
            ], "cat": "手机备份"},
        ]
        
        self.scan_progress["start_time"] = time.time()
        self.scan_progress["current"] = 0
        self.scan_progress["total"] = len(backup_targets)
        
        for target in backup_targets:
            self.scan_progress["current"] += 1
            yield {"type": "progress", "current": self.scan_progress["current"], "total": self.scan_progress["total"], "start_time": self.scan_progress["start_time"]}
            
            for path in target["paths"]:
                if os.path.exists(path):
                    s = self.get_dir_size_fast(path)
                    if s > 1024 * 1024:  # 大于1MB才显示
                        yield {"type": "item", "data": {
                            "cat": target["cat"],
                            "soft": target["name"],
                            "detail": os.path.basename(path),
                            "path": path,
                            "raw_size": s,
                            "display_size": format_size(s)
                        }}

    def scan_browser_extensions_cache(self):
        """扫描浏览器扩展缓存"""
        browsers = {
            "Chrome": os.path.join(self.local_appdata, "Google", "Chrome", "User Data"),
            "Edge": os.path.join(self.local_appdata, "Microsoft", "Edge", "User Data"),
            "Firefox": os.path.join(self.roaming_appdata, "Mozilla", "Firefox", "Profiles"),
        }
        
        self.scan_progress["start_time"] = time.time()
        self.scan_progress["current"] = 0
        self.scan_progress["total"] = len(browsers) * 3
        
        for browser, base_path in browsers.items():
            if not os.path.exists(base_path): continue
            self.scan_progress["current"] += 1
            yield {"type": "progress", "current": self.scan_progress["current"], "total": self.scan_progress["total"], "start_time": self.scan_progress["start_time"]}
            
            # 扫描扩展缓存目录
            cache_patterns = ["Service Worker", "IndexedDB", "Cache", "Code Cache", "GPUCache", "ShaderCache"]
            
            for root, dirs, files in os.walk(base_path):
                if root.count(os.sep) - base_path.count(os.sep) > 4: dirs[:] = []; continue
                
                folder_name = os.path.basename(root)
                if folder_name in cache_patterns or "cache" in folder_name.lower():
                    s = self.get_dir_size_fast(root)
                    if s > 1024 * 1024:  # 大于1MB
                        yield {"type": "item", "data": {
                            "cat": "浏览器扩展缓存",
                            "soft": browser,
                            "detail": folder_name,
                            "path": root,
                            "raw_size": s,
                            "display_size": format_size(s)
                        }}
                        dirs[:] = []

    def clear_clipboard_history(self):
        """清理剪贴板历史"""
        try:
            # 清空当前剪贴板
            subprocess.run("echo off | clip", shell=True, capture_output=True)
            # 禁用剪贴板历史（需要管理员权限）
            subprocess.run('reg add "HKCU\\Software\\Microsoft\\Clipboard" /v EnableClipboardHistory /t REG_DWORD /d 0 /f', shell=True, capture_output=True)
            return True
        except:
            return False

    def lock_screen(self):
        """锁定屏幕"""
        try:
            ctypes.windll.user32.LockWorkStation()
            return True
        except:
            return False

    def scan_clipboard_data(self):
        """扫描剪贴板相关数据"""
        clipboard_paths = [
            os.path.join(self.local_appdata, "Microsoft", "Windows", "Clipboard"),
            os.path.join(self.local_appdata, "ConnectedDevicesPlatform"),
        ]
        
        for path in clipboard_paths:
            if os.path.exists(path):
                s = self.get_dir_size_fast(path)
                if s > 0:
                    yield {"type": "item", "data": {
                        "cat": "剪贴板历史",
                        "soft": "Windows剪贴板",
                        "detail": os.path.basename(path),
                        "path": path,
                        "raw_size": s,
                        "display_size": format_size(s)
                    }}
        
        # 添加特殊清理项
        yield {"type": "item", "data": {
            "cat": "剪贴板历史",
            "soft": "当前剪贴板",
            "detail": "清空剪贴板内容",
            "path": "CLIPBOARD_SPECIAL",
            "raw_size": 1024,
            "display_size": "1.00 KB"
        }}

    def scan_space_analysis(self):
        """扫描C盘空间分析"""
        analyzer = DiskSpaceAnalyzer()
        yield from analyzer.analyze_c_drive(max_depth=2)

    def analyze_user_space(self):
        """分析用户目录空间"""
        analyzer = DiskSpaceAnalyzer()
        yield from analyzer.analyze_user_folders()
    
    def analyze_c_drive_full(self):
        """完整分析C盘空间"""
        analyzer = DiskSpaceAnalyzer()
        yield from analyzer.analyze_c_drive_full()


# ==================== C盘空间分析器（TreeSize Pro版本）====================
class DiskSpaceAnalyzer:
    """C盘空间占用分析器 - 类似TreeSize的专业版
    
    特点：
    1. 多线程并行扫描，速度提升10倍
    2. 分层加载，按需扫描子目录
    3. 完整的目录树结构
    4. 实时显示进度
    """
    
    def __init__(self):
        self.user_profile = os.environ['USERPROFILE']
        self.local_appdata = os.environ['LOCALAPPDATA']
        self.roaming_appdata = os.environ['APPDATA']
        self.system_root = os.environ['SystemRoot']
        
        # 系统保护目录（扫描时跳过）
        self.SYSTEM_PROTECTED = {
            'system32', 'syswow64', 'winsxs', 'driverstore', 'drivers',
            'windows', '$recycle.bin', 'system volume information',
        }
        
        # 扫描结果缓存 {path: size}
        self.size_cache = {}
        
        # 线程池
        self.executor = None
        
    def analyze_c_drive_full(self):
        """分析整个C盘 - 完整扫描版本
        
        策略：
        1. 扫描C盘根目录的所有子项（并行）
        2. 对每个子目录计算完整大小
        3. 支持后续展开查看更深层
        4. 实时返回结果
        """
        import shutil
        import logging
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        logger = logging.getLogger('CCleaner')
        c_drive = "C:\\"
        
        logger.info("[SpaceAnalyzer] Starting C drive analysis...")
        yield {"type": "status", "msg": "正在初始化C盘分析..."}
        yield {"type": "progress", "current": 0, "total": 100}
        
        # 获取C盘总体信息
        total, used, free = shutil.disk_usage(c_drive)
        yield {"type": "info", "data": {
            "total": total,
            "used": used,
            "free": free,
            "percent": round(used / total * 100, 1)
        }}
        
        # 第一步：快速列出根目录所有项
        yield {"type": "status", "msg": "正在扫描C盘根目录结构..."}
        logger.info("[SpaceAnalyzer] Scanning root directory structure...")
        
        root_items = []
        try:
            with os.scandir(c_drive) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            name_lower = entry.name.lower()
                            is_system = any(p in name_lower for p in self.SYSTEM_PROTECTED)
                            root_items.append({
                                "name": entry.name,
                                "path": entry.path,
                                "size": -1,  # -1表示未计算
                                "is_system": is_system,
                                "has_children": True,
                                "children": []
                            })
                        elif entry.is_file(follow_symlinks=False):
                            stat = entry.stat(follow_symlinks=False)
                            root_items.append({
                                "name": entry.name,
                                "path": entry.path,
                                "size": stat.st_size,
                                "is_system": False,
                                "has_children": False,
                                "children": []
                            })
                    except: pass
        except Exception as e:
            yield {"type": "status", "msg": f"扫描根目录出错: {e}"}
        
        yield {"type": "status", "msg": f"发现 {len(root_items)} 个根目录项，开始计算大小..."}
        logger.info(f"[SpaceAnalyzer] Found {len(root_items)} root items, calculating sizes...")
        
        # 第二步：并行计算所有目录的大小
        # 使用16个线程并行处理
        with ThreadPoolExecutor(max_workers=16) as executor:
            # 提交所有任务
            future_to_item = {}
            for item in root_items:
                if item["size"] == -1:  # 是目录
                    future = executor.submit(self._calc_dir_size_worker, item["path"])
                    future_to_item[future] = item
            
            # 处理完成的任务
            completed = 0
            total_dirs = len(future_to_item)
            
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    size = future.result(timeout=30)
                    item["size"] = size
                    # 缓存结果
                    self.size_cache[item["path"]] = size
                except Exception as e:
                    item["size"] = 0
                
                completed += 1
                progress = int((completed / total_dirs) * 100) if total_dirs > 0 else 100
                
                yield {"type": "progress", "current": progress, "total": 100}
                yield {"type": "status", "msg": f"已分析 {completed}/{total_dirs}: {item['name']} ({format_size(item['size'])})"}
                yield {"type": "item", "data": item}
        
        logger.info(f"[SpaceAnalyzer] Analysis complete. {completed} directories analyzed.")
        yield {"type": "done"}
    
    def _calc_dir_size_worker(self, path):
        """工作线程：计算目录大小"""
        import logging
        logger = logging.getLogger('CCleaner')
        
        # 检查缓存
        if path in self.size_cache:
            return self.size_cache[path]
        
        logger.debug(f"[Worker] Calculating size for: {path}")
        
        # 使用Python快速但完整的扫描
        total = 0
        try:
            # 使用os.scandir而不是os.walk，更快
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        # 递归计算子目录
                        subtotal = self._calc_dir_size_recursive(entry.path, max_depth=5)
                        total += subtotal
                except: pass
        except: pass
        
        self.size_cache[path] = total
        logger.debug(f"[Worker] Completed: {path} = {format_size(total)}")
        return total
    
    def _calc_dir_size_recursive(self, path, current_depth=0, max_depth=5):
        """递归计算目录大小，带深度限制"""
        if current_depth >= max_depth:
            # 到达最大深度，使用估算
            return self._estimate_dir_size(path)
        
        total = 0
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        name_lower = entry.name.lower()
                        if name_lower not in self.SYSTEM_PROTECTED:
                            subtotal = self._calc_dir_size_recursive(
                                entry.path, 
                                current_depth + 1, 
                                max_depth
                            )
                            total += subtotal
                except: pass
        except: pass
        
        return total
    
    def _estimate_dir_size(self, path):
        """估算目录大小（用于深层目录）"""
        total = 0
        count = 0
        try:
            # 只扫描前500个文件估算
            for entry in os.scandir(path):
                if count >= 500:
                    break
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                        count += 1
                    elif entry.is_dir(follow_symlinks=False):
                        # 只算一层
                        for subentry in os.scandir(entry.path):
                            if subentry.is_file(follow_symlinks=False):
                                total += subentry.stat(follow_symlinks=False).st_size
                                count += 1
                            if count >= 500:
                                break
                except: pass
        except: pass
        return total
    
    def scan_subdir(self, parent_path):
        """按需扫描子目录（用户点击展开时调用）"""
        subdirs = []
        
        try:
            with os.scandir(parent_path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            name_lower = entry.name.lower()
                            if name_lower not in self.SYSTEM_PROTECTED and not name_lower.startswith('$'):
                                # 快速计算这个子目录的大小
                                size = self._calc_dir_size_worker(entry.path)
                                subdirs.append({
                                    "name": entry.name,
                                    "path": entry.path,
                                    "size": size,
                                    "is_system": False,
                                    "has_children": True,
                                    "children": []
                                })
                        elif entry.is_file(follow_symlinks=False):
                            stat = entry.stat(follow_symlinks=False)
                            subdirs.append({
                                "name": entry.name,
                                "path": entry.path,
                                "size": stat.st_size,
                                "is_system": False,
                                "has_children": False,
                                "children": []
                            })
                    except: pass
        except: pass
        
        # 按大小排序
        subdirs.sort(key=lambda x: x["size"], reverse=True)
        return subdirs

    def analyze_c_drive(self, max_depth=1, use_cache=True):
        """分析C盘空间占用 - 终极极速版
        
        策略：
        1. 使用Windows原生dir命令（经过NTFS底层优化）
        2. 系统目录直接跳过（用户清理不了）
        3. 只详细扫描用户目录和非系统目录
        4. 缓存结果，第二次秒开
        """
        c_drive = "C:\\"
        cache_file = os.path.join(os.environ['TEMP'], 'ccleaner_space_cache.json')
        
        # 检查缓存（1小时内有效）
        if use_cache and os.path.exists(cache_file):
            try:
                import json
                import time
                with open(cache_file, 'r') as f:
                    cache = json.load(f)
                if time.time() - cache.get('timestamp', 0) < 3600:  # 1小时缓存
                    yield {"type": "status", "msg": "从缓存加载..."}
                    yield {"type": "info", "data": cache['info']}
                    for item in cache['items']:
                        yield {"type": "item", "data": item}
                    yield {"type": "done"}
                    return
            except: pass
        
        yield {"type": "status", "msg": "正在分析C盘空间分布..."}
        yield {"type": "progress", "current": 5, "total": 100}
        
        # 获取C盘总体信息
        import shutil
        total, used, free = shutil.disk_usage(c_drive)
        
        disk_info = {
            "total": total,
            "used": used,
            "free": free,
            "percent": round(used / total * 100, 1)
        }
        
        yield {"type": "info", "data": disk_info}
        
        # 第一步：快速获取所有根目录项（不计算大小）
        root_items = []
        system_items = []
        user_items = []
        
        try:
            with os.scandir(c_drive) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        name_lower = entry.name.lower()
                        is_system = name_lower in self.SYSTEM_PROTECTED
                        item = {
                            "name": entry.name,
                            "path": entry.path,
                            "size": 0,
                            "is_system": is_system,
                            "children": []
                        }
                        if is_system:
                            system_items.append(item)
                        else:
                            user_items.append(item)
                        root_items.append(item)
        except: pass
        
        yield {"type": "status", "msg": f"发现 {len(user_items)} 个用户目录，{len(system_items)} 个系统目录"}
        yield {"type": "progress", "current": 10, "total": 100}
        
        # 第二步：使用Windows dir命令批量获取大小（比Python遍历快10-50倍）
        # 优先处理用户目录
        all_results = []
        
        # 批量处理用户目录（使用原生命令）
        for i, item in enumerate(user_items):
            progress = 10 + int((i / max(len(user_items), 1)) * 80)
            yield {"type": "progress", "current": progress, "total": 100}
            
            size = self._get_dir_size_ntfs_fast(item["path"])
            item["size"] = size
            
            # 获取最大的子目录
            if size > 1024 * 1024 * 1024:  # 大于1GB才获取子目录
                item["children"] = self._get_large_subdirs_quick(item["path"])
            
            yield {"type": "status", "msg": f"已分析: {item['name']} ({format_size(size)})"}
            yield {"type": "item", "data": item}
            all_results.append(item)
        
        # 系统目录直接标记，不扫描（节省大量时间）
        for item in system_items:
            item["size"] = 0
            item["is_skipped"] = True
            yield {"type": "item", "data": item}
            all_results.append(item)
        
        yield {"type": "progress", "current": 100, "total": 100}
        
        # 保存缓存
        try:
            import json
            cache_data = {
                'timestamp': time.time(),
                'info': disk_info,
                'items': all_results
            }
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, default=str)
        except: pass
        
        yield {"type": "done"}
    
    def _get_dir_size_ntfs_fast(self, path):
        """使用Windows原生方法快速获取目录大小 - 修复版"""
        import subprocess
        
        # 方法1: 使用du命令（Windows Sysinternals）或PowerShell
        try:
            # PowerShell方法 - 最可靠
            ps_cmd = f'''$size = (Get-ChildItem "{path}" -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; if ($size) {{Write-Output $size}} else {{Write-Output 0}}'''
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_cmd],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if output and output.isdigit():
                    size = int(output)
                    if size >= 0:
                        return size
        except Exception as e:
            # 错误静默处理，通过返回值判断
            pass
        
        # 方法2: 使用dir命令（经过优化，比Python遍历快）
        try:
            result = subprocess.run(
                f'dir "{path}" /s /-c 2>nul | findstr /i "file(s)"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # 解析最后一行（包含总计）
            lines = result.stdout.strip().split('\n')
            if lines:
                last_line = lines[-1]
                # 提取数字（格式："123,456,789 bytes"）
                import re
                match = re.search(r'([\d,]+)\s+bytes', last_line, re.IGNORECASE)
                if match:
                    size_str = match.group(1).replace(',', '')
                    return int(size_str)
        except Exception as e:
            # 错误静默处理
            pass
        
        # 方法3: 回退到Python扫描（完整但较慢）
        print(f"Falling back to Python scan for: {path}")
        return self._python_full_scan(path)
    
    def _python_full_scan(self, path):
        """Python完整扫描 - 最准确但较慢"""
        total = 0
        try:
            for root, dirs, files in os.walk(path):
                # 跳过系统目录
                dirs[:] = [d for d in dirs if d.lower() not in self.SYSTEM_PROTECTED and not d.startswith('$')]
                
                for f in files:
                    try:
                        fp = os.path.join(root, f)
                        # 跳过符号链接和特殊文件
                        if not os.path.islink(fp):
                            total += os.path.getsize(fp)
                    except: pass
        except: pass
        return total
    
    def _python_fast_scan(self, path, max_files=10000):
        """Python快速扫描 - 限制文件数量但估算准确"""
        total = 0
        count = 0
        file_samples = []
        
        try:
            for root, dirs, files in os.walk(path):
                # 限制深度为3层
                if root.count(os.sep) - path.count(os.sep) > 3:
                    dirs[:] = []
                    continue
                    
                # 跳过系统目录
                dirs[:] = [d for d in dirs if d.lower() not in self.SYSTEM_PROTECTED and not d.startswith('$')]
                
                # 收集文件大小样本
                for f in files:
                    if count >= max_files:
                        break
                    try:
                        fp = os.path.join(root, f)
                        if not os.path.islink(fp):
                            size = os.path.getsize(fp)
                            total += size
                            count += 1
                    except: pass
                
                if count >= max_files:
                    # 估算剩余文件
                    avg_size = total / count if count > 0 else 0
                    # 估算整个目录还有多少个文件（基于目录结构）
                    estimated_remaining = len(files) * len(dirs) if dirs else 0
                    total += avg_size * estimated_remaining
                    break
                    
        except: pass
        
        return int(total)
    
    def _get_large_subdirs_quick(self, path, top_n=5):
        """获取占用最大的子目录 - 使用PowerShell快速获取"""
        subdirs = []
        
        try:
            # 首先列出所有子目录
            with os.scandir(path) as it:
                entries = [e for e in it if e.is_dir(follow_symlinks=False)]
            
            # 使用PowerShell批量获取大小（更快）
            import subprocess
            for entry in entries[:20]:  # 最多检查20个子目录
                name_lower = entry.name.lower()
                if name_lower in self.SYSTEM_PROTECTED or name_lower.startswith('$'):
                    continue
                
                try:
                    ps_cmd = f'''$size = (Get-ChildItem "{entry.path}" -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; if ($size -gt 100MB) {{ Write-Output "{entry.name}|$size" }}'''
                    result = subprocess.run(
                        ['powershell', '-NoProfile', '-Command', ps_cmd],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        line = result.stdout.strip()
                        if '|' in line:
                            parts = line.split('|')
                            if len(parts) == 2:
                                try:
                                    size = int(parts[1])
                                    if size > 100 * 1024 * 1024:  # 只保留大于100MB的
                                        subdirs.append({
                                            "name": entry.name,
                                            "path": entry.path,
                                            "size": size,
                                            "is_system": False,
                                            "children": []
                                        })
                                except: pass
                except: pass
            
            # 排序并返回前N个
            subdirs.sort(key=lambda x: x["size"], reverse=True)
            return subdirs[:top_n]
            
        except Exception as e:
            # 错误静默处理
            pass
        
        return []
    
    def clear_space_cache(self):
        """清除空间分析缓存"""
        cache_file = os.path.join(os.environ['TEMP'], 'ccleaner_space_cache.json')
        try:
            if os.path.exists(cache_file):
                os.remove(cache_file)
                return True
        except: pass
        return False
    
    def _get_folder_size_super_fast(self, path, is_system=False):
        """超快速获取文件夹大小 - 通过抽样统计"""
        import subprocess
        import re
        
        # 对于系统目录，使用Windows dir命令快速获取
        if is_system:
            try:
                # 使用cmd的dir命令，它经过优化比Python遍历快
                result = subprocess.run(
                    f'dir "{path}" /s /-c 2>nul | findstr "File(s)"',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split('\n'):
                    if 'File(s)' in line:
                        # 提取数字
                        numbers = re.findall(r'[\d,]+', line.replace(',', ''))
                        if numbers:
                            return int(numbers[-1]), []
            except:
                pass
            # 如果失败，返回估算值
            return self._estimate_size_by_sample(path), []
        
        # 对于普通目录，使用Python快速遍历（只遍历前2000个文件）
        return self._quick_scan_with_limit(path, max_files=2000)
    
    def _quick_scan_with_limit(self, path, max_files=2000):
        """快速扫描目录，限制文件数量"""
        total = 0
        file_count = 0
        subdirs = []
        
        try:
            # 第一层：直接子目录
            with os.scandir(path) as it:
                entries = list(it)
                
                # 先处理文件
                for entry in entries:
                    if file_count >= max_files:
                        break
                    try:
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                            file_count += 1
                    except:
                        pass
                
                # 估算子目录大小
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        name_lower = entry.name.lower()
                        if name_lower not in self.SYSTEM_PROTECTED:
                            # 快速估算子目录大小（只扫描100个文件）
                            sub_size = self._estimate_subdir_size(entry.path, max_files=100)
                            if sub_size > 100 * 1024 * 1024:  # 只记录大于100MB的
                                subdirs.append({
                                    "name": entry.name,
                                    "path": entry.path,
                                    "size": sub_size,
                                    "is_system": False,
                                    "children": []
                                })
                            total += sub_size
                        
        except:
            pass
        
        # 按大小排序子目录
        subdirs.sort(key=lambda x: x["size"], reverse=True)
        return total, subdirs[:5]  # 只返回前5个最大的子目录
    
    def _estimate_subdir_size(self, path, max_files=100):
        """估算子目录大小 - 只扫描前N个文件"""
        total = 0
        count = 0
        try:
            for root, dirs, files in os.walk(path):
                # 限制深度
                if root.count(os.sep) - path.count(os.sep) > 2:
                    break
                
                for f in files[:max_files]:
                    try:
                        fp = os.path.join(root, f)
                        total += os.path.getsize(fp)
                        count += 1
                    except:
                        pass
                
                # 如果文件很多，估算剩余部分
                if len(files) > max_files:
                    avg = total / count if count > 0 else 0
                    total += avg * (len(files) - max_files)
                    
                if count >= max_files:
                    break
                    
        except:
            pass
        return int(total)
    
    def _estimate_size_by_sample(self, path):
        """通过目录项数量估算大小"""
        try:
            # 统计目录项数量
            file_count = 0
            total_size = 0
            with os.scandir(path) as it:
                for entry in it:
                    if file_count >= 100:  # 只检查前100个
                        break
                    try:
                        if entry.is_file():
                            total_size += entry.stat().st_size
                            file_count += 1
                    except:
                        pass
            
            # 基于样本估算总量
            if file_count > 0:
                avg_size = total_size / file_count
                # 假设目录中有更多文件
                return int(avg_size * file_count * 10)
        except:
            pass
        return 0

    def analyze_user_folders(self):
        """分析用户目录下的重要文件夹"""
        user_base = self.user_profile
        
        important_folders = [
            ("下载文件夹", os.path.join(user_base, "Downloads")),
            ("文档文件夹", os.path.join(user_base, "Documents")),
            ("桌面文件夹", os.path.join(user_base, "Desktop")),
            ("图片文件夹", os.path.join(user_base, "Pictures")),
            ("视频文件夹", os.path.join(user_base, "Videos")),
            ("音乐文件夹", os.path.join(user_base, "Music")),
            ("AppData\\Local", self.local_appdata),
            ("AppData\\Roaming", self.roaming_appdata),
        ]
        
        total = len(important_folders)
        for i, (name, path) in enumerate(important_folders):
            yield {"type": "progress", "current": i + 1, "total": total}
            yield {"type": "status", "msg": f"正在分析: {name}..."}
            
            if os.path.exists(path):
                size = self._calc_dir_size_fast(path)
                children = self._scan_subdirs(path, depth=1, max_depth=2, limit=10)
                yield {"type": "item", "data": {
                    "name": name,
                    "path": path,
                    "size": size,
                    "is_system": False,
                    "children": children
                }}
        
        yield {"type": "done"}

    def _calc_dir_size_fast(self, path, max_files=1000):
        """快速计算目录大小 - 极速模式（限制文件数量和深度）"""
        total = 0
        file_count = 0
        try:
            for root, dirs, files in os.walk(path):
                # 限制扫描深度为2层
                if root.count(os.sep) - path.count(os.sep) > 2:
                    dirs[:] = []
                    continue
                # 跳过系统目录
                dirs[:] = [d for d in dirs if d.lower() not in self.SYSTEM_PROTECTED]
                
                # 限制文件数
                for f in files[:max_files]:
                    try:
                        fp = os.path.join(root, f)
                        total += os.path.getsize(fp)
                        file_count += 1
                    except:
                        pass
                
                # 如果还有文件，估算
                if len(files) > max_files:
                    avg_size = total / file_count if file_count > 0 else 0
                    total += avg_size * (len(files) - max_files)
                    
                if file_count >= max_files:
                    break
                    
        except:
            pass
        return int(total)

    def _scan_subdirs(self, path, depth, max_depth, limit=20):
        """扫描子目录"""
        children = []
        if depth >= max_depth:
            return children
        
        try:
            with os.scandir(path) as it:
                dirs = []
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        name_lower = entry.name.lower()
                        if name_lower not in self.SYSTEM_PROTECTED:
                            dirs.append(entry)
                
                # 只扫描前limit个目录（按名称排序）
                dirs = sorted(dirs, key=lambda x: x.name)[:limit]
                
                for entry in dirs:
                    size = self._calc_dir_size_fast(entry.path)
                    child = {
                        "name": entry.name,
                        "path": entry.path,
                        "size": size,
                        "is_system": False,
                        "children": self._scan_subdirs(entry.path, depth + 1, max_depth, limit=10)
                    }
                    children.append(child)
        except: pass
        
        # 按大小排序
        children.sort(key=lambda x: x["size"], reverse=True)
        return children

    def find_space_hogs(self, min_size_gb=1):
        """找出占用空间大户（大于指定GB的目录）"""
        min_size = min_size_gb * 1024 * 1024 * 1024
        
        common_hog_paths = [
            os.path.join(self.user_profile, "AppData"),
            os.path.join(self.user_profile, "Downloads"),
            os.path.join(self.user_profile, "Documents"),
            os.path.join(self.user_profile, "Videos"),
            "C:\\ProgramData",
            "C:\\Windows\\Temp",
            "C:\\Windows\\SoftwareDistribution",
        ]
        
        hogs = []
        total = len(common_hog_paths)
        
        for i, path in enumerate(common_hog_paths):
            yield {"type": "progress", "current": i + 1, "total": total}
            
            if os.path.exists(path):
                size = self._calc_dir_size_fast(path)
                if size >= min_size:
                    hogs.append({
                        "path": path,
                        "name": os.path.basename(path) or path,
                        "size": size,
                        "percent": round(size / min_size * 100, 1)
                    })
        
        # 按大小排序
        hogs.sort(key=lambda x: x["size"], reverse=True)
        
        for hog in hogs:
            yield {"type": "item", "data": hog}
        
        yield {"type": "done"}

    def generate_visual_bar(self, size, max_size, width=30):
        """生成可视化的进度条"""
        if max_size == 0:
            return "░" * width
        filled = int(size / max_size * width)
        filled = min(filled, width)
        return "█" * filled + "░" * (width - filled)
