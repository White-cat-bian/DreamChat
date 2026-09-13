# DreamChat — 桌面 AI 聊天客户端 ✨

> **白色-彼岸** 打造的跨平台 AI 助手，支持 AIScript v1.0 角色人格系统。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![customtkinter](https://img.shields.io/badge/UI-customtkinter-green.svg)](https://github.com/TomSchimansky/customtkinter)
[![Status](https://img.shields.io/badge/status-active-brightgreen.svg)](#)

## 简介

**DreamChat** 是一款轻量级桌面聊天应用，连接任意 OpenAI 兼容 API（如 Agnes AI、OpenAI、Ollama 等）。核心亮点是独创的 **AIScript v1.0** 角色配置系统——一份 `.aiscript` 文件即可定义一个完整 AI 人格。

## 功能特性

| 类别 | 说明 |
|---|---|
| 💬 **双模式** | 默认助手模式 + 角色人格模式 |
| 🎭 **AIScript v1.0** | 支持 `::META` / `::RULES` / `::VARS` / `::KNW` / `::CORPUS` / `::FLOW` 六区块解析 |
| 🎨 **5 主题** | 午夜极光、绯樱隐士（粉）、深海秘境、翡翠幽林、暮火余烬 |
| 🤖 **模型自动获取** | 设置 API Key + Base URL 后一键拉取可用模型列表 |
| 🔐 **配置本地化** | 所有配置（含 API Key）保存在本地 `data/config.json`，不上传 |
| 📖 **内置文档** | 使用说明 + AIScript V1.0 完整规范，文档按钮直接查阅 |
| 🖱️ **自动滚动** | 新消息自动滚到底部，多主题切换即时刷新全部消息颜色 |
| 📦 **PyInstaller 打包** | 一条命令生成独立 EXE（约 28 MB），无 Python 依赖可直接分发 |

## 快速开始

### 从源码运行
```bash
# 安装依赖
pip install -r requirements.txt

# 启动
python dreamchat.py
```

### 使用预编译 EXE（Windows）
下载 `DreamChat_Release` 压缩包，解压后双击 `DreamChat.exe` 即可，配置自动保存在解压目录。

### 首次配置 API
1. 点击右上角 **⚙️ 设置**
2. 填入 `API Key`（从 Agnes AI 等平台获取）
3. 填入 `Base URL`（如 `https://api.agnes-ai.cn/v1`）
4. 填入或选择 `Model`（点"🔄 刷新"自动拉取列表）
5. 点 **💾 保存设置**

## AIScript v1.0 简介

AIScript 是 DreamChat 专为 AI 角色定义设计的轻量脚本语言，一份文件即可封装完整人格：

```
AUTH_CFG_START
::META
RID "角色名"
AID "创作者"
VER "1.0"
TYPE "OPEN"
DSC "一句话描述这个角色"

::RULES
B0 "必须遵守的行为规则"
B1 "第二条规则"

::VARS
SET mood = "calm"
SET energy = 100

::KNW
name = "角色名"
gender = "女"
age = 22

::CORPUS
greeting:
- "嗨～今天过得怎么样？"

::FLOW
... 自由编排对话流 ...
AUTH_CFG_END
```

DreamChat 内置 AIScript 解析器，把上述所有区块编译成系统提示词注入到 LLM 调用中。

**示例人格**：`personalities/dreamchat_persona.aiscript`

## 项目结构

```
DreamChat/
├── dreamchat.py              # 主程序
├── requirements.txt          # Python 依赖
├── run.bat                   # Windows 启动脚本（可选）
├── AIScript V1.0.txt         # AIScript 语言完整规范
├── personalities/            # 角色配置目录
│   └── dreamchat_persona.aiscript
├── data/                     # 运行时配置（首次启动自动创建）
│   └── config.json
└── README.md
```

## 打包为独立 EXE

```powershell
pyinstaller --onefile --windowed --name="DreamChat" ^
  --add-data "data\config.json;data" ^
  --add-data "personalities;personalities" ^
  --add-data "AIScript V1.0.txt;." ^
  dreamchat.py
```

生成 `dist/DreamChat.exe`（约 28 MB）。

## 技术栈

- **Python 3.9+** — 核心逻辑
- **customtkinter 6.0** — 现代化深色主题 UI
- **requests** — OpenAI 兼容 API 调用
- **PyInstaller** — 跨平台打包

## License

本项目采用 **MIT License**，自由使用、修改、分发。

---
**作者**：[white-cat彼岸](https://space.bilibili.com/3493257650637602) · Bilibili 创作者

> 如果喜欢这个项目，欢迎 ⭐ Star 支持！
