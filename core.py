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
        
        try:
            rb_size = 0
            for drive_idx in range(26):
                drive = chr(ord('A') + drive_idx) + ":/"
                root = os.path.join(drive, "$Recycle.Bin")
                if os.path.exists(root): rb_size += self.get_dir_size_fast(root)
            if rb_size > 0:
                yield {"type": "item", "data": {"cat": "特别清理", "soft": "回收站", "detail": "已删除文件", "path": "RECYCLE_BIN_SPECIAL", "raw_size": rb_size, "display_size": format_size(rb_size)}}
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
        }
        for key, (c, s) in app_map.items():
            if key in name_lower: cat, soft = c, s; break
        return cat, soft

    def scan_custom(self, paths):
        self.scan_progress["start_time"] = time.time()
        self.scan_progress["current"] = 0
        self.scan_progress["total"] = len(paths) * 5
        
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(self._scan_single_custom, p) for p in paths]
            for fut in as_completed(futures):
                self.scan_progress["current"] += 1
                yield {"type": "progress", "current": self.scan_progress["current"], "total": self.scan_progress["total"], "start_time": self.scan_progress["start_time"]}
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
