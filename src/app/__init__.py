"""应用装配入口。"""

from src.app.default_agent import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_WORKBENCH_TOOL_NAMES,
    build_default_agent,
)

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "DEFAULT_WORKBENCH_TOOL_NAMES",
    "build_default_agent",
]
