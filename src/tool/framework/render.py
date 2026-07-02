"""工具文档渲染器。"""

from __future__ import annotations

from src.tool.framework.contracts import ToolDoc


def render_tool_description(doc: ToolDoc) -> str:
    """把结构化 `ToolDoc` 渲染成 provider-facing 英文 description。"""

    sections: list[tuple[str, tuple[str, ...]]] = [
        ("Purpose", (doc.purpose,)),
        ("When to use", doc.when_to_use),
        ("Parameters", doc.parameters),
        ("Returns", doc.returns),
        ("Common failures", doc.common_failures),
    ]
    if doc.notes:
        sections.append(("Notes", doc.notes))
    lines: list[str] = []
    for title, bullets in sections:
        lines.append(f"{title}:")
        lines.extend(f"- {bullet}" for bullet in bullets)
        lines.append("")
    return "\n".join(lines).rstrip()
