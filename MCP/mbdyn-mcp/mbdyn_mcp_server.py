#!/usr/bin/env python3
"""
MBDyn MCP Server — 多体动力学仿真 MCP 桥接
==========================================
作为 Hermes Agent / Claude Desktop 的 MCP 工具，
将结构化仿真参数转为 MBDyn .mbd 输入文件并执行求解。

用法:
    python mbdyn_mcp_server.py

协议: MCP stdio (MCP 2025-06-18)
依赖: pip install matplotlib numpy

MBDyn 安装: https://www.mbdyn.org/download.html
"""

import json, sys, subprocess, os, tempfile, re, shutil
from pathlib import Path
from typing import Any, Optional

# ═══════════════════════════════════════════════════
#  配置
# ═══════════════════════════════════════════════════

# MBDyn 可执行文件路径（根据实际安装位置修改）
MBDYN_BIN = shutil.which("mbdyn") or r"C:\Program Files\MBDyn\bin\mbdyn.exe"

# 临时工作目录
WORK_DIR = Path(os.environ.get("MBDYN_MCP_WORK_DIR", tempfile.gettempdir())) / "mbdyn_mcp"

# 工具清单
TOOLS = [
    {
        "name": "mbdyn_run_simulation",
        "description": "运行 MBDyn 多体动力学仿真。"
                       "接收结构化参数（刚体、铰链、力、时间），"
                       "自动生成 .mbd 输入文件并调用 MBDyn 求解。"
                       "返回节点轨迹数据和运动结果摘要。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bodies": {
                    "type": "array",
                    "description": "刚体列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "刚体名称"},
                            "mass": {"type": "number", "description": "质量 kg"},
                            "inertia": {
                                "type": "array",
                                "description": "惯性张量 [Ixx, Iyy, Izz, Ixy, Ixz, Iyz]",
                                "items": {"type": "number"}
                            },
                            "initial_pos": {
                                "type": "array",
                                "description": "初始位置 [x, y, z] m",
                                "items": {"type": "number"}
                            },
                            "initial_rot": {
                                "type": "array",
                                "description": "初始姿态欧拉角 [rx, ry, rz] rad",
                                "items": {"type": "number"},
                                "default": [0, 0, 0]
                            }
                        },
                        "required": ["name", "mass", "inertia", "initial_pos"]
                    }
                },
                "joints": {
                    "type": "array",
                    "description": "约束/铰链列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["revolute", "spherical", "ground", "prismatic", "cylindrical"],
                                "description": "铰链类型: revolute(旋转)/spherical(球铰)/ground(固定)/prismatic(移动)"
                            },
                            "body1": {"type": "string", "description": "第一个刚体名"},
                            "body2": {"type": "string", "description": "第二个刚体名（ground 类型忽略此项）"},
                            "position": {
                                "type": "array",
                                "description": "铰链位置 [x, y, z] m",
                                "items": {"type": "number"}
                            },
                            "axis": {
                                "type": "array",
                                "description": "旋转轴方向（仅 revolute/prismatic）[x, y, z]",
                                "items": {"type": "number"},
                                "default": [1, 0, 0]
                            }
                        },
                        "required": ["type", "body1", "position"]
                    }
                },
                "forces": {
                    "type": "array",
                    "description": "力/力矩列表（可选）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["absolute", "gravity", "spring"],
                                "description": "力类型: absolute(定力方向)/gravity(重力)/spring(弹簧)"
                            },
                            "body": {"type": "string", "description": "施加的刚体名"},
                            "magnitude": {"type": "number", "description": "力的大小 N"},
                            "direction": {
                                "type": "array",
                                "description": "力的方向向量 [x, y, z]（仅 absolute）",
                                "items": {"type": "number"},
                                "default": [0, 0, -1]
                            },
                            "gravity": {
                                "type": "number",
                                "description": "重力加速度 m/s²（仅 gravity 类型，默认 9.81）",
                                "default": 9.81
                            }
                        },
                        "required": ["type", "body", "magnitude"]
                    },
                    "default": []
                },
                "time": {
                    "type": "object",
                    "description": "仿真时间参数",
                    "properties": {
                        "start": {"type": "number", "description": "起始时间 s", "default": 0},
                        "stop": {"type": "number", "description": "结束时间 s"},
                        "step": {"type": "number", "description": "时间步长 s", "default": 0.01}
                    },
                    "required": ["stop"]
                },
                "output": {
                    "type": "object",
                    "description": "输出控制（可选）",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["csv", "mov"],
                            "description": "输出格式: csv(文本)/mov(二进制动画)",
                            "default": "csv"
                        }
                    },
                    "default": {"format": "csv"}
                }
            },
            "required": ["bodies", "joints", "time"]
        }
    },
    {
        "name": "mbdyn_load_file",
        "description": "加载已有的 .mbd 输入文件并运行仿真",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_file": {
                    "type": "string",
                    "description": ".mbd 输入文件完整路径"
                },
                "output_dir": {
                    "type": "string",
                    "description": "输出目录（可选，默认输入文件所在目录）"
                }
            },
            "required": ["input_file"]
        }
    },
    {
        "name": "mbdyn_get_results",
        "description": "获取指定仿真的结果摘要",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": "仿真运行ID（从 run_simulation 返回中获取）"
                }
            },
            "required": ["run_id"]
        }
    },
    {
        "name": "mbdyn_query_capabilities",
        "description": "查询 MBDyn 支持的能力和当前配置",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "mbdyn_visualize",
        "description": "生成运动轨迹可视化图像（PNG）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "仿真运行ID"},
                "output_path": {"type": "string", "description": "输出 PNG 文件路径"}
            },
            "required": ["run_id", "output_path"]
        }
    }
]

