"""项目内工具注册表。

该文件提供最小内存注册表，并负责装配默认工具集合。当前默认集合包含
完整 fileglide 文件系统工具，以及现有 Seedream 生图工具。
"""

from __future__ import annotations

from src.tool.contracts import ToolSpec


class ToolRegistry:
    """维护一组已注册工具。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool_spec: ToolSpec) -> None:
        """注册或覆盖一个工具。"""

        self._tools[tool_spec.name] = tool_spec

    def get(self, name: str) -> ToolSpec:
        """按名称读取一个工具。"""

        return self._tools[name]

    def list_tools(self, *tool_names: str) -> list[ToolSpec]:
        """返回全部工具或指定子集。

        Args:
            tool_names: 要暴露的工具名子集；为空时返回全部。

        Returns:
            与给定顺序一致的工具描述列表。
        """

        if not tool_names:
            return list(self._tools.values())
        return [self._tools[name] for name in tool_names if name in self._tools]


def build_default_tool_registry() -> ToolRegistry:
    """构造默认工具注册表。"""

    from src.tool.fileglide_tools import build_fileglide_tool_specs
    from src.tool.seedream_image import TOOL_SPEC

    registry = ToolRegistry()
    for tool_spec in build_fileglide_tool_specs():
        registry.register(tool_spec)
    registry.register(TOOL_SPEC)
    return registry
