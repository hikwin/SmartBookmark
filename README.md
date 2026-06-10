# TidyMarks

[English](#english) | [中文](#中文-1)

---

## English

**TidyMarks** is a premium, local-first desktop application designed to organize, clean, and categorize your Chrome bookmarks. By parsing standard Netscape HTML bookmark exports into a local SQLite database, it gives you complete control over your web archives with an intuitive, modern dark-themed dashboard interface.

### Key Features

* **🤖 Offline AI Classification**: Automatically organizes your bookmarks into categories (e.g., Development, Education, AI, Social, and Shopping) based on domain patterns and keywords, without sending any data to external servers.
* **🏠 Intranet Auto-detection**: Automatically isolates local hostnames, private IP segments (like `192.168.x.x`), and LAN addresses under a unified local category using URL-only checks.
* **⚡ Multi-threaded Link Checker**: Validates bookmark availability in parallel with support for cancel operations. Automatically handles network exceptions, SSL errors, and redirects.
* **🔍 Smart Deduplication & Filter**: Groups duplicate URLs with alternating visual tracks, allowing you to choose whether to keep the oldest or latest copy. Filter links by fine-grained HTTP status codes (such as `200`, `404`, `403`, `50x`, and network timeouts).
* **↩️ Snapshot-based Version Control**: Backs up your initial imported state and takes snapshots before every write operation, letting you safely undo/redo any step or restore back to default.
* **🎨 Premium Dark Dashboard**: Features modern typography, hover micro-animations, and a beautifully balanced visual theme that follows best design practices.

### Getting Started

#### Prerequisites
* Python 3.8 or higher

#### Installation
1. Clone this repository or download the source files.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

#### Running the Application
Launch the graphical interface by running:
```bash
python main.py
```

---

## 中文

**TidyMarks** 是一款高颜值、本地优先的桌面书签智能整理与清洗工具。它能够将您从 Chrome 导出的标准 Netscape HTML 书签文件导入到本地 SQLite 数据库中进行解析和清理，并通过精美且富有交互感的深色系仪表盘界面为您呈现实时的数据面板。

### 核心功能

* **🤖 离线 AI 分类引擎**：完全基于本地规则匹配域名后缀与中英文关键词，不依赖外部服务器，一键将书签整理归类（如开发工具、学习教育、人工智能、购物电商、工作效率等）。
* **🏠 内网地址自动识别**：自动根据 URL 结构（如 `localhost`、`127.0.0.1`、私有 IP、NAS 主机名等）将内网及局域网书签划分进本地分类下，不参与任何公网标题的模糊匹配。
* **⚡ 多线程网址可用性检测**：多线程并发检测网址可用性，支持一键随时中止，完美捕获并显示超时、证书失效、网络不可达等各类连接异常。
* **🔍 智能去重与详细状态码过滤**：分组高亮展示所有重复链接，提供“保留最早/最晚”的去重决策策略。状态过滤栏支持针对 `200`、`404`、`403`、`50x` 服务器错误以及网络超时进行针对性筛选。
* **↩️ 安全的快照式历史版本控制**：初次导入自动创建 `Version 0` 备份，每次修改或去重操作前均会自动创建版本快照。支持多步「撤销上一步」和一键「还原初始导入状态」，数据无忧，绝对不会修改或损坏您本地硬盘上的原始 HTML 文件。
* **🎨 极客风深色主题仪表盘**：采用现代无衬线字体，配合精巧平滑的微交互和色调调和的卡片式布局，带来极为专业、舒适的使用体验。

### 快速开始

#### 环境要求
* Python 3.8 或更高版本

#### 安装步骤
1. 克隆本仓库或下载源码文件。
2. 安装项目依赖：
   ```bash
   pip install -r requirements.txt
   ```

#### 启动运行
在项目根目录下，运行以下命令启动 GUI 界面：
```bash
python main.py
```

### 声明
本项目完全在本地离线运行。数据库的清空或重置操作仅对本软件的本地缓存数据库生效，**绝不会以任何形式修改、覆盖或损坏您在本地硬盘上的原始书签文件**。