# ═══════════════════════════════════════════════════
#  模板生成
# ═══════════════════════════════════════════════════

def generate_mbd_input(params: dict) -> str:
    """将结构化参数转为 MBDyn .mbd 输入文件文本"""
    t = params.get("time", {})
    t_start = t.get("start", 0.0)
    t_stop = t.get("stop", 1.0)
    t_step = t.get("step", 0.01)

    bodies = params.get("bodies", [])
    joints = params.get("joints", [])
    forces = params.get("forces", [])
    output = params.get("output", {"format": "csv"})
    out_fmt = output.get("format", "csv")

    lines = [
        f"# MBDyn input - Generated by Pipeline MCP",
        f"# Time: {t_start} -> {t_stop}, step={t_step}",
        "",
        "begin: data;",
        "    problem: initial value;",
        "end: data;",
        "",
        "begin: initial value;",
        f"    initial time: {t_start};",
        f"    final time:   {t_stop};",
        f"    time step:    {t_step};",
        f"    max iterations: 50;",
        f"    tolerance: 1e-6;",
        "end: initial value;",
        "",
    ]

    # ── 节点 ──
    lines.append("# ── Nodes ──")
    node_id = 1
    node_map = {}
    for body in bodies:
        name = body.get("name", f"body_{node_id}")
        pos = body.get("initial_pos", [0, 0, 0])
        rot = body.get("initial_rot", [0, 0, 0])
        lines.append(f"structural: {node_id}, {name},")
        lines.append(f"    position, reference, global, {pos[0]}, {pos[1]}, {pos[2]},")
        lines.append(f"    orientation, reference, global, euler, {rot[0]}, {rot[1]}, {rot[2]};")
        node_map[name] = node_id
        node_id += 1

    lines.append("")

    # ── 刚体 ──
    lines.append("# ── Bodies ──")
    for body in bodies:
        nid = node_map[body["name"]]
        m = body.get("mass", 1.0)
        I = body.get("inertia", [1, 1, 1, 0, 0, 0])
        lines.append(f"body: {nid}, {nid},")
        lines.append(f"    {m},")
        lines.append(f"    {I[0]}, {I[1]}, {I[2]},")
        lines.append(f"    {I[3]}, {I[4]}, {I[5]};")

    lines.append("")

    # ── 铰链 ──
    if joints:
        lines.append("# ── Joints ──")
        for j, joint in enumerate(joints):
            jid = node_id + j
            jtype = joint.get("type", "revolute")
            b1 = node_map.get(joint.get("body1"), 1)
            pos = joint.get("position", [0, 0, 0])
            axis = joint.get("axis", [1, 0, 0])

            if jtype == "ground":
                lines.append(f"joint: clamp, {jid}, {b1},")
                lines.append(f"    position, reference, global, {pos[0]}, {pos[1]}, {pos[2]};")
            elif jtype == "spherical":
                b2 = node_map.get(joint.get("body2"), 2)
                lines.append(f"joint: spherical, {jid},")
                lines.append(f"    {b1}, {b2},")
                lines.append(f"    position, reference, global, {pos[0]}, {pos[1]}, {pos[2]};")
            elif jtype == "revolute":
                b2 = node_map.get(joint.get("body2"), 2)
                lines.append(f"joint: revolute, {jid},")
                lines.append(f"    {b1}, {b2},")
                lines.append(f"    position, reference, global, {pos[0]}, {pos[1]}, {pos[2]},")
                lines.append(f"    axis, {axis[0]}, {axis[1]}, {axis[2]};")
            elif jtype == "prismatic":
                b2 = node_map.get(joint.get("body2"), 2)
                lines.append(f"joint: prismatic, {jid},")
                lines.append(f"    {b1}, {b2},")
                lines.append(f"    position, reference, global, {pos[0]}, {pos[1]}, {pos[2]},")
                lines.append(f"    axis, {axis[0]}, {axis[1]}, {axis[2]};")
            elif jtype == "cylindrical":
                b2 = node_map.get(joint.get("body2"), 2)
                lines.append(f"joint: cylindrical, {jid},")
                lines.append(f"    {b1}, {b2},")
                lines.append(f"    position, reference, global, {pos[0]}, {pos[1]}, {pos[2]},")
                lines.append(f"    axis, {axis[0]}, {axis[1]}, {axis[2]};")
        lines.append("")

    # ── 力 ──
    if forces:
        lines.append("# ── Forces ──")
        for k, force in enumerate(forces):
            fid = node_id + len(joints) + k
            ftype = force.get("type", "absolute")
            body_name = force.get("body", bodies[0]["name"])
            nid = node_map.get(body_name, 1)

            if ftype == "absolute":
                mag = force.get("magnitude", 0)
                direction = force.get("direction", [0, 0, -1])
                lines.append(f"force: absolute, {fid}, {nid},")
                lines.append(f"    {mag * direction[0]}, {mag * direction[1]}, {mag * direction[2]};")
            elif ftype == "gravity":
                g = force.get("gravity", 9.81)
                lines.append(f"gravity: {fid}, {nid}, {0}, {0}, -{g};")
            elif ftype == "spring":
                mag = force.get("magnitude", 100)
                lines.append(f"force: spring, {fid}, {nid},")
                lines.append(f"    spring constant, {mag},")
                lines.append(f"    unstressed length, 1.0,")
                lines.append(f"    damping coefficient, 0.1;")
        lines.append("")

    # ── 输出 ──
    if bodies:
        lines.append("# ── Output ──")
        node_ids_str = ", ".join(str(node_map[b["name"]]) for b in bodies)
        if out_fmt == "csv":
            lines.append(f"abstract: output, csv, all nodes,")
            lines.append(f"    position, orientation, velocity, angular velocity;")
            lines.append("")
            lines.append(f"print: results, all nodes,")
            lines.append(f"    all variables,")
            lines.append(f"    do not print, initial values;")
        else:
            lines.append(f"abstract: output, mov, all nodes,")
            lines.append(f"    position, orientation, velocity, angular velocity;")

    lines.append("")
    lines.append("end: initial value;")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════
