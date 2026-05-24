# ⚙ IronMind — 工业设计 AI Pipeline

[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**IronMind** 是一个基于多 AI 模型协作的工业硬件设计自动化工作台。输入一个产品想法 → 自动完成从主题设计到交付的完整 6 阶段 Pipeline。

```
你: "设计一台300×200mm桌面激光雕刻机"
    │
    ▼
  🔍 判断 → 💬 闲聊 / ❓ 澄清 / ▶ 执行
    │
    ▼
  Phase 0 · 主题设计 → Phase 1 · 详细设计 → Phase 2 · 执行
      │                                        ├── 🔧 3D建模
      │                                        ├── ⚡ 电路设计
      │                                        └── 💻 嵌入式编程
      ▼
  Phase 3 · 初审 → Phase 4 · 审核（pass/redo）→ Phase 5 · 交付
```

## 🧠 AI 模型矩阵

| 角色 | 模型 | 职责 |
|:------|:------|:------|
| 👑 设计总监 | GLM-5.1 | 需求判断、主题/详细设计、审核决策 |
| 🔧 设计工程师 | DeepSeek V4 Flash | 执行阶段（建模/电路/编程） |
| 👁️ 视觉质检师 | GLM-5V-Turbo | 产出视觉审核 |
| 💻 嵌入式工程师 | DeepSeek V4 Pro | 代码生成 |

## ✨ 核心特性

- **智能判断** — 区分闲聊/模糊需求/具体需求，模糊需求自动生成多选题澄清
- **审核回退** — 设计不通过自动回到 Phase 0 重新设计（最多 2 轮）
- **Sub-Agent 拆分** — Phase 2 下拆分为 3D建模/电路设计/嵌入式编程子 Agent
- **逐字流式显示** — ref DOM 直写，非 React 批量，像打字机一样
- **会话管理** — 每次请求存为 JSON 文件，支持切换和状态完全还原
- **可配置模型** — 4 个模型槽位独立配置 API Key / Base URL

## 🚀 快速开始

### 运行 EXE（推荐）

```bash
双击 dist/PipelineDesk.exe
```

### 开发模式

```bash
# 后端
pip install pywebview
python PipelineDesk.py

# 前端
cd pipeline-desk
npm install
npm run dev
```

### 打包

```bash
pyinstaller --onefile --windowed --add-data "pipeline-desk/dist;pipeline-desk/dist" PipelineDesk.py
```

## 📁 目录结构

```
IronMind/
├── PipelineDesk.py          # 主程序（pywebview + Pipeline 引擎）
├── config/
│   └── models.json          # AI 模型配置
├── pipeline-desk/           # React 前端
│   └── src/App.tsx
├── PipelineVault/           # 知识库（材料/传动/PCB/流体/运动学）
├── sessions/                # 会话记录（每个请求一个 JSON）
└── dist/
    └── PipelineDesk.exe     # Windows 打包产物
```

## 🔧 技术栈

- **桌面壳**: pywebview (WebView2)
- **前端**: React 18 + TypeScript + Vite
- **打包**: PyInstaller (onefile ~14MB)
- **AI 通信**: 流式 HTTP/SSE
- **会话存储**: JSON 文件

## 📝 会话 JSON 格式

```json
{
  "id": "20260524_223015_桌面激光雕刻机",
  "title": "桌面激光雕刻机",
  "time": "2026-05-24 22:30",
  "user_idea": "设计一台300×200mm...",
  "phases": [
    {"id": 0, "name": "Phase 0 · 主题设计", "thinking": "...", "status": "done"}
  ],
  "msgs": [{"role": "user", "content": "..."}]
}
```

## 📄 License

MIT

---

*Made with ⚙ in the forge of AI*
