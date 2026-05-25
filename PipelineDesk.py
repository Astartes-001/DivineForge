#!/usr/bin/env python3
"""
Pipeline Desk — 工业设计 AI 工作台
===================================
pywebview 桌面壳 + AI Pipeline 引擎 + 真实模型调用

双击 EXE 或 python PipelineDesk.py 启动
"""

import os, sys, json, threading, time, queue
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
import webview


# ── 配置 ──
def get_base_dir():
    """前端 dist 目录：打包后从临时解压目录读"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

def get_config_dir():
    """配置目录：始终从 EXE/脚本所在目录读取"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "config"
    return Path(__file__).parent / "config"

BASE_DIR = get_base_dir()
CONFIG_DIR = get_config_dir()
DIST_DIR = BASE_DIR / "pipeline-desk" / "dist"
MODELS_FILE = CONFIG_DIR / "models.json"

def get_project_dir():
    """项目根目录（运行时目录）：EXE/脚本所在位置"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent

PROJECT_DIR = get_project_dir()

# 默认模型配置
DEFAULT_MODELS = [
    {"role": "manager", "label": "设计总监", "modelId": "glm-5.1", "provider": "zhipu",
     "apiKey": "", "apiBase": "https://open.bigmodel.cn/api/paas/v4/chat/completions"},
    {"role": "executor", "label": "设计工程师", "modelId": "deepseek-chat", "provider": "deepseek",
     "apiKey": "", "apiBase": "https://api.deepseek.com/chat/completions"},
    {"role": "reviewer", "label": "视觉质检师", "modelId": "glm-5v-turbo", "provider": "zhipu",
     "apiKey": "", "apiBase": "https://open.bigmodel.cn/api/paas/v4/chat/completions"},
    {"role": "coder", "label": "嵌入式工程师", "modelId": "deepseek-reasoner", "provider": "deepseek",
     "apiKey": "", "apiBase": "https://api.deepseek.com/chat/completions"},
]


# ── 模型配置管理 ──
def load_models() -> list:
    try:
        if MODELS_FILE.exists():
            return json.loads(MODELS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return DEFAULT_MODELS

def save_models(models: list):
    MODELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODELS_FILE.write_text(json.dumps(models, indent=2, ensure_ascii=False), encoding="utf-8")

def get_model_by_role(role: str) -> dict:
    models = load_models()
    for m in models:
        if m["role"] == role:
            return m
    return {}


# ── AI API 调用 ──
def call_ai(model_config: dict, messages: list, stream: bool = False):
    """调用 AI API，支持流式"""
    api_key = model_config.get("apiKey", "")
    api_base = model_config.get("apiBase", "")
    model_id = model_config.get("modelId", "")

    if not api_key:
        yield {"error": f"未配置 {model_config.get('label', model_config.get('role'))} 的 API Key，请在配置面板中填写"}
        return

    body = {
        "model": model_id if model_id else model_config.get("role"),
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.7,
    }
    if stream:
        body["stream"] = True

    req = Request(
        api_base,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urlopen(req, timeout=120) as resp:
            if stream:
                for line in resp:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield {"content": content}
                        except json.JSONDecodeError:
                            pass
            else:
                result = json.loads(resp.read().decode("utf-8"))
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                yield {"content": content}
    except URLError as e:
        yield {"error": f"API 请求失败: {e.reason}"}
    except Exception as e:
        yield {"error": str(e)}


# ── 会话管理 ──
class SessionManager:
    """管理多个设计会话，每个存为 JSON 文件"""

    def __init__(self):
        self.sessions_dir = PROJECT_DIR / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.sessions_dir / "index.json"

    def _read_index(self):
        try: return json.loads(self.index_file.read_text(encoding="utf-8"))
        except: return []

    def _write_index(self, data):
        self.index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def create(self, user_idea: str) -> str:
        """创建新会话 JSON，返回 session_id"""
        ts = time.strftime("%Y%m%d_%H%M%S")
        title = self._summarize_title(user_idea)
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:40]
        sid = f"{ts}_{safe_title}"
        data = {
            "id": sid, "title": title,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "user_idea": user_idea,
            "phases": [],
            "msgs": [],
        }
        (self.sessions_dir / f"{sid}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        idx = self._read_index()
        idx.insert(0, {"id": sid, "title": title, "time": time.strftime("%Y-%m-%d %H:%M"), "idea": user_idea[:80]})
        self._write_index(idx)
        return sid

    def _summarize_title(self, idea: str) -> str:
        model = get_model_by_role("manager")
        full = ""
        for chunk in call_ai(model, [{"role":"user","content":f"用8个字总结这个设计需求：{idea[:200]}"}], stream=False):
            full += chunk.get("content","")
        t = full.strip().replace("\n"," ")
        return t if t and len(t)<=50 else idea[:30].replace("\n"," ")

    def append_phase(self, sid: str, phase_id: int, phase_name: str, thinking: str):
        """追加 Phase 到会话 JSON"""
        path = self.sessions_dir / f"{sid}.json"
        if not path.exists(): return
        data = json.loads(path.read_text(encoding="utf-8"))
        data["phases"].append({"id": phase_id, "name": phase_name, "thinking": thinking, "status": "done"})
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_msg(self, sid: str, role: str, content: str):
        path = self.sessions_dir / f"{sid}.json"
        if not path.exists(): return
        data = json.loads(path.read_text(encoding="utf-8"))
        data["msgs"].append({"role": role, "content": content})
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, sid: str) -> str:
        path = self.sessions_dir / f"{sid}.json"
        return path.read_text(encoding="utf-8") if path.exists() else "{}"

    def list_all(self):
        return self._read_index()


# ── Pipeline 引擎 ──
class PipelineEngine:
    """工业设计 Pipeline — 含判断/澄清/执行三阶段"""

    PHASES = [
        {"id": 0, "name": "Phase 0 · 主题设计", "model": "manager"},
        {"id": 1, "name": "Phase 1 · 详细设计", "model": "manager"},
        {"id": 2, "name": "Phase 2 · 执行", "model": "executor"},
        {"id": 3, "name": "Phase 3 · 视觉初审", "model": "reviewer"},
        {"id": 4, "name": "Phase 4 · 复核决策", "model": "manager"},
        {"id": 5, "name": "Phase 5 · 最终交付", "model": "manager"},
    ]

    SYSTEM_PROMPTS = {
        "manager": (
            "你是硬件产品设计总监。你拥有一个三模型执行团队和五个 MCP 工程工具。"
            "你负责从需求到完整交付包的全过程。"
            "每个阶段先读知识库，然后给出详细的工程设计方案。用中文回答。"
        ),
        "executor": (
            "你是设计工程师。收到设计总监的发包指令后，将参数转为具体的工程操作。用中文回答。"
        ),
        "reviewer": (
            "你是视觉质检师。只描述物理问题，不做工程判断。用中文回答。"
        ),
        "coder": (
            "你是嵌入式工程师。收到引脚分配表和技术规格后，生成固件代码。用中文回答。"
        ),
    }

    JUDGE_PROMPT = """你是一个需求分析助手。分析用户输入，判断它属于哪种类型，然后返回 JSON。

