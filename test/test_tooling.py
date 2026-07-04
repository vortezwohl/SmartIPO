"""EasyHarness 工具装配与会话管理测试。

本文件验证两类公共契约：

1. OpenBuffett 默认 agent / tool 装配继续使用 EasyHarness 公开表面；
2. 默认 agent 继续接上 EasyHarness 官方提供的会话压缩管理器。
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from easyharness import Agent, ModelConfig
from easyharness._internal.conversation import EventingSummarizingConversationManager

from src.agent import (
    DEFAULT_AGENT_BRAND,
    DEFAULT_BASIC_TOOL_NAMES,
    DEFAULT_BUSINESS_TOOL_NAMES,
    DEFAULT_FILEGLIDE_TOOL_NAMES,
    DEFAULT_OPENING_MESSAGE,
    DEFAULT_REPORT_FOLLOW_UP,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_WORKBENCH_TOOL_NAMES,
    build_default_agent,
    build_default_model_config,
    build_default_tools,
)
from src.ext.fmp import FmpClient
from src.tool.fmp_tools import FMP_TOOL_NAMES

_PROJECT_TOOL_METADATA_REQUIRED_SECTIONS = (
    "Purpose:",
    "When To Use:",
    "Parameters:",
    "Returns:",
    "Common Failures:",
)

_PROJECT_OWNED_TOOL_NAMES = (
    "calculator",
    "now",
    "web_fetch_page",
)

_KEY_FMP_RUNTIME_TOOL_NAMES = (
    "fmp_get_quote",
    "fmp_get_historical_price_eod_full",
    "fmp_get_historical_market_cap",
    "fmp_get_stock_peers",
    "fmp_get_company_screener",
    "fmp_get_financial_estimates",
    "fmp_get_earnings_transcripts",
)


def _has_required_metadata_sections(description: str) -> bool:
    """判断工具描述是否包含项目要求的全部元数据章节。"""

    return all(section in description for section in _PROJECT_TOOL_METADATA_REQUIRED_SECTIONS)


class EasyHarnessToolingTests(unittest.TestCase):
    """验证默认工具装配、提示词和会话管理装配契约。"""

    @staticmethod
    def _public_fmp_method_count() -> int:
        """按定义顺序统计 `FmpClient` 的公开方法数量。"""

        return sum(
            1
            for name, value in FmpClient.__dict__.items()
            if not name.startswith("_") and callable(value)
        )

    @staticmethod
    def _tool_specs_by_name() -> dict[str, dict[str, object]]:
        """读取默认工具集合的 runtime `tool_spec`。"""

        return {
            item.tool_name: item.tool_spec
            for item in build_default_tools(".")
            if getattr(item, "tool_name", "")
        }

    def test_default_tool_names_use_easyharness_public_names(self) -> None:
        """默认工具名应继续基于 EasyHarness 公开工具命名。"""

        self.assertIn("fileglide_read_text", DEFAULT_FILEGLIDE_TOOL_NAMES)
        self.assertIn("fileglide_edit_text", DEFAULT_FILEGLIDE_TOOL_NAMES)
        self.assertEqual(
            DEFAULT_BASIC_TOOL_NAMES,
            ("calculator", "now", "web_fetch_page"),
        )
        self.assertIn("calculator", DEFAULT_BUSINESS_TOOL_NAMES)
        self.assertIn("fmp_get_profile", DEFAULT_BUSINESS_TOOL_NAMES)
        self.assertEqual(len(FMP_TOOL_NAMES), self._public_fmp_method_count())
        self.assertEqual(
            DEFAULT_WORKBENCH_TOOL_NAMES,
            (*DEFAULT_FILEGLIDE_TOOL_NAMES, *DEFAULT_BUSINESS_TOOL_NAMES),
        )
        self.assertEqual(DEFAULT_AGENT_BRAND, "OpenBuffett")
        self.assertIn("OpenBuffett", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("ticker", DEFAULT_SYSTEM_PROMPT)
        self.assertIn(DEFAULT_REPORT_FOLLOW_UP, DEFAULT_SYSTEM_PROMPT)

    def test_build_default_tools_returns_public_tool_objects(self) -> None:
        """默认工具集合应可直接交给 EasyHarness Agent 使用。"""

        tools = build_default_tools(".")
        names = {getattr(item, "tool_name", "") for item in tools}

        self.assertIn("fileglide_read_text", names)
        self.assertIn("fileglide_search_text", names)
        self.assertIn("calculator", names)
        self.assertIn("now", names)
        self.assertIn("web_fetch_page", names)
        self.assertIn("fmp_get_profile", names)

    def test_runtime_tool_specs_expose_metadata_sections(self) -> None:
        """项目自有工具的 runtime 描述必须包含完整元数据章节。"""

        specs = self._tool_specs_by_name()

        for tool_name in _PROJECT_OWNED_TOOL_NAMES:
            description = str(specs[tool_name]["description"])
            self.assertTrue(
                _has_required_metadata_sections(description),
                msg=f"{tool_name} 缺少必需的元数据章节。",
            )

        self.assertTrue(str(specs["fileglide_read_text"]["description"]).strip())

    def test_key_fmp_runtime_metadata_distinguishes_neighboring_tools(self) -> None:
        """关键 FMP 工具的 runtime 描述应体现边界差异。"""

        specs = self._tool_specs_by_name()

        for tool_name in _KEY_FMP_RUNTIME_TOOL_NAMES:
            description = str(specs[tool_name]["description"])
            self.assertTrue(
                _has_required_metadata_sections(description),
                msg=f"{tool_name} runtime 描述不完整。",
            )
            self.assertNotIn(
                "当任务明确需要通过 Financial Modeling Prep",
                description,
                msg=f"{tool_name} 仍保留旧模板化的 when_to_use 描述。",
            )

        quote_description = str(specs["fmp_get_quote"]["description"])
        self.assertIn("快照", quote_description)

        historical_price_description = str(
            specs["fmp_get_historical_price_eod_full"]["description"]
        )
        self.assertIn("历史价格", historical_price_description)

        market_cap_description = str(specs["fmp_get_historical_market_cap"]["description"])
        self.assertIn("历史市值", market_cap_description)

        peers_description = str(specs["fmp_get_stock_peers"]["description"])
        self.assertIn("company screener", peers_description)

    def test_company_screener_runtime_metadata_includes_filter_examples(self) -> None:
        """company screener 工具应提供高频筛选参数示例。"""

        specs = self._tool_specs_by_name()
        screener_description = str(specs["fmp_get_company_screener"]["description"])
        screener_schema = specs["fmp_get_company_screener"]["inputSchema"]["json"]
        extra_params_description = str(
            screener_schema["properties"]["extra_params"]["description"]
        )

        for expected in ("sector", "industry", "exchange", "marketCapMoreThan"):
            self.assertIn(expected, screener_description)
            self.assertIn(expected, extra_params_description)

    def test_opening_message_and_system_prompt_keep_product_identity(self) -> None:
        """默认开场文案与 system prompt 应继续体现当前产品定位。"""

        self.assertIn("OpenBuffett", DEFAULT_OPENING_MESSAGE)
        self.assertIn("OpenBuffett", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("ticker", DEFAULT_SYSTEM_PROMPT)
        self.assertIn(DEFAULT_REPORT_FOLLOW_UP, DEFAULT_SYSTEM_PROMPT)

    def test_build_default_agent_returns_easyharness_agent(self) -> None:
        """默认 agent 装配入口应继续返回 EasyHarness Agent。"""

        with patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False):
            agent = build_default_agent(".")

        self.assertIsInstance(agent, Agent)

    def test_build_default_model_config_returns_model_config(self) -> None:
        """默认模型配置入口应继续返回 EasyHarness `ModelConfig`。"""

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
        self.assertEqual(model.model, "openai/deepseek-v4-pro")
        self.assertEqual(model.api_key, "test-key")
        self.assertEqual(model.base_url, "https://example.com/v1")
        self.assertEqual(model.temperature, 0.01)
        self.assertEqual(model.top_p, 0.01)
        self.assertIsNone(model.seed)
        self.assertEqual(model.context_window_limit, 900_000)

    def test_default_agent_uses_official_conversation_manager(self) -> None:
        """默认 agent 应直接使用 EasyHarness 官方会话压缩管理器。"""

        with patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False):
            agent = build_default_agent(".")

        runtime = agent.__dict__["_runtime"]
        conversation_manager = runtime.__dict__["_conversation_manager"]

        self.assertIsInstance(
            conversation_manager,
            EventingSummarizingConversationManager,
        )
        self.assertEqual(conversation_manager.preserve_recent_messages, 6)


if __name__ == "__main__":
    unittest.main()
