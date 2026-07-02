"""工具结果与错误执行辅助。"""

from __future__ import annotations

import json
from typing import Any

from src.tool.framework.contracts import ToolError, ToolExecutionError, ToolResult


def build_tool_result(
    *,
    content: Any,
    model_text: str = "",
    preview_text: str = "",
    detail_text: str = "",
    summary: str = "",
    metadata: dict[str, Any] | None = None,
    annotations: dict[str, Any] | None = None,
) -> ToolResult:
    """构造一条统一的工具结果。"""

    return ToolResult(
        content=content,
        summary=summary,
        metadata=metadata or {},
        model_text=model_text,
        preview_text=preview_text or summary,
        detail_text=detail_text or model_text,
        annotations=annotations or {},
    )


def serialize_tool_result(result: ToolResult) -> str:
    """把工具结果整理为主脑可读文本。"""

    model_text = result.model_text.strip()
    if model_text:
        return model_text
    if isinstance(result.content, str):
        return result.content
    return json.dumps(result.content, ensure_ascii=False, default=str)


def build_tool_result_payload(result: ToolResult, *, detail_collapse_threshold: int, preview_limit: int) -> dict[str, Any]:
    """把工具结果整理为时间线可消费的概要与详情。"""

    detail = (result.detail_text or serialize_tool_result(result)).strip()
    preview = (
        result.preview_text.strip()
        or result.summary.strip()
        or _truncate_text(detail, preview_limit)
    )
    collapsible = (
        len(detail) > detail_collapse_threshold
        or "\n" in detail
        or detail != preview
    )
    payload = {
        "result_preview": preview,
        "result_detail": detail,
        "collapsible": collapsible,
        "collapsed_by_default": collapsible,
    }
    payload.update(result.annotations)
    return payload


def extract_tool_error(error: Exception) -> ToolError:
    """把任意异常归一化为统一 `ToolError`。"""

    if isinstance(error, ToolExecutionError):
        return error.tool_error
    model_message = str(error).strip() or error.__class__.__name__
    raw_error = str(getattr(error, "raw_error", "")).strip() or model_message
    code = str(getattr(error, "error_code", "")).strip() or "tool_error"
    retry_hint = str(getattr(error, "retry_hint", "")).strip()
    return ToolError(
        code=code,
        model_message=model_message,
        raw_error=raw_error,
        retry_hint=retry_hint,
        retryable=bool(retry_hint),
    )


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."
