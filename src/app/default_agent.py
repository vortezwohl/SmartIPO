"""默认本地 agent 装配入口。

该文件承担应用 composition 层职责：定义默认 system prompt、默认工具集、
默认模型和默认 agent 组装。TUI、future WebUI 等界面层只消费这里提供的
装配结果，不再在 UI 内部定义底层协议和默认运行栈。
"""

from __future__ import annotations

import os

from src.core.agent import Agent
from src.service.model_hub import create_default_brain_model
from src.tool.registry import build_default_tool_registry


DEFAULT_SYSTEM_PROMPT = """
你是 SmartIPO 的本地 coding agent。
- 接到一个任务后要自己连续规划并调用工具，直到任务自然结束。
- 优先使用 fileglide 完成读取、搜索、写入、移动等本地文件系统操作。
- 先做范围尽可能小的只读探索，再进入修改。
- 先读再改，避免无根据猜测。
- 工具失败时要直接暴露失败，不要伪装成成功。
""".strip()

DEFAULT_WORKBENCH_TOOL_NAMES = (
    "path.list",
    "file.list",
    "text.read",
    "text.grep",
)


def build_default_agent(event_sink) -> Agent:
    """构造默认本地主脑控制器。"""

    return Agent(
        model=create_default_brain_model(),
        tool_registry=build_default_tool_registry(),
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        tool_names=DEFAULT_WORKBENCH_TOOL_NAMES,
        event_sink=event_sink,
        workspace_root=os.getcwd(),
    )
