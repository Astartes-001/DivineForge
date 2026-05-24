# MBDyn MCP Server

多体动力学仿真 MCP 桥接服务器。作为 Hermes Agent / Claude Desktop 的 MCP 工具，将结构化仿真参数转为 MBDyn `.mbd` 输入文件并执行求解。

## 安装

```powershell
# 1. 安装 MBDyn
# https://www.mbdyn.org/download.html

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 验证
python mbdyn_mcp_server.py
# 输入: {"jsonrpc":"2.0","method":"tools/list","id":1}
```

## 提供的工具

| 工具名 | 功能 |
|:------|:-----|
| `mbdyn_run_simulation` | 结构化参数直接跑仿真 |
| `mbdyn_load_file` | 加载已有 `.mbd` 文件 |
| `mbdyn_get_results` | 查询运行结果 |
| `mbdyn_visualize` | 生成 3D 运动轨迹 PNG |
| `mbdyn_query_capabilities` | 查询 MBDyn 能力 |

## 支持的铰链类型

- `revolute`（旋转副）
- `spherical`（球铰）
- `ground`（固定）
- `prismatic`（移动副）
- `cylindrical`（圆柱副）

## 支持的力类型

- `absolute`（定方向力）
- `gravity`（重力）
- `spring`（弹簧）

## MCP 配置

```json
{
    "mbdyn": {
        "command": "python",
        "args": ["D:\\MCP\\mbdyn-mcp\\mbdyn_mcp_server.py"]
    }
}
```
