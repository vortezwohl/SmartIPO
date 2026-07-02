"""工具框架公共入口。

该包沉淀跨具体 tool 复用的最小合同能力：结构化文档、结果/错误合同、
provider description 渲染、catalog 校验，以及运行时可复用的策略接口。
"""

from src.tool.framework.contracts import (
    ToolDoc,
    ToolError,
    ToolExecutionError,
    ToolIdentity,
    ToolPolicies,
    ToolResult,
    ToolSpec,
)
from src.tool.framework.execution import (
    build_tool_result,
    build_tool_result_payload,
    extract_tool_error,
    serialize_tool_result,
)
from src.tool.framework.render import render_tool_description
from src.tool.framework.validation import (
    sanitize_provider_tool_name,
    validate_tool_catalog,
    validate_tool_spec,
)

__all__ = [
    "ToolDoc",
    "ToolError",
    "ToolExecutionError",
    "ToolIdentity",
    "ToolPolicies",
    "ToolResult",
    "ToolSpec",
    "build_tool_result",
    "build_tool_result_payload",
    "extract_tool_error",
    "render_tool_description",
    "sanitize_provider_tool_name",
    "serialize_tool_result",
    "validate_tool_catalog",
    "validate_tool_spec",
]
