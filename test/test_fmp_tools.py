"""FMP EasyHarness 工具最小回归测试。

该文件验证 `src/tool/fmp_tools.py` 是否真正形成最小可靠闭环：

1. `FmpClient` 的全部公开查询方法都被包装成工具；
2. 代表性工具会把显式参数和 `extra_params` 正确委托给底层 client；
3. 缺少 API Key、参数校验失败和 HTTP 失败都会通过 EasyHarness 工具失败语义暴露。
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

import requests
from pydantic import ValidationError

from src.ext.fmp import FmpClient
from src.tool.fmp_tools import FMP_TOOL_NAMES, build_fmp_tools


def _public_fmp_method_names() -> list[str]:
    """按定义顺序返回 `FmpClient` 的公开方法名。"""

    names: list[str] = []
    for name, value in FmpClient.__dict__.items():
        if name.startswith("_") or not callable(value):
            continue
        names.append(name)
    return names


def _find_tool(tool_name: str) -> object:
    """从默认 FMP 工具集合中找到目标工具。"""

    for item in build_fmp_tools():
        if getattr(item, "tool_name", "") == tool_name:
            return item
    raise AssertionError(f"未找到工具: {tool_name}")


async def _collect_stream_events(tool_obj: object, tool_input: dict[str, object]) -> list[object]:
    """收集一次 EasyHarness 工具事件流。"""

    events: list[object] = []
    async for event in tool_obj.stream(  # type: ignore[attr-defined]
        {"toolUseId": "tool-use-1", "input": tool_input},
        {},
    ):
        events.append(event)
    return events


class _FakeProfileClient:
    """用于验证 symbol 类工具委托行为的最小替身。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_profile(self, symbol: str, **params: object) -> list[dict[str, object]]:
        """记录调用参数并返回最小结果。"""

        self.calls.append((symbol, params))
        return [{"symbol": symbol, "params": params}]


class _FakeCalendarClient:
    """用于验证日期区间类工具委托行为的最小替身。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_ipos_calendar(
        self,
        *,
        from_date: str = "",
        to_date: str = "",
        **params: object,
    ) -> list[dict[str, object]]:
        """记录调用参数并返回最小结果。"""

        self.calls.append(
            {
                "from_date": from_date,
                "to_date": to_date,
                "params": params,
            }
        )
        return [
            {
                "from_date": from_date,
                "to_date": to_date,
                "params": params,
            }
        ]


class _FakeHistoricalPriceClient:
    """用于验证 symbol + 日期区间类工具委托行为的最小替身。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_historical_price_eod_full(
        self,
        symbol: str,
        *,
        from_date: str = "",
        to_date: str = "",
        **params: object,
    ) -> list[dict[str, object]]:
        """记录调用参数并返回最小结果。"""

        self.calls.append(
            {
                "symbol": symbol,
                "from_date": from_date,
                "to_date": to_date,
                "params": params,
            }
        )
        return [
            {
                "symbol": symbol,
                "from_date": from_date,
                "to_date": to_date,
                "params": params,
            }
        ]


