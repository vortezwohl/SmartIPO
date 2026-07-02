"""主脑工具契约兼容入口。

该文件保留项目内最常用的工具上下文对象，并把结构化 `ToolSpec` / `ToolResult`
等新合同从 `src.tool.framework` 重新导出，保证旧引用路径继续可用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from src.tool.framework.contracts import (
    ToolDoc,
    ToolError,
    ToolExecutionError,
    ToolIdentity,
    ToolPolicies,
    ToolResult,
    ToolSpec,
)


@dataclass(slots=True)
class ToolContext:
    """描述一次工具调用可用的共享上下文。

    Args:
        services: 共享服务对象字典。
        llm: 可选文本模型调用器。
        workspace_root: fileglide 等本地工具默认作用域根目录。
        event_sink: 可选运行时事件接收器。
    """

    services: dict[str, Any] = field(default_factory=dict)
    llm: Any | None = None
    workspace_root: str = "."
    event_sink: Callable[[Any], None] | None = None

    def resolve_service(self, name: str, default: Any = None) -> Any:
        """按名称读取共享服务对象。"""

        return self.services.get(name, default)

    def emit(self, event: Any) -> None:
        """把运行时事件发送给上层消费者。"""

        if self.event_sink is not None:
            self.event_sink(event)


__all__ = [
    "ToolContext",
    "ToolDoc",
    "ToolError",
    "ToolExecutionError",
    "ToolIdentity",
    "ToolPolicies",
    "ToolResult",
    "ToolSpec",
]