#  结果解析
# ═══════════════════════════════════════════════════

def parse_output(run_dir: Path) -> dict:
    """解析 MBDyn 输出的 .csv / .out / .log 文件"""
    result = {"status": "completed", "nodes": {}, "log": ""}

    # 读日志
    log_files = list(run_dir.glob("*.log"))
    if log_files:
        result["log"] = log_files[0].read_text(errors="replace")[:3000]

    # 读 CSV
    csv_files = list(run_dir.glob("*.csv"))
    for csv_f in csv_files:
        try:
            with open(csv_f) as f:
                header = f.readline().strip().split(",")
                # 取前几行作为样本
                samples = []
                for i, line in enumerate(f):
                    if i >= 20:
                        break
                    vals = line.strip().split(",")
                    if len(vals) == len(header):
                        row = {}
                        for h, v in zip(header, vals):
                            try:
                                row[h.strip()] = float(v)
                            except ValueError:
                                row[h.strip()] = v.strip()
                        samples.append(row)
            node_name = csv_f.stem.replace("_node", "node")
            with open(csv_f) as f:
                total_lines = sum(1 for _ in f) - 1  # 减表头
            result["nodes"][node_name] = {
                "columns": header,
                "total_steps": total_lines,
                "samples": samples[:5]
            }
        except Exception as e:
            result["nodes"][csv_f.stem] = {"error": str(e)}

    # 检查时间序列边界
    for node_name, node_data in result["nodes"].items():
        if "samples" in node_data and node_data["samples"]:
            samples = node_data["samples"]
            first_time = samples[0].get("Time", 0)
            last_time = samples[-1].get("Time", 0)
            min_x = min(s.get("X", 0) for s in samples)
            max_x = max(s.get("X", 0) for s in samples)
            min_y = min(s.get("Y", 0) for s in samples)
            max_y = max(s.get("Y", 0) for s in samples)
            min_z = min(s.get("Z", 0) for s in samples)
            max_z = max(s.get("Z", 0) for s in samples)
            node_data["bounds"] = {
                "time_range": [first_time, last_time],
                "x_range": [min_x, max_x],
                "y_range": [min_y, max_y],
                "z_range": [min_z, max_z]
            }

    # 总步数摘要
    total = sum(
        n.get("total_steps", 0) or 0
        for n in result["nodes"].values()
    )
    result["summary"] = f"解析了 {len(result['nodes'])} 个节点的 {total} 步数据"

    return result


