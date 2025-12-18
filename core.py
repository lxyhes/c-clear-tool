import os
import time
import winreg
import ctypes
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
        
        # 扫描黑名单：这些目录文件极多且不可能有社交/办公账号数据，跳过可节省 60% 以上时间
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
        """极致优化的目录大小计算"""
        total = 0
        try:
            stack = [path]
            while stack:
                current = stack.pop()
                try:
                    with os.scandir(current) as it:
                        for entry in it:
                            try:
                                if entry.is_file(follow_symlinks=False): 
                                    total += entry.stat(follow_symlinks=False).st_size
                                elif entry.is_dir(follow_symlinks=False): 
                                    stack.append(entry.path)
                            except: pass
                except: pass
        except: pass
        return total

    def scan_generator(self):
        # 1. 回收站
        try:
            rb_size = 0
            for drive_idx in range(26):
                drive = chr(ord('A') + drive_idx) + ":\\"
                root = os.path.join(drive, "$Recycle.Bin")
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
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        drives = []
        for i in range(26):
            if bitmask & (1 << i):
                d = chr(ord('A') + i) + ":\\"
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

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self._analyze_social_root, path, name, social_targets) for path, name in unique_tasks.items()]
            for fut in as_completed(futures):
                for item in fut.result(): yield item

    def scan_resignation_targets(self, custom_paths=[]):
        """离职专清 2.0 极速加速版：分治扫描 + 智能避让 + 全隐私覆盖"""
        # 1. 获取驱动器列表
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        drives = []
        for i in range(26):
            if bitmask & (1 << i):
                d = chr(ord('A') + i) + ":\\"
                if ctypes.windll.kernel32.GetDriveTypeW(d) == 3: drives.append(d)

        app_targets = [
            {"name": "微信 WeChat", "patterns": ["WeChat Files"], "cat": "通讯软件"},
            {"name": "腾讯 QQ", "patterns": ["Tencent Files", "TencentFiles"], "cat": "通讯软件"},
            {"name": "钉钉 DingTalk", "patterns": ["DingTalk"], "cat": "办公软件"},
            {"name": "飞书 Feishu", "patterns": ["Feishu", "Lark"], "cat": "办公软件"}
        ]

        # 任务分发：一级子目录扫描
        scan_tasks = []
        for d in drives:
            try:
                with os.scandir(d) as it:
                    for entry in it:
                        if entry.is_dir():
                            if entry.name.lower() in self.SYSTEM_EXCLUDE: continue
                            scan_tasks.append(entry.path)
                scan_tasks.append(d)
            except: pass

        # 2. 高并发雷达扫描
        with ThreadPoolExecutor(max_workers=24) as executor:
            futures = [executor.submit(self._radar_scan_sub_folder, path, app_targets) for path in scan_tasks]
            for fut in as_completed(futures):
                for item in fut.result(): yield item

        # 3. 系统隐私
        for item in self._scan_system_privacy(): yield item

        # 4. 自定义目录
        for cp in custom_paths:
            if os.path.exists(cp):
                s = self.get_dir_size_fast(cp)
                if s > 0:
                    yield {"type": "item", "data": {
                        "cat": "自定义敏感目录", "soft": "手动添加",
                        "detail": os.path.basename(cp), "path": cp, 
                        "raw_size": s, "display_size": format_size(s)
                    }}

    def _radar_scan_sub_folder(self, folder_path, targets):
        results = []
        try:
            folder_name = os.path.basename(folder_path).lower()
            for target in targets:
                if any(p.lower() == folder_name for p in target['patterns']):
                    return self._extract_account_folders(folder_path, target)
            
            with os.scandir(folder_path) as it:
                for entry in it:
                    if entry.is_dir():
                        e_name_low = entry.name.lower()
                        for target in targets:
                            if any(p.lower() == e_name_low for p in target['patterns']):
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
                            accounts.append({"type": "item", "data": {
                                "cat": target['cat'], "soft": target['name'],
                                "detail": f"账号数据: {entry.name}", "path": entry.path, 
                                "raw_size": s, "display_size": format_size(s)
                            }})
        except: pass
        return accounts

    def _scan_system_privacy(self):
        privacy_results = []
        local_appdata = self.local_appdata
        roaming_appdata = self.roaming_appdata
        user_home = self.user_profile

        # A. 浏览器
        browsers = {
            "Chrome": os.path.join(local_appdata, "Google", "Chrome", "User Data"),
            "Edge": os.path.join(local_appdata, "Microsoft", "Edge", "User Data")
        }
        for b_name, b_path in browsers.items():
            if os.path.exists(b_path):
                for root, dirs, files in os.walk(b_path):
                    if "Login Data" in files or "Cookies" in files:
                        for target in ["Login Data", "Cookies", "History", "Web Data"]:
                            fp = os.path.join(root, target)
                            if os.path.exists(fp):
                                privacy_results.append({"type": "item", "data": {
                                    "cat": "浏览器隐私", "soft": b_name, "detail": f"凭据/历史: {target}",
                                    "path": fp, "raw_size": os.path.getsize(fp), "display_size": format_size(os.path.getsize(fp))
                                }})
                    if root.count(os.sep) - b_path.count(os.sep) > 2: dirs[:] = []; continue

        # B. 邮件
        mail_paths = [
            ("Outlook", os.path.join(local_appdata, "Microsoft", "Outlook")),
            ("Foxmail", os.path.join(local_appdata, "Foxmail", "Storage")),
            ("Foxmail", os.path.join(user_home, "Documents", "Foxmail"))
        ]
        for m_name, m_path in mail_paths:
            if os.path.exists(m_path):
                s = self.get_dir_size_fast(m_path)
                if s > 0:
                    privacy_results.append({"type": "item", "data": {
                        "cat": "邮件存档", "soft": m_name, "detail": "邮件数据库(.ost/.pst)",
                        "path": m_path, "raw_size": s, "display_size": format_size(s)
                    }})

        # C. 凭据
        ssh_path = os.path.join(user_home, ".ssh")
        if os.path.exists(ssh_path):
            s = self.get_dir_size_fast(ssh_path)
            privacy_results.append({"type": "item", "data": { "cat": "开发凭据", "soft": "SSH", "detail": "服务器私钥", "path": ssh_path, "raw_size": s, "display_size": format_size(s) }})
        
        ps_history = os.path.join(roaming_appdata, "Microsoft", "Windows", "PowerShell", "PSReadLine", "ConsoleHost_history.txt")
        if os.path.exists(ps_history):
            privacy_results.append({"type": "item", "data": { "cat": "指令历史", "soft": "PowerShell", "detail": "命令历史记录", "path": ps_history, "raw_size": os.path.getsize(ps_history), "display_size": format_size(os.path.getsize(ps_history)) }})

        ide_paths = [("VS Code", os.path.join(roaming_appdata, "Code", "User", "workspaceStorage"))]
        for i_name, i_path in ide_paths:
            if os.path.exists(i_path):
                s = self.get_dir_size_fast(i_path)
                privacy_results.append({"type": "item", "data": { "cat": "IDE 记录", "soft": i_name, "detail": "项目历史与缓存", "path": i_path, "raw_size": s, "display_size": format_size(s) }})

        return privacy_results

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