类型定义:
- "chat": 闲聊、问候、测试（如"你好"、"测试"、"今天天气怎么样"），与工业设计完全无关
- "vague": 模糊的产品需求（如"我想做一个机器人"），但缺少具体参数，需要进一步澄清
- "specific": 具体的设计需求（如"设计一台工作面积300×200mm、精度±0.05mm的激光雕刻机"），参数足够清晰

返回格式（严格 JSON）:
{"type": "chat|vague|specific", "reason": "简短判断理由", "response": "如果是chat，这里是友好的聊天回复；否则为空"}

不要返回 JSON 以外的任何内容。"""

    CLARIFY_PROMPT = """你是一个工业设计需求分析师。用户提出了以下需求：
{user_idea}

请分析哪些关键信息还缺失（从以下维度考虑：产品定位、尺寸、材料、精度、功率、预算、使用场景、特殊约束等）。

返回 JSON 格式（严格，不要返回其他内容）：
{{
  "summary": "对需求的一句话理解",
  "missing": [
    {{
      "question": "你向用户提出的问题（简洁清晰）",
      "options": ["选项A", "选项B", "选项C", "以上都不确定"],
      "multi": false
    }}
  ],
  "next_action": "clarify"
}}

注意:
- 最多提出 4 个问题
- 每个问题 2-4 个选项
- 如果需求已经足够清晰，next_action 设为 "proceed"
- missing 数组中的问题按重要性排序"""

    def __init__(self, on_event):
        self.on_event = on_event
        self.vault_path = PROJECT_DIR / "PipelineVault"
        self._stop_flag = False
        self.sessions = SessionManager()
        self._current_sid = None

    def stop(self):
        self._stop_flag = True

    def run(self, user_idea: str):
        """主入口：判断 → 澄清/聊天 → Pipeline"""
        self._stop_flag = False
        thread = threading.Thread(target=self._run_flow, args=(user_idea,), daemon=True)
        thread.start()

    def _run_flow(self, user_idea: str):
        """完整流程"""
        # Step 1: 判断
        self.on_event("judging", {"text": "分析需求..."})
        result = self._judge(user_idea)
        jtype = result.get("type", "chat")

        if jtype == "chat":
            # 闲聊模式 — 不用 system prompt
            resp = result.get("response", "你好！有什么可以帮助你的？")
            self.on_event("chat_response", {"text": resp})
            return

        if jtype == "vague":
            # 澄清模式
            self._clarify(user_idea)
            return

        # jtype == "specific" — 直接跑 Pipeline
        self._run_full_pipeline(user_idea)

    def _judge(self, user_idea: str) -> dict:
        """调用 AI 判断输入类型"""
        model = get_model_by_role("manager")
        messages = [
            {"role": "system", "content": self.JUDGE_PROMPT},
            {"role": "user", "content": user_idea},
        ]
        full = ""
        for chunk in call_ai(model, messages, stream=False):
            if "error" in chunk:
                self.on_event("error", chunk["error"])
                return {"type": "chat", "response": "你好！"}
            full += chunk.get("content", "")
        # 提取 JSON
        try:
            # 去掉可能的 markdown 包裹
            full = full.strip()
            if full.startswith("```"):
                full = full.split("\n", 1)[1].rsplit("\n```", 1)[0]
            return json.loads(full)
        except json.JSONDecodeError:
            return {"type": "specific"}  # fallback: 直接跑

    def _clarify(self, user_idea: str):
        """生成澄清问题"""
        self.on_event("phase_start", {"id": -1, "name": "需求澄清", "model": "设计总监"})

        model = get_model_by_role("manager")
        prompt = self.CLARIFY_PROMPT.replace("{user_idea}", user_idea)
        messages = [{"role": "user", "content": prompt}]

        full = ""
        for chunk in call_ai(model, messages, stream=False):
            if "error" in chunk:
                self.on_event("error", chunk["error"])
                return
            full += chunk.get("content", "")

        try:
            full = full.strip()
            if full.startswith("```"):
                full = full.split("\n", 1)[1].rsplit("\n```", 1)[0]
            qdata = json.loads(full)
            next_action = qdata.get("next_action", "clarify")

            if next_action == "proceed":
                # 需求已清晰，直接进入 Pipeline
                self._run_full_pipeline(user_idea)
            else:
                self.on_event("clarify_questions", {
                    "summary": qdata.get("summary", ""),
                    "questions": qdata.get("missing", []),
                })
        except json.JSONDecodeError:
            self._run_full_pipeline(user_idea)
        finally:
            self.on_event("phase_end", {"id": -1, "name": "需求澄清", "status": "done"})

    def answer_question(self, answers: str):
        """处理用户的选择题答案，重新评估是否能进入 Pipeline"""
        self.on_event("judging", {"text": "根据你的选择重新评估..."})
        model = get_model_by_role("manager")

        # 将答案和澄清总结一起发送给 judge
        prompt = f"""用户对需求的补充回答如下（可能尚未完整）：
{answers}

