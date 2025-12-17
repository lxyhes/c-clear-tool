# C-Clear-Tool (C盘深度清理助手)

**v4.0 分类增强版** - 更智能、更快速、更懂你的 Windows C 盘清理工具。

![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Platform](https://img.shields.io/badge/platform-Windows-blue.svg) ![Python](https://img.shields.io/badge/python-3.x-green.svg)

## 🌟 核心特性 (v4.0)

### 1. 📊 智能树状分类
告别杂乱无章的文件列表！本工具采用**智能分类引擎**，自动将垃圾文件归类：
*   📂 **系统垃圾**: 临时文件、Prefetch、Windows 更新缓存等。
*   🌐 **浏览器缓存**: Chrome, Edge, Firefox 等浏览器缓存。
*   💬 **社交通讯**: 微信 (WeChat)、QQ、钉钉、飞书等图片/视频缓存。
*   🎮 **游戏平台**: Steam, Epic Games, Origin 等下载缓存。
*   🛠️ **开发工具**: VS Code, JetBrains, Python/Pip 缓存。
*   🎨 **设计软件**: Adobe, Blender, Autodesk 临时渲染文件。

### 2. ⚡ 极速流式扫描
*   **零等待**: 采用生成器 (Generator) + 消息队列 (Queue) 架构，点击开始即刻出结果，无需漫长等待。
*   **高性能**: 多线程并行扫描 + `os.scandir` 底层优化，即使面对数万个小文件也能瞬间处理。
*   **零过滤**: 无论文件多小，只要是垃圾就会被揪出来，绝不放过任何 1KB。

### 3. 📦 僵尸安装包清理 (**New!**)
*   痛点解决：下载文件夹里堆满了几个月前下载的安装包？
*   功能：自动扫描 `Downloads` 目录下**超过 30 天未修改**的 `.exe`, `.msi`, `.zip`, `.iso` 文件，帮您一键释放大量空间。

### 4. 🐘 大文件雷达
*   全盘扫描桌面、文档、下载、视频目录。
*   快速定位体积超过 **100MB** 的“巨无霸”文件。
*   支持右键一键打开所在文件夹，方便人工确认和删除。

### 5. 🛡️ 安全至上
*   **白名单机制**: 严格避开 `User Data` (浏览器配置), `SaveGames` (存档), `Profile` 等敏感目录。
*   **占用跳过**: 删除时遇到正在运行的程序文件会自动跳过，防止系统或软件崩溃。

---

## 🚀 快速开始

### 运行要求
*   Windows 10 / 11
*   Python 3.6+

### 使用方法
1.  下载本项目。
2.  找到 **`start_cleaner.bat`**。
3.  **右键点击** -> 选择 **“以管理员身份运行”** (为了清理 C:\Windows\Temp 等系统目录)。
4.  在界面中选择相应的功能 Tab 进行清理。

---

## 🛠️ 常见问题

**Q: 为什么需要管理员权限？**
A: 普通权限只能清理用户个人的临时文件。清理 Windows 系统更新缓存、错误报告和系统临时目录需要管理员权限。

**Q: 会误删我的微信聊天记录吗？**
A: **不会**。工具通过白名单严格限制，只删除 `FileStorage\Image`, `Video`, `Cache` 等缓存目录，绝对不会触碰 `Msg` (消息数据库) 等核心文件。

**Q: 扫描速度取决于什么？**
A: 取决于您的硬盘类型 (SSD 极快，HDD 较慢) 和小文件的数量。v4.0 版本已针对海量小文件做了极致优化。

---

## 📄 许可证
MIT License