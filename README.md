# 🔨 DivineForge — 工业设计 AI Pipeline · Industrial Design AI Pipeline

> *"神之火炉，锻造万物" — "Forged in the divine fire"*

[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**DivineForge** 是一个基于多 AI 模型协作的工业硬件设计自动化工作台。输入一个产品想法 → 自动完成从主题设计到交付的完整 6 阶段 Pipeline。

*DivineForge is a multi-model AI collaborative hardware design automation workbench. Input a product idea → automatically complete the full 6-phase design pipeline from concept to delivery.*

> ⚠️ **起步阶段 · Early Stage** — 项目仍在活跃开发中，功能和稳定性持续迭代。欢迎 Star、Issue、PR！ · *This project is under active development. Features and stability are evolving. Stars, Issues, and PRs welcome!*

```
你 · You: "设计一台300×200mm桌面激光雕刻机"
    │
    ▼
  🔍 判断 · Judge → 💬 Chat / ❓ Clarify / ▶ Execute
    │
    ▼
  Phase 0 · Concept → Phase 1 · Design → Phase 2 · Execution
      │                                        ├── 🔧 3D Modeling
      │                                        ├── ⚡ Circuit Design
      │                                        └── 💻 Embedded Dev
      ▼
  Phase 3 · Review → Phase 4 · Decision → Phase 5 · Delivery
```

## 🧠 AI 模型矩阵 · Model Matrix

| 角色 Role | 模型 Model | 职责 Responsibility |
|:------|:------|:------|
| 👑 设计总监 Director | GLM-5.1 | 需求判断、主题/详细设计、审核决策 · Judgment, concept design, review decisions |
| 🔧 设计工程师 Engineer | DeepSeek V4 Flash | 执行阶段（建模/电路/编程）· Execution (modeling/circuit/code) |
| 👁️ 视觉质检师 Reviewer | GLM-5V-Turbo | 产出视觉审核 · Visual output review |
| 💻 嵌入式工程师 Coder | DeepSeek V4 Pro | 代码生成 · Code generation |

## ✨ 核心特性 · Features

- 🤖 **智能判断 · Smart Judgment** — 区分闲聊/模糊需求/具体需求，模糊需求自动生成多选题澄清 · *Classifies chat/vague/specific input; generates clarification cards for vague requirements*
- 🔄 **审核回退 · Review Loopback** — 设计不通过自动回到 Phase 0 重新设计（最多 2 轮）· *Auto-returns to Phase 0 on review rejection (max 2 rounds)*
- 📦 **Sub-Agent 拆分 · Sub-Agent Decomposition** — Phase 2 拆分为 3D建模/电路设计/嵌入式编程 · *Phase 2 split into modeling/circuit/embedded sub-agents*
- ⚡ **逐字流式 · Character Streaming** — ref DOM 直写，像打字机一样实时显示思考 · *Direct DOM writes for typewriter-style real-time thinking display*
- 💾 **会话管理 · Session Management** — 每次请求存为 JSON，支持切换和状态完全还原 · *JSON-serialized sessions with full state restoration*
- ⚙ **可配置模型 · Configurable Models** — 4 个模型槽位独立配置 API Key / Base URL · *4 independent model slots with custom keys and endpoints*

## 🚀 快速开始 · Quick Start

### 运行 EXE (推荐 · Recommended)

```bash
双击 · Double-click: dist/PipelineDesk.exe
```

### 开发模式 · Dev Mode

```bash
# 后端 · Backend
pip install pywebview
python PipelineDesk.py

# 前端 · Frontend
cd pipeline-desk
npm install
npm run dev
```

### 打包 · Build

```bash
pyinstaller --onefile --windowed --add-data "pipeline-desk/dist;pipeline-desk/dist" PipelineDesk.py
```

## 📁 目录结构 · Structure

```
DivineForge/
├── PipelineDesk.py          # 主程序 · Main app (pywebview + Pipeline engine)
├── config/
│   ├── models.json          # AI 模型配置 · Model configuration
│   ├── mcp_servers.json     # MCP 服务配置 · MCP server config
│   └── pipeline_system_prompt.md  # Pipeline 系统指令 · System prompt
├── pipeline-desk/           # React 前端 · Frontend
│   └── src/App.tsx
├── MCP/
│   └── mbdyn-mcp/           # MBDyn 运动学 MCP 服务 · Kinematics MCP server
├── PipelineVault/
│   └── knowledge/           # 知识库 · Knowledge base
│       ├── pcb-design-spec.md
│       ├── transmission-design.md
│       ├── materials-database.md
│       ├── fluid-mechanics.md
│       └── kinematics-guide.md
├── sessions/                # 会话记录 · Session records
├── dist/                    # 打包产物 · Built EXE
└── README.md
```

## 🔧 技术栈 · Tech Stack

- **桌面壳 · Shell**: pywebview (WebView2)
- **前端 · Frontend**: React 18 + TypeScript + Vite
- **打包 · Packaging**: PyInstaller (onefile ~14MB)
- **AI 通信 · AI Transport**: Streaming HTTP/SSE
- **会话存储 · Storage**: JSON files

## 📝 会话格式 · Session Format

```json
{
  "id": "20260524_223015_laser-engraver",
  "title": "桌面激光雕刻机",
  "time": "2026-05-24 22:30",
  "user_idea": "设计一台300×200mm...",
  "phases": [
    {"id": 0, "name": "Phase 0 · Concept", "thinking": "...", "status": "done"}
  ],
  "msgs": [{"role": "user", "content": "..."}]
}
```

## 📄 许可证 · License

MIT

---

*Forged in the divine fire of AI* 🔨