请重新判断：现在是否已经足够清晰可以开始工业设计？回答 JSON：
{{"type": "specific|vague", "reason": "简短理由", "refined_requirement": "如果 type=specific，这里是一句精炼后的完整需求描述"}}"""

        messages = [{"role": "user", "content": prompt}]
        full = ""
        for chunk in call_ai(model, messages, stream=False):
            if "error" in chunk:
                self.on_event("error", chunk["error"])
                return
            full += chunk.get("content", "")

        try:
            full = full.strip()
            if full.startswith("```"):
                full = full.split("\n", 1)[1].rsplit("\n```", 1)[0]
            result = json.loads(full)
            if result.get("type") == "specific":
                refined = result.get("refined_requirement", answers)
                self.on_event("chat_response", {"text": f"好的，需求已明确。开始工业设计 Pipeline...\n\n精炼需求：{refined}"})
                self._run_full_pipeline(refined)
            else:
                # 仍然模糊，再次生成问题
                self._clarify(answers)
        except json.JSONDecodeError:
            self._run_full_pipeline(answers)

    PHASES_0_3 = [
        {"id": 0, "name": "Phase 0 · 主题设计", "model": "manager"},
        {"id": 1, "name": "Phase 1 · 详细设计", "model": "manager"},
        {"id": 2, "name": "Phase 2 · 执行", "model": "executor"},
        {"id": 3, "name": "Phase 3 · 视觉初审", "model": "reviewer"},
    ]

    def _run_full_pipeline(self, user_idea: str):
        """Phase 0-3 → 审核 → Phase 5 交付"""
        retry = 0
        max_retries = 2
        outputs = {}
        feedback = ""
        # 创建会话
        self._current_sid = self.sessions.create(user_idea)
        self.on_event("session_created", {"id": self._current_sid})
        if self._current_sid:
            self.sessions.append_msg(self._current_sid, "user", user_idea)

        while retry <= max_retries:
            if self._stop_flag: return

            # Phase 0-3
            for phase in self.PHASES_0_3:
                if self._stop_flag: return
                self.on_event("phase_start", phase)
                cfg = get_model_by_role(phase["model"])
                prompt = self._build_phase_prompt(phase["id"], user_idea, feedback, outputs)
                full = self._call_stream(cfg, self.SYSTEM_PROMPTS.get(phase["model"], ""), prompt, phase["id"])
                if full is None: return
                outputs[phase["id"]] = full
                if self._current_sid:
                    self.sessions.append_phase(self._current_sid, phase["id"], phase["name"], full)
                self.on_event("thinking", {"phase_id": phase["id"], "text": full, "model": cfg.get("label", phase["model"])})
                self.on_event("phase_end", {"id": phase["id"], "status": "done"})
                time.sleep(0.1)

            # 审核决策 (Phase 4)
            self.on_event("phase_start", {"id": 4, "name": "Phase 4 · 审核决策", "model": "设计总监"})
            action, reason = self._decide(outputs, user_idea)
            self.on_event("thinking", {"phase_id": 4, "text": f"决策: {action} | {reason}", "model": "设计总监"})
            self.on_event("phase_end", {"id": 4, "status": "done"})
            if self._current_sid:
                self.sessions.append_phase(self._current_sid, 4, "Phase 4 · 审核决策", f"决策: {action}\n理由: {reason}")

            if action == "pass":
                # Phase 5 交付
                self.on_event("phase_start", {"id": 5, "name": "Phase 5 · 最终交付", "model": "设计总监"})
                cfg = get_model_by_role("manager")
                prompt = self._build_phase_prompt(5, user_idea, feedback, outputs)
                full = self._call_stream(cfg, self.SYSTEM_PROMPTS["manager"], prompt, 5)
                if full is None: return
                self.on_event("thinking", {"phase_id": 5, "text": full, "model": cfg.get("label", "manager")})
                self.on_event("phase_end", {"id": 5, "status": "done"})
                if self._current_sid:
                    self.sessions.append_phase(self._current_sid, 5, "Phase 5 · 最终交付", full)
                self.on_event("pipeline_done", {"message": "✅ 审核通过，设计已交付。"})
                return
            elif action in ("minor_fix", "retry"):
                feedback = f"[审核反馈·第{retry+1}轮] {reason}"
                outputs = {} if action == "redo" else outputs
                self.on_event("chat_response", {"text": f"🔧 审核反馈：{reason}\n自动修正中..."})
                retry += 1
            else:
                feedback = f"[审核反馈·重做] {reason}"
                outputs = {}
                self.on_event("chat_response", {"text": f"🔄 审核不通过：{reason}\n重新设计中..."})
                retry += 1

        self.on_event("pipeline_done", {"message": f"完成（{max_retries}轮修正）。"})

    def _call_stream(self, cfg, sys_prompt, user_prompt, pid):
        """调用 AI 流式输出。出错自动重试一次。返回完整文本或 None"""
        msgs = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_prompt}]
        full = ""
        for attempt in range(2):
            try:
                for chunk in call_ai(cfg, msgs, stream=True):
                    if self._stop_flag: return None
                    if "error" in chunk:
                        if "10054" in chunk["error"] or "forcibly" in chunk["error"].lower():
                            if attempt == 0:
                                time.sleep(1)
                                break  # retry
                            self.on_event("error", chunk["error"])
                            return None
                        self.on_event("error", chunk["error"])
                        return None
                    if "content" in chunk:
                        full += chunk["content"]
                        self.on_event("thinking_stream", {"phase_id": pid, "text": chunk["content"]})
                        time.sleep(0.02)
                else:
                    return full  # completed without error
            except Exception as ex:
                if attempt == 0:
                    time.sleep(1)
                    continue
                self.on_event("error", str(ex))
                return None
        return full

    def _decide(self, outputs, user_idea):
        """审核决策（非流式）。返回 (action, reason)"""
        prompt = f"""需求: {user_idea}
