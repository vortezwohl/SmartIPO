"""Textual 本地工作台入口。"""

from src.app.default_agent import build_default_agent
from src.tui.app import AgentWorkbenchApp

__all__ = ["AgentWorkbenchApp", "build_default_agent"]
