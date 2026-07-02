"""工具框架结构化合同定义。

该文件定义跨 tool 复用的结构化定义对象。目标不是引入复杂插件系统，而是把
原先散落在具体工具和 runtime 中的隐式协议显式化，并保留必要的 legacy 兼容。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ToolDoc:
    """描述一个工具的结构化英文说明。

    Args:
        purpose: 工具核心职责。
        when_to_use: 适用场景列表。
        parameters: 参数说明列表。
        returns: 返回结果说明列表。
        common_failures: 常见失败与恢复提示列表。
        notes: 可选补充说明。
    """

    purpose: str
    when_to_use: tuple[str, ...]
    parameters: tuple[str, ...]
    returns: tuple[str, ...]
    common_failures: tuple[str, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolIdentity:
    """描述一个工具的基础身份信息。"""

    name: str
    display_name: str
    tool_kind: str = "native"


@dataclass(frozen=True, slots=True)
class ToolPolicies:
    """描述一个工具挂载的可复用策略组件。"""

    path_policy: Any | None = None
    traversal_policy: Any | None = None
    result_formatter: Any | None = None
    error_mapper: Any | None = None
    mutation_safety_policy: Any | None = None


@dataclass(slots=True)
class ToolError:
    """描述一次工具失败的结构化错误合同。

    Args:
        code: 稳定英文错误码。
        model_message: 面向模型的英文错误信息。
        raw_error: 原始诊断文本。
        retry_hint: 可选英文重试提示。
        retryable: 是否适合重试。
        metadata: 额外结构化诊断。
    """

    code: str
    model_message: str
    raw_error: str = ""
    retry_hint: str = ""
    retryable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolExecutionError(RuntimeError):
    """把结构化 `ToolError` 挂到异常上的轻量包装。"""

    def __init__(self, tool_error: ToolError) -> None:
        super().__init__(tool_error.model_message)
        self.tool_error = tool_error
        self.raw_error = tool_error.raw_error or tool_error.model_message
        self.error_code = tool_error.code
        self.retry_hint = tool_error.retry_hint


@dataclass(slots=True)
class ToolResult:
    """描述一次工具调用的规范化结果。

    Args:
        content: 原始结构化结果内容。
        summary: legacy 摘要字段；新的调用方应优先使用 `preview_text`。
        metadata: legacy 附加元数据；迁移期间保留兼容。
        model_text: 面向模型的英文正文。
        preview_text: 面向 timeline / UI 的短摘要。
        detail_text: 面向 UI 的详细文本。
        annotations: 结构化附加标注。
    """

    content: Any
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    model_text: str = ""
    preview_text: str = ""
    detail_text: str = ""
    annotations: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_text:
            legacy_model_text = str(self.metadata.get("model_text", "")).strip()
            if legacy_model_text:
                self.model_text = legacy_model_text
        if not self.preview_text:
            self.preview_text = self.summary
        if not self.detail_text and self.model_text:
            self.detail_text = self.model_text

    @property
    def data(self) -> Any:
        """返回原始结构化结果。"""

        return self.content


@dataclass(slots=True)
class ToolSpec:
    """描述一个可暴露给主脑的业务工具。"""

    name: str
    description: str = ""
    display_name: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    handler: Callable[..., ToolResult] | None = None
    tool_kind: str = "native"
    doc: ToolDoc | None = None
    policies: ToolPolicies = field(default_factory=ToolPolicies)

    def __post_init__(self) -> None:
        from src.tool.framework.render import render_tool_description

        if not self.display_name:
            self.display_name = self.name
        if self.doc is not None and not self.description:
            self.description = render_tool_description(self.doc)
        if self.handler is None:
            raise RuntimeError(f"Tool '{self.name}' must define a handler.")

    @property
    def identity(self) -> ToolIdentity:
        """返回工具身份对象。"""

        return ToolIdentity(
            name=self.name,
            display_name=self.display_name,
            tool_kind=self.tool_kind,
        )
