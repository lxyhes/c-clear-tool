# C-Clear-Tool (C盘深度清理助手)

**v4.1 增强体验版** - 更智能、更流畅、更懂你的 Windows C 盘清理工具。

![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Platform](https://img.shields.io/badge/platform-Windows-blue.svg) ![Python](https://img.shields.io/badge/python-3.x-green.svg)

## 🌟 核心特性 (v4.1 Update)

### 1. 🚀 自动化与性能体验 (**New!**)
*   **自动提权**: 不再需要繁琐的右键操作！程序启动时会自动检测并请求管理员权限，确保能清理系统级垃圾。
*   **实时反馈**: 新增底部**状态栏**和**动态进度条**，实时显示正在扫描的目录，拒绝界面“假死”。
*   **UI 零卡顿**: 优化了底层多线程消息队列机制，即使扫描出数万个小文件，界面依然丝般顺滑。

### 2. 📊 智能树状分类
告别杂乱无章的文件列表！本工具采用**智能分类引擎**，自动将垃圾文件归类：
*   📂 **系统垃圾**: 临时文件、Prefetch、Windows 更新缓存、错误报告。
*   🌐 **浏览器缓存**: Chrome, Edge, Firefox 等浏览器缓存。
*   💬 **社交通讯**: 微信 (WeChat)、QQ、钉钉、飞书等图片/视频缓存。
*   🎮 **游戏平台**: Steam, Epic Games, Origin 等下载缓存。
*   🛠️ **开发工具**: VS Code, JetBrains, Python/Pip 缓存。
*   🎨 **设计软件**: Adobe, Blender, Autodesk 临时渲染文件。

### 3. 📦 僵尸安装包清理
*   痛点解决：下载文件夹里堆满了几个月前下载的安装包？
*   功能：自动扫描 `Downloads` 目录下**超过 30 天未修改**的 `.exe`, `.msi`, `.zip`, `.iso` 文件，帮您一键释放大量空间。

### 4. 🐘 大文件雷达
*   全盘扫描桌面、文档、下载、视频目录。
*   快速定位体积超过 **100MB** 的“巨无霸”文件。
*   支持右键一键打开所在文件夹，方便人工确认和删除。

---

## 🚀 快速开始

### 运行要求
*   Windows 10 / 11
*   Python 3.6+
*   依赖库：`tkinter` (Python 内置，通常无需安装)

### 使用方法
1.  下载本项目。
2.  双击 **`start_cleaner.bat`** (或者直接运行 `python cleaner.py`)。
3.  程序会自动请求管理员权限（点击“是”）。
4.  在界面中点击 **“开始扫描”**。
5.  勾选想要删除的项目，点击 **“立即清理”**。

---

## 🛠️ 常见问题

**Q: 为什么需要管理员权限？**
A: 清理 Windows 系统更新缓存 (SoftwareDistribution)、错误报告和系统临时目录 (Windows\Temp) 必须拥有管理员权限。v4.1 版本已实现自动获取。

**Q: 扫描速度取决于什么？**
A: 取决于您的硬盘类型 (SSD 极快) 和文件数量。我们已经针对海量小文件遍历做了极致优化。

**Q: 安全吗？会误删文件吗？**
A: **非常安全**。工具内置白名单机制，严格避开 `User Data` (配置), `SaveGames` (存档), `Msg` (聊天记录数据库) 等敏感目录，只针对临时缓存文件下手。

---

## 📄 许可证
MIT License