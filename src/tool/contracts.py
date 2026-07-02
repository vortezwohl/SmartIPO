"""主脑工具契约定义。

该文件提供项目内工具暴露给 strands 运行时所需的最小静态描述、调用上下文
和事件桥接能力。它仍然保持为薄层，不引入插件系统或权限框架。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


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
        """按名称读取共享服务对象。

        Args:
            name: 服务名。
            default: 未找到时返回的默认值。

        Returns:
            命中的服务对象或默认值。
        """

        return self.services.get(name, default)

    def emit(self, event: Any) -> None:
        """把运行时事件发送给上层消费者。"""

        if self.event_sink is not None:
            self.event_sink(event)


@dataclass(slots=True)
class ToolResult:
    """描述一次工具调用的规范化结果。

    Args:
        content: 原始结果内容。
        summary: 主脑可直接消费的摘要文本。
        metadata: 附加元数据。
    """

    content: Any
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """描述一个可暴露给主脑的业务工具。

    Args:
        name: 工具名。
        description: 工具职责说明。
        display_name: 面向人类的显示名。
        input_schema: strands tool 输入 schema。
        handler: 实际执行业务逻辑的处理函数。
        tool_kind: 工具类别，供 UI 展示使用。
    """

    name: str
    description: str
    display_name: str
    input_schema: dict[str, Any]
    handler: Callable[..., ToolResult]
    tool_kind: str = "native"
