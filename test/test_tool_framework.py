"""工具框架合同测试。

该文件覆盖结构化 tool doc、catalog validation、English-only 规则，以及
composition 与 TUI 之间的边界约束，确保本次框架化改动有独立门禁。
"""

from __future__ import annotations

import unittest

from src.app.default_agent import (
    DEFAULT_SYSTEM_PROMPT as APP_DEFAULT_SYSTEM_PROMPT,
    DEFAULT_WORKBENCH_TOOL_NAMES as APP_DEFAULT_WORKBENCH_TOOL_NAMES,
    build_default_agent as build_app_default_agent,
)
from src.tool.contracts import ToolDoc, ToolResult, ToolSpec
from src.tool.framework.validation import validate_tool_spec
from src.tool.registry import build_default_tool_registry
from src.tui import build_default_agent as build_tui_default_agent
from src.tui.app import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_WORKBENCH_TOOL_NAMES,
)


class ToolFrameworkTests(unittest.TestCase):
    """验证结构化 tool framework 的关键合同。"""

    def test_structured_doc_renders_provider_description(self) -> None:
        """结构化文档应自动渲染 provider-facing description。"""

        spec = ToolSpec(
            name="demo_tool",
            display_name="Demo Tool",
            input_schema={
                "type": "object",
                "properties": {"target": {"type": "string"}},
            },
            handler=lambda _context, **_kwargs: ToolResult(content="ok"),
            doc=ToolDoc(
                purpose="Read a demo target.",
                when_to_use=("You need a tiny structured demo tool.",),
                parameters=("`target`: Demo target path.",),
                returns=("`content`: Demo output.",),
                common_failures=("Target missing: the demo target does not exist.",),
            ),
        )

        self.assertIn("Purpose:", spec.description)
        self.assertIn("Parameters:", spec.description)
        validate_tool_spec(spec)

    def test_validator_rejects_non_english_contract_text(self) -> None:
        """结构化合同中的中文文本应被 English-only 校验拒绝。"""

        spec = ToolSpec(
            name="bad_tool",
            display_name="Bad Tool",
            input_schema={
                "type": "object",
                "properties": {"target": {"type": "string"}},
            },
            handler=lambda _context, **_kwargs: ToolResult(content="ok"),
            doc=ToolDoc(
                purpose="读取 demo target.",
                when_to_use=("You need a tiny structured demo tool.",),
                parameters=("`target`: Demo target path.",),
                returns=("`content`: Demo output.",),
                common_failures=("Target missing: the demo target does not exist.",),
            ),
        )

        with self.assertRaisesRegex(RuntimeError, "non-English contract text"):
            validate_tool_spec(spec)

    def test_validator_rejects_undocumented_schema_field(self) -> None:
        """schema 字段若未被结构化参数文档覆盖，应校验失败。"""

        spec = ToolSpec(
            name="broken_demo_tool",
            display_name="Broken Demo Tool",
            input_schema={
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "mode": {"type": "string"},
                },
            },
            handler=lambda _context, **_kwargs: ToolResult(content="ok"),
            doc=ToolDoc(
                purpose="Read a demo target.",
                when_to_use=("You need a tiny structured demo tool.",),
                parameters=("`target`: Demo target path.",),
                returns=("`content`: Demo output.",),
                common_failures=("Target missing: the demo target does not exist.",),
            ),
        )

        with self.assertRaisesRegex(RuntimeError, "schema fields are undocumented"):
            validate_tool_spec(spec)

    def test_default_registry_and_tui_reexport_use_composition_layer(self) -> None:
        """默认 registry 应通过校验，TUI 默认装配入口应来自 composition 层。"""

        registry = build_default_tool_registry()

        self.assertIs(build_tui_default_agent, build_app_default_agent)
        self.assertEqual(DEFAULT_SYSTEM_PROMPT, APP_DEFAULT_SYSTEM_PROMPT)
        self.assertEqual(
            DEFAULT_WORKBENCH_TOOL_NAMES,
            APP_DEFAULT_WORKBENCH_TOOL_NAMES,
        )
        self.assertIsNotNone(registry.get("text.read").doc)
        self.assertIsNotNone(registry.get("generate_seedream_image").doc)


if __name__ == "__main__":
    unittest.main()
