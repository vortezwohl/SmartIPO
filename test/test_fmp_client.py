"""FMP 客户端最小回归测试。

该文件聚焦验证 `src/ext/fmp.py` 的最小可靠闭环：环境变量解析、显式配置
优先级、统一 query 参数拼接、代表性 endpoint 路径映射，以及 HTTP 失败
不会被伪装成成功结果。
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import requests

from src.ext.fmp import FmpClient, create_fmp_client


class _FakeResponse:
    """用于伪造 `requests.Response` 的最小替身。"""

    def __init__(
        self,
        payload: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self._payload = payload if payload is not None else []
        self._error = error

    def raise_for_status(self) -> None:
        """按测试需要模拟 HTTP 成功或失败。"""
        if self._error is not None:
            raise self._error

    def json(self) -> object:
        """返回预设的 JSON 结果。"""
        return self._payload


class _FakeSession:
    """用于记录请求调用明细的最小 session 替身。"""

    def __init__(self, response: _FakeResponse | None = None) -> None:
        self._response = response or _FakeResponse()
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        *,
        params: dict[str, object],
        timeout: int,
    ) -> _FakeResponse:
        """记录调用参数并返回预设响应。"""
        self.calls.append(
            {
                "url": url,
                "params": params,
                "timeout": timeout,
            }
        )
        return self._response


class FmpClientTests(unittest.TestCase):
    """验证 FMP 客户端的核心边界行为。"""

    def test_request_fails_fast_without_api_key(self) -> None:
        """缺少 FMP API Key 时应在发请求前失败。"""

        session = _FakeSession()
        with patch.dict(os.environ, {"FMP_API_KEY": "", "FMP_API_BASE": ""}, clear=False):
            client = create_fmp_client(session=session)
            with self.assertRaisesRegex(RuntimeError, "FMP API Key"):
                client.get_profile("AAPL")

        self.assertEqual(session.calls, [])

    def test_explicit_config_overrides_environment_values(self) -> None:
        """显式传入的 key 和 base 必须覆盖环境变量。"""

        session = _FakeSession()
        with patch.dict(
            os.environ,
            {
                "FMP_API_KEY": "env-key",
                "FMP_API_BASE": "https://env.example.com/stable",
            },
            clear=False,
        ):
            client = create_fmp_client(
                api_key="explicit-key",
                api_base="https://explicit.example.com/stable/",
                session=session,
            )
            client.get_profile("aapl")

        self.assertEqual(len(session.calls), 1)
        call = session.calls[0]
        self.assertEqual(
            call["url"],
            "https://explicit.example.com/stable/profile",
        )
        self.assertEqual(call["params"], {"apikey": "explicit-key", "symbol": "AAPL"})

    def test_get_builds_query_and_filters_empty_values(self) -> None:
        """统一请求层应补齐 apikey，并过滤空字符串和 None。"""

        session = _FakeSession()
        client = FmpClient(api_key="test-key", session=session)

        client.get_ipos_calendar(
            from_date="2026-01-01",
            to_date="2026-01-31",
            page=0,
            limit=None,
            exchange="",
        )

        self.assertEqual(len(session.calls), 1)
        call = session.calls[0]
        self.assertEqual(
            call["url"],
            "https://financialmodelingprep.com/stable/ipos-calendar",
        )
        self.assertEqual(
            call["params"],
            {
                "apikey": "test-key",
                "from": "2026-01-01",
                "to": "2026-01-31",
                "page": 0,
            },
        )

    def test_representative_endpoint_paths_and_params_match_expectations(self) -> None:
        """代表性 IPO、财报和估值接口应映射到正确路径。"""

        session = _FakeSession()
        client = FmpClient(api_key="test-key", session=session)

        client.get_ipo_prospectus(from_date="2026-02-01", to_date="2026-02-28")
        client.get_income_statement("MSFT", period="annual", limit=3)
        client.get_key_metrics("NVDA", period="quarter", limit=2)

        self.assertEqual(len(session.calls), 3)
        self.assertEqual(
            session.calls[0]["url"],
            "https://financialmodelingprep.com/stable/ipos-prospectus",
        )
        self.assertEqual(
            session.calls[0]["params"],
            {
                "apikey": "test-key",
                "from": "2026-02-01",
                "to": "2026-02-28",
            },
        )
        self.assertEqual(
            session.calls[1]["url"],
            "https://financialmodelingprep.com/stable/income-statement",
        )
        self.assertEqual(
            session.calls[1]["params"],
            {
                "apikey": "test-key",
                "symbol": "MSFT",
                "period": "annual",
                "limit": 3,
            },
        )
        self.assertEqual(
            session.calls[2]["url"],
            "https://financialmodelingprep.com/stable/key-metrics",
        )
        self.assertEqual(
            session.calls[2]["params"],
            {
                "apikey": "test-key",
                "symbol": "NVDA",
                "period": "quarter",
                "limit": 2,
            },
        )

    def test_market_data_endpoints_map_expected_paths_and_params(self) -> None:
        """新增市场数据接口应映射到正确路径并保留查询参数。"""

        session = _FakeSession()
        client = FmpClient(api_key="test-key", session=session)

        client.get_historical_price_eod_full(
            "aapl",
            from_date="2025-01-01",
            to_date="2025-01-31",
            limit=10,
        )
        client.get_historical_market_cap(
            "msft",
            from_date="2024-06-01",
            to_date="2024-06-30",
        )
        client.get_company_screener(
            marketCapMoreThan=10000000000,
            sector="Technology",
            isEtf=False,
        )

        self.assertEqual(len(session.calls), 3)
        self.assertEqual(
            session.calls[0]["url"],
            "https://financialmodelingprep.com/stable/historical-price-eod/full",
        )
        self.assertEqual(
            session.calls[0]["params"],
            {
                "apikey": "test-key",
                "symbol": "AAPL",
                "from": "2025-01-01",
                "to": "2025-01-31",
                "limit": 10,
            },
        )
        self.assertEqual(
            session.calls[1]["url"],
            "https://financialmodelingprep.com/stable/historical-market-capitalization",
        )
        self.assertEqual(
            session.calls[1]["params"],
            {
                "apikey": "test-key",
                "symbol": "MSFT",
                "from": "2024-06-01",
                "to": "2024-06-30",
            },
        )
        self.assertEqual(
            session.calls[2]["url"],
            "https://financialmodelingprep.com/stable/company-screener",
        )
        self.assertEqual(
            session.calls[2]["params"],
            {
                "apikey": "test-key",
                "marketCapMoreThan": 10000000000,
                "sector": "Technology",
                "isEtf": False,
            },
        )

    def test_http_errors_bubble_up_without_being_hidden(self) -> None:
        """FMP 非 2xx 响应必须继续向上暴露异常。"""

        error = requests.HTTPError("boom")
        session = _FakeSession(response=_FakeResponse(error=error))
        client = FmpClient(api_key="test-key", session=session)

        with self.assertRaises(requests.HTTPError):
            client.get_quote("TSLA")

        self.assertEqual(len(session.calls), 1)


if __name__ == "__main__":
    unittest.main()
