<p align="center">
  <a href="#-中文">中文</a> &nbsp;|&nbsp; <a href="#-english">English</a>
</p>

---

# 🔨 DivineForge

> *"神之火炉，锻造万物" — "Forged in the divine fire"*

[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Stage](https://img.shields.io/badge/Stage-Early_Preview-orange)](#)

> ⚠️ **起步阶段 · Early Stage** — 项目仍在活跃开发中，功能和稳定性持续迭代。欢迎 Star、Issue、PR！
> *This project is under active development. Features and stability are evolving. Stars, Issues, and PRs welcome!*

---

## 🇨🇳 中文

**DivineForge** 是一个基于多 AI 模型协作的工业硬件设计自动化工作台。输入一个产品想法 → 自动完成从主题设计到交付的完整 6 阶段 Pipeline。

```
你: "设计一台300×200mm桌面激光雕刻机"
    │
    ▼
  🔍 判断 → 💬 闲聊 / ❓ 澄清 / ▶ 执行
    │
    ▼
  Phase 0 · 主题设计 → Phase 1 · 详细设计 → Phase 2 · 执行
      │                                       ├── 🔧 3D建模
      │                                       ├── ⚡ 电路设计
      │                                       └── 💻 嵌入式编程
      ▼
  Phase 3 · 初审 → Phase 4 · 审核（pass/redo）→ Phase 5 · 交付
```

### 🧠 AI 模型矩阵

| 角色 | 模型 | 职责 |
|:------|:------|:------|
| 👑 设计总监 | GLM-5.1 | 需求判断、主题/详细设计、审核决策 |
| 🔧 设计工程师 | DeepSeek V4 Flash | 执行阶段（建模/电路/编程） |
| 👁️ 视觉质检师 | GLM-5V-Turbo | 产出视觉审核 |
| 💻 嵌入式工程师 | DeepSeek V4 Pro | 代码生成 |

### ✨ 核心特性

- 🤖 **智能判断** — 区分闲聊/模糊需求/具体需求，模糊需求自动生成多选题澄清
- 🔄 **审核回退** — 设计不通过自动回到 Phase 0 重新设计（最多 2 轮）
- 📦 **Sub-Agent 拆分** — Phase 2 拆分为 3D建模/电路设计/嵌入式编程子Agent
- ⚡ **逐字流式** — ref DOM 直写，打字机式实时思考显示
- 💾 **会话管理** — 每次请求存为 JSON，支持切换和状态完全还原
- ⚙ **可配置模型** — 4 个模型槽位独立配置 API Key / Base URL

### 🚀 快速开始

```bash
# 运行 EXE（推荐）
双击 dist/PipelineDesk.exe

# 开发模式
pip install pywebview
python PipelineDesk.py

cd pipeline-desk
npm install && npm run dev

# 打包
pyinstaller --onefile --windowed --add-data "pipeline-desk/dist;pipeline-desk/dist" PipelineDesk.py
```

### 📁 目录结构

```
├── PipelineDesk.py          # 主程序（pywebview + Pipeline 引擎）
├── config/                  # 模型/工具配置
├── pipeline-desk/           # React 前端
├── MCP/mbdyn-mcp/           # MBDyn 运动学 MCP 服务
├── PipelineVault/knowledge/ # 知识库
├── sessions/                # 会话记录（每个请求一个 JSON）
└── dist/                    # 打包产物
```

### 🔧 技术栈

- **桌面壳**: pywebview (WebView2)
- **前端**: React 18 + TypeScript + Vite
- **打包**: PyInstaller (~14MB)
- **AI 通信**: 流式 HTTP/SSE
- **存储**: JSON

---

## 🇬🇧 English

**DivineForge** is a multi-model AI collaborative hardware design automation workbench. Input a product idea → automatically complete the full 6-phase design pipeline from concept to delivery.

```
You: "Design a 300×200mm desktop laser engraver"
    │
    ▼
  🔍 Judge → 💬 Chat / ❓ Clarify / ▶ Execute
    │
    ▼
  Phase 0 · Concept → Phase 1 · Design → Phase 2 · Execution
      │                                        ├── 🔧 3D Modeling
      │                                        ├── ⚡ Circuit Design
      │                                        └── 💻 Embedded Dev
      ▼
  Phase 3 · Review → Phase 4 · Decision → Phase 5 · Delivery
```

### 🧠 Model Matrix

| Role | Model | Responsibility |
|:------|:------|:------|
| 👑 Director | GLM-5.1 | Input judgment, concept design, review decisions |
| 🔧 Engineer | DeepSeek V4 Flash | Execution (modeling/circuits/code) |
| 👁️ Reviewer | GLM-5V-Turbo | Visual output review |
| 💻 Coder | DeepSeek V4 Pro | Firmware code generation |

### ✨ Features

- 🤖 **Smart Judgment** — Classifies chat/vague/specific input; auto-generates clarification cards
- 🔄 **Review Loopback** — Auto-returns to Phase 0 on rejection (max 2 rounds)
- 📦 **Sub-Agent Decomposition** — Phase 2 splits into modeling/circuit/embedded sub-agents
- ⚡ **Character Streaming** — Direct DOM writes for typewriter-style thinking display
- 💾 **Session Management** — JSON-persisted sessions with full state restoration
- ⚙ **Configurable Models** — 4 independent slots with custom API keys and endpoints

### 🚀 Quick Start

```bash
# Run EXE (recommended)
Double-click: dist/PipelineDesk.exe

# Dev mode
pip install pywebview
python PipelineDesk.py

cd pipeline-desk
npm install && npm run dev

# Build
pyinstaller --onefile --windowed --add-data "pipeline-desk/dist;pipeline-desk/dist" PipelineDesk.py
```

### 📁 Structure

```
├── PipelineDesk.py          # Main app (pywebview + Pipeline engine)
├── config/                  # Model/tool configuration
├── pipeline-desk/           # React frontend
├── MCP/mbdyn-mcp/           # MBDyn kinematics MCP server
├── PipelineVault/knowledge/ # Knowledge base
├── sessions/                # Session records (one JSON per request)
└── dist/                    # Built EXE
```

### 🔧 Tech Stack

- **Shell**: pywebview (WebView2)
- **Frontend**: React 18 + TypeScript + Vite
- **Packaging**: PyInstaller (~14MB)
- **AI Transport**: Streaming HTTP/SSE
- **Storage**: JSON

---

## 📄 License

MIT

---

*Forged in the divine fire of AI* 🔨