class _FakeScreenerClient:
    """用于验证 company screener 工具委托行为的最小替身。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_company_screener(self, **params: object) -> list[dict[str, object]]:
        """记录调用参数并返回最小结果。"""

        self.calls.append(params)
        return [{"params": params}]


class _RaisingProfileClient:
    """用于模拟底层 HTTP 失败的最小替身。"""

    def get_profile(self, symbol: str, **params: object) -> list[dict[str, object]]:
        """始终抛出 HTTPError。"""

        del symbol, params
        raise requests.HTTPError("boom")


class FmpEasyHarnessToolTests(unittest.TestCase):
    """验证 FMP EasyHarness 工具的最小可靠边界。"""

    def test_build_fmp_tools_wraps_all_public_fmp_methods(self) -> None:
        """每个公开 `FmpClient` 方法都应有一一对应的工具。"""

        public_methods = _public_fmp_method_names()

        self.assertEqual(len(FMP_TOOL_NAMES), len(public_methods))
        self.assertEqual(
            FMP_TOOL_NAMES,
            tuple(f"fmp_{name}" for name in public_methods),
        )
        self.assertEqual(len(build_fmp_tools()), len(public_methods))

    def test_symbol_tool_delegates_symbol_and_extra_params(self) -> None:
        """symbol 类工具应把显式参数与附加参数正确委托给底层 client。"""

        fake_client = _FakeProfileClient()
        tool_obj = _find_tool("fmp_get_profile")

        with patch("src.tool.fmp_tools._create_client", return_value=fake_client):
            output = tool_obj(
                symbol="aapl",
                extra_params={"limit": 1, "symbol": "MSFT"},
            )

        self.assertEqual(fake_client.calls, [("aapl", {"limit": 1})])
        self.assertEqual(output.data["method_name"], "get_profile")
        self.assertEqual(output.data["request"]["symbol"], "aapl")
        self.assertEqual(output.data["request"]["extra_params"], {"limit": 1})
        self.assertIn("fmp_get_profile", output.preview)

    def test_date_range_tool_delegates_date_window_and_extra_params(self) -> None:
        """日期区间类工具应保留显式日期参数并透传附加字段。"""

        fake_client = _FakeCalendarClient()
        tool_obj = _find_tool("fmp_get_ipos_calendar")

        with patch("src.tool.fmp_tools._create_client", return_value=fake_client):
            output = tool_obj(
                from_date="2026-01-01",
                to_date="2026-01-31",
                extra_params={"page": 2, "from_date": "ignored"},
            )

        self.assertEqual(
            fake_client.calls,
            [
                {
                    "from_date": "2026-01-01",
                    "to_date": "2026-01-31",
                    "params": {"page": 2},
                }
            ],
        )
        self.assertEqual(output.data["request"]["extra_params"], {"page": 2})
        self.assertIn("返回 1 条记录", output.preview)

    def test_symbol_date_range_tool_delegates_symbol_window_and_extra_params(self) -> None:
        """symbol + 日期区间类工具应保留显式代码和时间窗口。"""

        fake_client = _FakeHistoricalPriceClient()
        tool_obj = _find_tool("fmp_get_historical_price_eod_full")

        with patch("src.tool.fmp_tools._create_client", return_value=fake_client):
            output = tool_obj(
                symbol="aapl",
                from_date="2025-01-01",
                to_date="2025-01-31",
                extra_params={"limit": 5, "symbol": "MSFT", "from_date": "ignored"},
            )

        self.assertEqual(
            fake_client.calls,
            [
                {
                    "symbol": "aapl",
                    "from_date": "2025-01-01",
                    "to_date": "2025-01-31",
                    "params": {"limit": 5},
                }
            ],
        )
        self.assertEqual(output.data["request"]["symbol"], "aapl")
        self.assertEqual(output.data["request"]["from_date"], "2025-01-01")
        self.assertEqual(output.data["request"]["to_date"], "2025-01-31")
        self.assertEqual(output.data["request"]["extra_params"], {"limit": 5})

    def test_extra_params_tool_delegates_company_screener_filters(self) -> None:
        """company screener 工具应保留结构化筛选参数。"""

        fake_client = _FakeScreenerClient()
        tool_obj = _find_tool("fmp_get_company_screener")

        with patch("src.tool.fmp_tools._create_client", return_value=fake_client):
            output = tool_obj(
                extra_params={
                    "sector": "Technology",
                    "marketCapMoreThan": 10000000000,
                }
            )

        self.assertEqual(
            fake_client.calls,
            [
                {
                    "sector": "Technology",
                    "marketCapMoreThan": 10000000000,
                }
            ],
        )
        self.assertEqual(
            output.data["request"]["extra_params"],
            {
                "sector": "Technology",
                "marketCapMoreThan": 10000000000,
            },
        )

    def test_stream_reports_missing_api_key_as_failed_tool_event(self) -> None:
        """缺少 FMP API Key 时，工具事件流必须显式失败。"""

        tool_obj = _find_tool("fmp_get_profile")

        with patch.dict("os.environ", {"FMP_API_KEY": ""}, clear=False):
            events = asyncio.run(_collect_stream_events(tool_obj, {"symbol": "AAPL"}))

        self.assertEqual(events[0]["easyharness_tool"]["status"], "started")
        self.assertEqual(events[1]["easyharness_tool"]["status"], "failed")
        self.assertIn("FMP API Key", events[1]["easyharness_tool"]["error"])
        self.assertEqual(events[2]["type"], "tool_result")
        self.assertEqual(events[2]["tool_result"]["status"], "error")

    def test_stream_reports_validation_failure_for_bad_extra_params(self) -> None:
        """参数校验失败时，工具事件流也必须显式失败。"""

        tool_obj = _find_tool("fmp_get_profile")
        original_json = ValidationError.json

        def compat_json(self: ValidationError, *args: object, **kwargs: object) -> str:
            """兼容 EasyHarness 当前对 `ensure_ascii` 的调用方式。"""

            kwargs.pop("ensure_ascii", None)
            return original_json(self, *args, **kwargs)

        with patch.object(ValidationError, "json", compat_json):
            events = asyncio.run(
                _collect_stream_events(
                    tool_obj,
                    {
                        "symbol": "AAPL",
                        "extra_params": "not-a-dict",
                    },
                )
            )

        self.assertEqual(events[0]["easyharness_tool"]["status"], "failed")
        self.assertIn("extra_params", events[0]["easyharness_tool"]["error"])
        self.assertEqual(events[1]["type"], "tool_result")
        self.assertEqual(events[1]["tool_result"]["status"], "error")

    def test_stream_reports_http_error_as_failed_tool_event(self) -> None:
        """底层 HTTP 失败时，工具事件流必须显式失败。"""

        tool_obj = _find_tool("fmp_get_profile")

        with patch("src.tool.fmp_tools._create_client", return_value=_RaisingProfileClient()):
            events = asyncio.run(_collect_stream_events(tool_obj, {"symbol": "AAPL"}))

        self.assertEqual(events[0]["easyharness_tool"]["status"], "started")
        self.assertEqual(events[1]["easyharness_tool"]["status"], "failed")
        self.assertIn("boom", events[1]["easyharness_tool"]["error"])
        self.assertEqual(events[2]["tool_result"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