# ═══════════════════════════════════════════════════
#  运行管理
# ═══════════════════════════════════════════════════

RUNS = {}

def run_mbdyn(input_path: Path, run_dir: Path) -> subprocess.CompletedProcess:
    """执行 MBDyn 求解"""
    if not MBDYN_BIN or not Path(MBDYN_BIN).exists():
        raise FileNotFoundError(
            f"MBDyn 未找到: {MBDYN_BIN}。请安装 MBDyn 或设置 MBDYN_BIN 环境变量。"
        )
    return subprocess.run(
        [MBDYN_BIN, str(input_path)],
        cwd=run_dir,
        capture_output=True,
        text=True,
        timeout=600
    )


def handle_tool_call(name: str, args: dict) -> dict:
    """处理 MCP 工具调用"""
    if name == "mbdyn_query_capabilities":
        return {
            "mbdyn_binary": str(MBDYN_BIN) if MBDYN_BIN else "未找到",
            "mbdyn_installed": Path(MBDYN_BIN).exists() if MBDYN_BIN else False,
            "joint_types": ["revolute", "spherical", "ground", "prismatic", "cylindrical"],
            "force_types": ["absolute", "gravity", "spring"],
            "output_formats": ["csv", "mov"],
            "capabilities": [
                "刚体动力学",
                "运动学分析",
                "约束/铰链建模",
                "柔性体（模态缩减）",
                "接触/碰撞",
                "控制联合仿真",
                "与 OpenFOAM 流固耦合"
            ]
        }

    elif name == "mbdyn_run_simulation":
        run_id = f"run_{len(RUNS) + 1:04d}"
        run_dir = WORK_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # 生成输入
        mbd_text = generate_mbd_input(args)
        inp_file = run_dir / "input.mbd"
        inp_file.write_text(mbd_text, encoding="utf-8")

        # 运行
        proc = run_mbdyn(inp_file, run_dir)

        if proc.returncode != 0:
            RUNS[run_id] = {
                "run_id": run_id,
                "status": "failed",
                "mbd_input": mbd_text,
                "input_file": str(inp_file),
                "stdout": proc.stdout[-1000:],
                "stderr": proc.stderr[-1000:]
            }
            return {"status": "failed", "run_id": run_id,
                    "error": proc.stderr[-500:] if proc.stderr else proc.stdout[-500:]}

        # 解析结果
        results = parse_output(run_dir)
        results["run_id"] = run_id
        results["input_file"] = str(inp_file)
        results["output_dir"] = str(run_dir)
        results["mbd_input_snippet"] = mbd_text[:500] + "..."
        results["stdout_tail"] = proc.stdout[-500:] if proc.stdout else ""

        # 生成可视化
        viz_path = run_dir / "motion_trace.png"
        try:
            _generate_visualization(results, str(viz_path))
            results["visualization"] = str(viz_path)
        except Exception:
            pass

        RUNS[run_id] = {"status": "completed", "run_id": run_id}
        return results

    elif name == "mbdyn_load_file":
        inp_path = Path(args["input_file"])
        if not inp_path.exists():
            return {"error": f"文件不存在: {inp_path}"}

        run_id = f"run_{len(RUNS) + 1:04d}"
        output_dir = Path(args.get("output_dir", inp_path.parent))
        output_dir.mkdir(parents=True, exist_ok=True)

        proc = run_mbdyn(inp_path, output_dir)

        if proc.returncode != 0:
            RUNS[run_id] = {"status": "failed", "run_id": run_id}
            return {"status": "failed", "run_id": run_id,
                    "error": proc.stderr[-500:] if proc.stderr else proc.stdout[-500:]}

        results = parse_output(output_dir)
        results["run_id"] = run_id
        results["input_file"] = str(inp_path)
        RUNS[run_id] = {"status": "completed", "run_id": run_id}
        return results

    elif name == "mbdyn_get_results":
        run_id = args.get("run_id", "")
        if run_id not in RUNS:
            return {"error": f"Run {run_id} 不存在"}
        return RUNS[run_id]

    elif name == "mbdyn_visualize":
        run_id = args.get("run_id", "")
        out_path = args.get("output_path", "")
        if run_id not in RUNS:
            return {"error": f"Run {run_id} 不存在"}
        _generate_visualization(
            RUNS[run_id] if isinstance(RUNS[run_id], dict) else {},
            out_path
        )
        return {"status": "ok", "visualization": out_path}

    return {"error": f"未知工具: {name}"}


