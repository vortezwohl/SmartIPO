"""EasyHarness 工具与默认装配测试。

该文件验证 SmartIPO 默认工具集合已经切换为 EasyHarness 公共工具合同：
官方 fileglide toolset 提供文件能力，FMP 业务工具使用 `easyharness.tool` 声明。
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from easyharness import Agent, ModelConfig
from src.ext.fmp import FmpClient
from src.agent import (
    DEFAULT_BASIC_TOOL_NAMES,
    DEFAULT_BUSINESS_TOOL_NAMES,
    DEFAULT_FILEGLIDE_TOOL_NAMES,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_WORKBENCH_TOOL_NAMES,
    build_default_model_config,
    build_default_agent,
    build_default_tools,
)
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
    """判断项目自有工具描述是否包含全部必需章节。"""

    return all(section in description for section in _PROJECT_TOOL_METADATA_REQUIRED_SECTIONS)


class EasyHarnessToolingTests(unittest.TestCase):
    """验证 EasyHarness 工具体系与默认 composition 层。"""

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
        """默认工具名应使用官方 fileglide 与业务工具公开名。"""

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
        self.assertIn("美股 IPO 研究", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("中签率", DEFAULT_SYSTEM_PROMPT)
        self.assertNotIn("text.read", DEFAULT_SYSTEM_PROMPT)

    def test_build_default_tools_returns_public_tool_objects(self) -> None:
        """默认工具对象集合应可直接交给 EasyHarness Agent 使用。"""

        tools = build_default_tools(".")
        names = {getattr(item, "tool_name", "") for item in tools}

        self.assertIn("fileglide_read_text", names)
        self.assertIn("fileglide_search_text", names)
        self.assertIn("calculator", names)
        self.assertIn("now", names)
        self.assertIn("web_fetch_page", names)
        self.assertIn("fmp_get_profile", names)

    def test_runtime_tool_specs_expose_metadata_sections(self) -> None:
        """项目自有工具在 runtime 层必须暴露完整元数据章节。"""

        specs = self._tool_specs_by_name()

        for tool_name in _PROJECT_OWNED_TOOL_NAMES:
            description = str(specs[tool_name]["description"])
            self.assertTrue(
                _has_required_metadata_sections(description),
                msg=f"{tool_name} 缺少必需的元数据章节。",
            )

        self.assertTrue(str(specs["fileglide_read_text"]["description"]).strip())

    def test_key_fmp_runtime_metadata_distinguishes_neighboring_tools(self) -> None:
        """关键 FMP 工具必须在 runtime 描述中体现边界差异。"""

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
                msg=f"{tool_name} 仍然保留旧的模板化 when_to_use。",
            )

        quote_description = str(specs["fmp_get_quote"]["description"])
        self.assertIn("最新价格快照", quote_description)
        self.assertIn("不适合分析历史区间走势", quote_description)

        historical_price_description = str(specs["fmp_get_historical_price_eod_full"]["description"])
        self.assertIn("完整历史价格时间序列", historical_price_description)
        self.assertIn("上市后走势", historical_price_description)

        market_cap_description = str(specs["fmp_get_historical_market_cap"]["description"])
        self.assertIn("历史估值轨迹", market_cap_description)
        self.assertIn("历史市值时间序列", market_cap_description)

        peers_description = str(specs["fmp_get_stock_peers"]["description"])
        self.assertIn("FMP 内建可比公司列表", peers_description)
        self.assertIn("company screener", peers_description)

    def test_company_screener_runtime_metadata_includes_filter_examples(self) -> None:
        """company screener 工具必须提供高频筛选参数示例。"""

        specs = self._tool_specs_by_name()
        screener_description = str(specs["fmp_get_company_screener"]["description"])
        screener_schema = specs["fmp_get_company_screener"]["inputSchema"]["json"]
        extra_params_description = str(screener_schema["properties"]["extra_params"]["description"])

        for expected in ("sector", "industry", "exchange", "marketCapMoreThan"):
            self.assertIn(expected, screener_description)
            self.assertIn(expected, extra_params_description)

    def test_project_owned_runtime_metadata_uses_chinese_content(self) -> None:
        """项目自有工具文案应保持中文研究语境。"""

        specs = self._tool_specs_by_name()

        self.assertIn("计算或化简", str(specs["calculator"]["description"]))
        self.assertIn("当前本地日期时间", str(specs["now"]["description"]))
        self.assertIn("抓取单个网页", str(specs["web_fetch_page"]["description"]))

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
