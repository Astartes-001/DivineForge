#!/usr/bin/env python3
"""
MBDyn MCP Server — 离线验证测试
==============================
不依赖 MBDyn 安装，测试模板生成、结果解析、可视化等核心功能。

用法:
    python test_mbdyn_mcp.py
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# 将 mbdyn-mcp 目录加入路径
PROJECT_ROOT = Path(__file__).parent
MCP_DIR = PROJECT_ROOT / "MCP" / "mbdyn-mcp"
sys.path.insert(0, str(MCP_DIR))

from mbdyn_mcp_server import generate_mbd_input, parse_output, TOOLS

PASS = 0
FAIL = 0

def check(name: str, condition: bool, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  {detail}")

def test_tools_definition():
    print("\n── 1. 工具定义 ──")
    check("定义了 5 个工具", len(TOOLS) == 5)
    names = [t["name"] for t in TOOLS]
    expected = ["mbdyn_run_simulation", "mbdyn_load_file", "mbdyn_get_results",
                 "mbdyn_query_capabilities", "mbdyn_visualize"]
    for e in expected:
        check(f"  包含工具: {e}", e in names)

def test_single_body():
    print("\n── 2. 单刚体自由落体 ──")
    params = {
        "bodies": [{
            "name": "ball",
            "mass": 1.0,
            "inertia": [0.1, 0.1, 0.1, 0, 0, 0],
            "initial_pos": [0, 0, 10],
            "initial_rot": [0, 0, 0]
        }],
        "joints": [
            {"type": "ground", "body1": "ball", "position": [0, 0, 10]}
        ],
        "forces": [
            {"type": "gravity", "body": "ball", "magnitude": 9.81}
        ],
        "time": {"stop": 2.0, "step": 0.01}
    }
    mbd = generate_mbd_input(params)
    check("生成了 .mbd 文本", len(mbd) > 100)
    check("包含 structural 节点", "structural:" in mbd)
    check("包含 body 定义", "body:" in mbd)
    check("包含 gravity 力", "gravity:" in mbd)
    check("包含输出定义", "abstract: output" in mbd)

def test_double_pendulum():
    print("\n── 3. 双摆机构 ──")
    params = {
        "bodies": [
            {"name": "link1", "mass": 0.5, "inertia": [0.01,0.01,0.01,0,0,0],
             "initial_pos": [0, 0, 2], "initial_rot": [0.3, 0, 0]},
            {"name": "link2", "mass": 0.3, "inertia": [0.005,0.005,0.005,0,0,0],
             "initial_pos": [0, 0, 1], "initial_rot": [-0.5, 0, 0]}
        ],
        "joints": [
            {"type": "revolute", "body1": "link1", "body2": "link2",
             "position": [0, 0, 1.5], "axis": [1, 0, 0]}
        ],
        "forces": [
            {"type": "gravity", "body": "link1", "magnitude": 9.81}
        ],
        "time": {"stop": 5.0, "step": 0.01}
    }
    mbd = generate_mbd_input(params)
    check("双刚体生成成功", len(mbd) > 200)
    check("包含旋转铰链", "revolute" in mbd)
    check("包含旋转轴方向", "axis" in mbd)

def test_spring_system():
    print("\n── 4. 弹簧-质量系统 ──")
    params = {
        "bodies": [
            {"name": "mass", "mass": 2.0, "inertia": [1,1,1,0,0,0],
             "initial_pos": [0, 0, 0.5]}
        ],
        "joints": [
            {"type": "prismatic", "body1": "mass", "body2": "mass",
             "position": [0, 0, 0], "axis": [0, 0, 1]}
        ],
        "forces": [
            {"type": "spring", "body": "mass", "magnitude": 100}
        ],
        "time": {"stop": 3.0, "step": 0.01}
    }
    mbd = generate_mbd_input(params)
    check("弹簧系统生成成功", len(mbd) > 100)
    check("包含 spring 力", "spring" in mbd.lower())
    check("包含移动副", "prismatic" in mbd)

def test_cylindrical_joint():
    print("\n── 5. 圆柱副 ──")
    params = {
        "bodies": [
            {"name": "piston", "mass": 0.5, "inertia": [0.01,0.01,0.01,0,0,0],
             "initial_pos": [0, 0, 0]},
            {"name": "cylinder", "mass": 1.0, "inertia": [0.02,0.02,0.02,0,0,0],
             "initial_pos": [0, 0, 0.2]}
        ],
        "joints": [
            {"type": "cylindrical", "body1": "piston", "body2": "cylinder",
             "position": [0, 0, 0.1], "axis": [0, 0, 1]}
        ],
        "time": {"stop": 1.0, "step": 0.01}
    }
    mbd = generate_mbd_input(params)
    check("圆柱副生成成功", len(mbd) > 100)
    check("包含 cylindrical 铰链", "cylindrical" in mbd)

def test_spherical_joint():
    print("\n── 6. 球铰 ──")
    params = {
        "bodies": [
            {"name": "arm", "mass": 0.5, "inertia": [0.01,0.01,0.01,0,0,0],
             "initial_pos": [0, 0, 0.5]},
            {"name": "base", "mass": 2.0, "inertia": [0.1,0.1,0.1,0,0,0],
             "initial_pos": [0, 0, 0]}
        ],
        "joints": [
            {"type": "spherical", "body1": "arm", "body2": "base",
             "position": [0, 0, 0.25]}
        ],
        "time": {"stop": 2.0, "step": 0.01}
    }
    mbd = generate_mbd_input(params)
    check("球铰生成成功", len(mbd) > 100)
    check("包含 spherical 铰链", "spherical" in mbd)

def test_absolute_force():
    print("\n── 7. 定向力 ──")
    params = {
        "bodies": [
            {"name": "block", "mass": 5.0, "inertia": [0.5,0.5,0.5,0,0,0],
             "initial_pos": [0, 0, 0]}
        ],
        "joints": [
            {"type": "ground", "body1": "block", "position": [0, 0, 0]}
        ],
        "forces": [
            {"type": "absolute", "body": "block", "magnitude": 50,
             "direction": [1, 0.5, 0]}
        ],
        "time": {"stop": 2.0, "step": 0.01}
    }
    mbd = generate_mbd_input(params)
    check("定向力生成成功", len(mbd) > 100)
    check("包含 force: absolute", "force: absolute" in mbd)

def test_parse_output():
    print("\n── 8. 结果解析 (离线) ──")
    # 创建模拟输出
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # 模拟 CSV
        csv_content = "Time,X,Y,Z\n0,0,0,0\n0.01,0.001,0,0\n0.02,0.002,0,0\n"
        (tmp_path / "ball.csv").write_text(csv_content)
        # 模拟日志
        (tmp_path / "run.log").write_text("Simulation completed successfully")

        result = parse_output(tmp_path)
        check("状态为 completed", result.get("status") == "completed")
        check("解析出节点", len(result.get("nodes", {})) > 0)
        check("包含日志", len(result.get("log", "")) > 0)
        check("生成了摘要", "summary" in result)

def test_output_format():
    print("\n── 9. 输出格式 ──")
    params1 = {
        "bodies": [{"name": "b", "mass": 1, "inertia": [1,1,1,0,0,0], "initial_pos": [0,0,0]}],
        "joints": [],
        "time": {"stop": 1.0}, "output": {"format": "csv"}
    }
    csv_out = generate_mbd_input(params1)
    check("CSV 格式包含 abstract: output, csv", "abstract: output, csv" in csv_out)

    params2 = {
        "bodies": [{"name": "b", "mass": 1, "inertia": [1,1,1,0,0,0], "initial_pos": [0,0,0]}],
        "joints": [],
        "time": {"stop": 1.0}, "output": {"format": "mov"}
    }
    mov_out = generate_mbd_input(params2)
    check("MOV 格式包含 abstract: output, mov", "abstract: output, mov" in mov_out)

def test_capabilities():
    print("\n── 10. 能力查询 ──")
    from mbdyn_mcp_server import handle_tool_call
    result = handle_tool_call("mbdyn_query_capabilities", {})
    check("返回了铰链类型", "joint_types" in result)
    check("返回了力类型", "force_types" in result)
    check("返回了能力列表", "capabilities" in result)
    check("铰链包含 revolute", "revolute" in result.get("joint_types", []))
    check("力包含 absolute", "absolute" in result.get("force_types", []))
    check("能力包含 刚体动力学", "刚体动力学" in str(result.get("capabilities", [])))

# ════════════════════════════════════════
#  Main
# ════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  MBDyn MCP Server — 离线验证测试")
    print("=" * 60)

    test_tools_definition()
    test_single_body()
    test_double_pendulum()
    test_spring_system()
    test_cylindrical_joint()
    test_spherical_joint()
    test_absolute_force()
    test_parse_output()
    test_output_format()
    test_capabilities()

    total = PASS + FAIL
    print("\n" + "=" * 60)
    print(f"  测试结果: {PASS}/{total} 通过, {FAIL}/{total} 失败")
    print("=" * 60)

    if FAIL > 0:
        sys.exit(1)
    else:
        print("\n  🎉 全部测试通过！MBDyn MCP Server 核心功能正常。")
        sys.exit(0)