Phase0: {outputs.get(0,'')[:400]}
Phase2: {outputs.get(2,'')[:400]}
Phase3初审: {outputs.get(3,'')[:400]}
请决策。JSON: {{"action":"pass|fix|redo","reason":"理由"}}"""
        msgs = [{"role": "user", "content": prompt}]
        full = ""
        for chunk in call_ai(get_model_by_role("manager"), msgs, stream=False):
            full += chunk.get("content", "")
        try:
            full = full.strip()
            if full.startswith("```"): full = full.split("\n",1)[1].rsplit("\n```",1)[0]
            r = json.loads(full)
            return r.get("action", "pass"), r.get("reason", "")
        except:
            return "pass", "自动通过"

    def _build_phase_prompt(self, phase_id: int, user_idea: str, feedback: str = "", outputs: dict = None) -> str:
        if outputs is None:
            outputs = {}
        base_prompts = {
            0: f"用户需求：{user_idea}\n{feedback}\n请完成 Phase 0 主题设计：产品定位、竞品对标、设计语言、功能分解、关键性能指标。",
            1: f"用户需求：{user_idea}\n{feedback}\n上一阶段主题设计：{outputs.get(0, '无')[:800]}\n\n请完成 Phase 1 详细工程设计：机械子系统选材/传动/尺寸链、电子子系统 MCU 选型/引脚/电源、散热方案、接口定义。",
            2: f"需求：{user_idea[:200]}\n详细设计摘要：{outputs.get(1, '无')[:500]}\n\nPhase 2 执行。按子任务分别输出：\n## 3D建模\n- FreeCAD参数\n## 电路设计\n- KiCad元件\n## 嵌入式编程\n- MCU/引脚/逻辑\n每段精简。",
            3: f"用户需求：{user_idea}\n执行产出摘要：{outputs.get(2, '无')[:800]}\n\n你是视觉质检师。请审核执行产出的合理性。只描述物理问题，不做工程判断。",
            4: f"用户需求：{user_idea}\n{feedback}\n视觉初审报告：{outputs.get(3, '无')[:800]}\n\n你是设计总监。请复核初审报告，结合设计意图做判断。列出具体问题和修正建议。",
            5: f"用户需求：{user_idea}\n{feedback}\n所有产出摘要：\nPhase0: {outputs.get(0, '无')[:300]}\nPhase1: {outputs.get(1, '无')[:300]}\nPhase2: {outputs.get(2, '无')[:300]}\n\n请生成最终交付包：机械/电子/固件/质量报告。",
        }
        return base_prompts.get(phase_id, user_idea)


# ── PyWebview API ──
class Api:
    """暴露给 JS 的 Python API"""

    def __init__(self):
        self.engine = PipelineEngine(on_event=self._on_engine_event)
        self.event_queue = queue.Queue()

    def _on_engine_event(self, event_type, data):
        self.event_queue.put({"type": event_type, "data": data})

    def start_pipeline(self, user_idea):
        """JS 调用：启动 Pipeline"""
        self.engine.run(user_idea)

    def stop_pipeline(self):
        """JS 调用：停止当前 Pipeline"""
        self.engine.stop()
        return "ok"

    def answer_question(self, answers):
        """JS 调用：提交选择题答案"""
        self.engine.answer_question(answers)
        return "ok"

    def list_sessions(self):
        """获取会话列表"""
        return json.dumps(self.engine.sessions.list_all(), ensure_ascii=False)

    def load_session(self, sid):
        """加载会话 JSON"""
        return self.engine.sessions.load(sid)

    def poll_events(self):
        """JS 轮询：获取最新事件列表"""
        events = []
        while not self.event_queue.empty():
            try:
                evt = self.event_queue.get_nowait()
                events.append(evt)
            except queue.Empty:
                break
        return json.dumps(events, ensure_ascii=False)

    def get_models(self):
        """获取模型配置"""
        return json.dumps(load_models(), ensure_ascii=False)

    def save_models(self, models_json):
        """保存模型配置"""
        models = json.loads(models_json)
        save_models(models)
        return "ok"

    def test_model(self, role):
        """测试模型连通性"""
        model = get_model_by_role(role)
        if not model.get("apiKey"):
            return json.dumps({"ok": False, "error": "API Key 未配置"}, ensure_ascii=False)
        messages = [{"role": "user", "content": "你好，请回复一个字：通"}]
        result = ""
        for chunk in call_ai(model, messages, stream=False):
            if "error" in chunk:
                return json.dumps({"ok": False, "error": chunk["error"]}, ensure_ascii=False)
            result += chunk.get("content", "")
        return json.dumps({"ok": True, "response": result.strip()}, ensure_ascii=False)

    def get_vault_knowledge(self):
        """获取知识库摘要"""
        kb = PROJECT_DIR / "PipelineVault" / "knowledge"
        files = list(kb.glob("*.md"))
        result = []
        for f in files:
            result.append({"name": f.stem, "path": str(f.relative_to(BASE_DIR))})
        return json.dumps(result, ensure_ascii=False)


# ── HTTP 服务器 ──
class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    def log_message(self, format, *args):
        pass


def start_server():
    server = HTTPServer(("127.0.0.1", 0), QuietHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return port


# ── 主入口 ──
def main():
    if not DIST_DIR.exists():
        print(f"前端 dist 不存在: {DIST_DIR}")
        print("请先: cd pipeline-desk && npm run build")
        sys.exit(1)

    # 确保 models.json 存在
    if not MODELS_FILE.exists():
        save_models(DEFAULT_MODELS)

    port = start_server()
    url = f"http://127.0.0.1:{port}"

    api = Api()

    window = webview.create_window(
        title="Pipeline Desk — 工业设计 AI 工作台",
        url=url,
        js_api=api,
        width=1280,
        height=800,
        min_size=(900, 600),
        resizable=True,
        text_select=True,
    )

    webview.start(debug=False)


if __name__ == "__main__":
    main()