# ═══════════════════════════════════════════════════
#  可视化
# ═══════════════════════════════════════════════════

def _generate_visualization(data: dict, output_path: str):
    """生成 3D 轨迹可视化"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D

    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection="3d")

    nodes = data.get("nodes", {})
    colors = plt.cm.tab10(range(len(nodes)))

    for idx, (node_name, node_data) in enumerate(nodes.items()):
        samples = node_data.get("samples", [])
        if not samples:
            continue
        times = [s.get("Time", 0) for s in samples]
        xs = [s.get("X", 0) for s in samples]
        ys = [s.get("Y", 0) for s in samples]
        zs = [s.get("Z", 0) for s in samples]

        c = colors[idx]
        ax.scatter(xs, ys, zs, c=[c], s=40, label=node_name)
        ax.plot(xs, ys, zs, c=c, alpha=0.6, linewidth=1)

        # 标记起点/终点
        if xs:
            ax.scatter([xs[0]], [ys[0]], [zs[0]], c=c, marker="o", s=100, edgecolors="k")
            ax.scatter([xs[-1]], [ys[-1]], [zs[-1]], c=c, marker="s", s=100, edgecolors="k")

    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Z (m)")
    ax.set_title("MBDyn 运动轨迹")
    if nodes:
        ax.legend(loc="upper left")

    # 自动调整坐标轴比例
    all_x, all_y, all_z = [], [], []
    for nd in nodes.values():
        samples = nd.get("samples", [])
        all_x.extend(s.get("X", 0) for s in samples)
        all_y.extend(s.get("Y", 0) for s in samples)
        all_z.extend(s.get("Z", 0) for s in samples)
    if all_x:
        margin = max(
            max(all_x) - min(all_x),
            max(all_y) - min(all_y),
            max(all_z) - min(all_z)
        ) * 0.1 + 0.5
        ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
        ax.set_ylim(min(all_y) - margin, max(all_y) + margin)
        ax.set_zlim(min(all_z) - margin, max(all_z) + margin)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


# ═══════════════════════════════════════════════════
#  MCP stdio 协议
# ═══════════════════════════════════════════════════

def main():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    log_path = WORK_DIR / "mbdyn_mcp_server.log"
    log_f = open(log_path, "a", encoding="utf-8")

    def log(msg: str):
        log_f.write(f"{msg}\n")
        log_f.flush()

    log(f"=== MBDyn MCP Server 启动 ===")
    log(f"WORK_DIR={WORK_DIR}, MBDYN_BIN={MBDYN_BIN}")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            msg = json.loads(line)
            msg_id = msg.get("id")
            method = msg.get("method", "")

            log(f">> {method} id={msg_id}")

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "serverInfo": {"name": "mbdyn-mcp", "version": "1.0.0"},
                        "capabilities": {"tools": {}}
                    }
                }

            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {"tools": TOOLS}
                }

            elif method == "tools/call":
                tool_name = msg["params"]["name"]
                arguments = msg["params"].get("arguments", {})
                log(f"  tool={tool_name}")
                result = handle_tool_call(tool_name, arguments)
                resp = {
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": json.dumps(result, indent=2, default=str)
                        }]
                    }
                }

            elif method == "notifications/initialized":
                resp = None

            else:
                resp = {
                    "jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32601, "message": f"未知方法: {method}"}
                }

            if resp:
                out = json.dumps(resp)
                sys.stdout.write(out + "\n")
                sys.stdout.flush()
                log(f"<< {out[:200]}...")

        except json.JSONDecodeError:
            continue
        except Exception as e:
            log(f"ERROR: {e}")
            err_resp = {
                "jsonrpc": "2.0",
                "id": msg.get("id") if 'msg' in dir() else None,
                "error": {"code": -32603, "message": str(e)}
            }
            try:
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
            except Exception:
                pass

    log("=== MBDyn MCP Server 关闭 ===")
    log_f.close()


if __name__ == "__main__":
    main()
