"""EasyHarness 工具与默认装配测试。

该文件验证 SmartIPO 默认工具集合已经切换为 EasyHarness 公共工具合同：
官方 fileglide toolset 提供文件能力，FMP 业务工具使用 `easyharness.tool` 声明。
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from easyharness import Agent, ModelConfig
from src.agent import (
    DEFAULT_BUSINESS_TOOL_NAMES,
    DEFAULT_FILEGLIDE_TOOL_NAMES,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_WORKBENCH_TOOL_NAMES,
    build_default_model_config,
    build_default_agent,
    build_default_tools,
)
from src.tool.fmp_tools import FMP_TOOL_NAMES


class EasyHarnessToolingTests(unittest.TestCase):
    """验证 EasyHarness 工具体系与默认 composition 层。"""

    def test_default_tool_names_use_easyharness_public_names(self) -> None:
        """默认工具名应使用官方 fileglide 与业务工具公开名。"""

        self.assertIn("fileglide_read_text", DEFAULT_FILEGLIDE_TOOL_NAMES)
        self.assertIn("fileglide_edit_text", DEFAULT_FILEGLIDE_TOOL_NAMES)
        self.assertIn("fmp_get_profile", DEFAULT_BUSINESS_TOOL_NAMES)
        self.assertEqual(len(FMP_TOOL_NAMES), 38)
        self.assertEqual(
            DEFAULT_WORKBENCH_TOOL_NAMES,
            (*DEFAULT_FILEGLIDE_TOOL_NAMES, *DEFAULT_BUSINESS_TOOL_NAMES),
        )
        self.assertIn("EasyHarness", DEFAULT_SYSTEM_PROMPT)
        self.assertNotIn("text.read", DEFAULT_SYSTEM_PROMPT)

    def test_build_default_tools_returns_public_tool_objects(self) -> None:
        """默认工具对象集合应可直接交给 EasyHarness Agent 使用。"""

        tools = build_default_tools(".")
        names = {getattr(item, "tool_name", "") for item in tools}

        self.assertIn("fileglide_read_text", names)
        self.assertIn("fileglide_search_text", names)
        self.assertIn("fmp_get_profile", names)

    def test_build_default_agent_returns_easyharness_agent(self) -> None:
        """默认 agent 装配入口应直接返回 EasyHarness Agent。"""

        with patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False):
            agent = build_default_agent(".")

        self.assertIsInstance(agent, Agent)

    def test_build_default_model_config_returns_model_config(self) -> None:
        """默认模型配置应直接返回 EasyHarness ModelConfig。"""

        with patch.dict(
            "os.environ",
            {
                "API_KEY": "test-key",
                "API_BASE": "https://example.com/v1",
            },
            clear=False,
        ):
            model = build_default_model_config()

        self.assertIsInstance(model, ModelConfig)
        self.assertEqual(model.model, "openai/deepseek-v4-flash")
        self.assertEqual(model.api_key, "test-key")
        self.assertEqual(model.base_url, "https://example.com/v1")
        self.assertEqual(model.temperature, 0.01)
        self.assertEqual(model.top_p, 0.01)
        self.assertIsNone(model.seed)

if __name__ == "__main__":
    unittest.main()
