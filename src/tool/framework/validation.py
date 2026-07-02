"""工具 catalog 校验与 provider 名规范化。"""

from __future__ import annotations

import re
from typing import Iterable

from src.tool.framework.contracts import ToolDoc, ToolSpec


_INVALID_PROVIDER_TOOL_NAME = re.compile(r"[^a-zA-Z0-9_-]+")
_CHINESE_TEXT = re.compile(r"[\u4e00-\u9fff]")
_BACKTICK_NAME = re.compile(r"`([^`]+)`")


def sanitize_provider_tool_name(name: str) -> str:
    """把内部工具名转换为 provider 可接受的名字。"""

    sanitized = _INVALID_PROVIDER_TOOL_NAME.sub("_", name)
    if not sanitized:
        raise RuntimeError(f"工具名 '{name}' 无法转换为合法的 provider 工具名。")
    return sanitized


def validate_tool_catalog(tool_specs: Iterable[ToolSpec]) -> None:
    """校验一组工具合同的一致性。"""

    provider_names: dict[str, str] = {}
    for tool_spec in tool_specs:
        validate_tool_spec(tool_spec)
        provider_name = sanitize_provider_tool_name(tool_spec.name)
        existing = provider_names.get(provider_name)
        if existing is not None and existing != tool_spec.name:
            raise RuntimeError(
                "不同内部工具名映射到了同一个 provider 工具名: "
                f"'{existing}' 与 '{tool_spec.name}' -> '{provider_name}'。"
            )
        provider_names[provider_name] = tool_spec.name


def validate_tool_spec(tool_spec: ToolSpec) -> None:
    """校验单个工具合同。"""

    if tool_spec.doc is None:
        raise RuntimeError(
            f"Tool '{tool_spec.name}' must define structured documentation."
        )
    _validate_required_doc_sections(tool_spec.name, tool_spec.doc)
    _validate_english_only(tool_spec.name, tool_spec.doc)
    _validate_schema_alignment(tool_spec)


def _validate_required_doc_sections(tool_name: str, doc: ToolDoc) -> None:
    if not doc.purpose.strip():
        raise RuntimeError(f"Tool '{tool_name}' is missing doc.purpose.")
    if not doc.when_to_use:
        raise RuntimeError(f"Tool '{tool_name}' is missing doc.when_to_use.")
    if not doc.parameters:
        raise RuntimeError(f"Tool '{tool_name}' is missing doc.parameters.")
    if not doc.returns:
        raise RuntimeError(f"Tool '{tool_name}' is missing doc.returns.")
    if not doc.common_failures:
        raise RuntimeError(f"Tool '{tool_name}' is missing doc.common_failures.")


def _validate_english_only(tool_name: str, doc: ToolDoc) -> None:
    values = [
        doc.purpose,
        *doc.when_to_use,
        *doc.parameters,
        *doc.returns,
        *doc.common_failures,
        *doc.notes,
    ]
    for value in values:
        if _CHINESE_TEXT.search(value):
            raise RuntimeError(
                f"Tool '{tool_name}' contains non-English contract text: {value!r}"
            )


def _validate_schema_alignment(tool_spec: ToolSpec) -> None:
    properties = tool_spec.input_schema.get("properties", {})
    if not isinstance(properties, dict):
        return
    documented = _extract_documented_names(tool_spec.doc.parameters)
    property_names = set(properties.keys())
    missing = sorted(property_names - documented)
    if missing:
        raise RuntimeError(
            f"Tool '{tool_spec.name}' schema fields are undocumented: {missing}"
        )
    extra = sorted(documented - property_names)
    if extra:
        raise RuntimeError(
            f"Tool '{tool_spec.name}' documents unknown schema fields: {extra}"
        )


def _extract_documented_names(items: tuple[str, ...]) -> set[str]:
    names: set[str] = set()
    for item in items:
        match = _BACKTICK_NAME.search(item)
        if match is None:
            continue
        names.add(match.group(1))
    return names
