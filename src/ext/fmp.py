"""FMP 美股 IPO 与估值研究客户端。

该文件负责对接 Financial Modeling Prep 的 stable API，并为项目内的
“是否参与某家美股 IPO”与“公司估值研究”两个场景提供最小可靠的数据
接入层。当前实现重点放在：

1. 统一解析 FMP API Key、Base URL 和超时配置；
2. 统一处理 GET 请求、query 参数清洗和 HTTP 错误透传；
3. 提供围绕 IPO 决策、财报底表、估值指标和研究辅助数据的薄封装方法；
4. 保持返回值尽量贴近 FMP 原始 JSON，避免在客户端层过早引入复杂建模。

调用方默认通过 `dotenv` 加载后的环境变量提供鉴权信息；若显式传入参数，
则显式值优先。
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
import requests

load_dotenv()


DEFAULT_FMP_API_BASE = "https://financialmodelingprep.com/stable"
DEFAULT_FMP_TIMEOUT_SECONDS = 30


class FmpClient:
    """提供 FMP stable API 的最小研究客户端。

    该客户端只封装美股 IPO 决策与估值研究所需的核心接口，不承担
    评分、排序、缓存和结论生成职责。所有公开方法都共享同一个
    `requests.Session` 和统一的 `_get()` 请求边界。

    Args:
        api_key: FMP API Key。为空时会从环境变量 `FMP_API_KEY` 读取。
        api_base: FMP stable API 基础地址。为空时会优先读取
            `FMP_API_BASE`，否则回退到默认 stable base。
        timeout: HTTP 请求超时时间，单位为秒。
        session: 可选的 `requests.Session`。测试时可注入 fake session。
    """

    def __init__(
        self,
        api_key: str = "",
        api_base: str = "",
        timeout: int = DEFAULT_FMP_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
    ) -> None:
        """初始化 FMP 客户端。"""
        self._api_key = api_key.strip() or self._resolve_api_key()
        self._api_base = (api_base.strip() or self._resolve_api_base()).rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()

    def get_ipos_calendar(
        self,
        *,
        from_date: str = "",
        to_date: str = "",
        **params: Any,
    ) -> Any:
        """获取美股 IPO 日历。

        Args:
            from_date: 开始日期，最终会映射到 FMP 的 `from` query 参数。
            to_date: 结束日期，最终会映射到 FMP 的 `to` query 参数。
            **params: 其他需要透传给 FMP 的查询参数。

        Returns:
            FMP 返回的 IPO 日历原始 JSON。
        """
        return self._get("ipos-calendar", **self._with_date_range(from_date, to_date, params))

    def get_ipo_disclosures(
        self,
        *,
        from_date: str = "",
        to_date: str = "",
        **params: Any,
    ) -> Any:
        """获取美股 IPO 披露列表。"""
        return self._get("ipos-disclosure", **self._with_date_range(from_date, to_date, params))

    def get_ipo_prospectus(
        self,
        *,
        from_date: str = "",
        to_date: str = "",
        **params: Any,
    ) -> Any:
        """获取美股 IPO 招股书列表。"""
        return self._get("ipos-prospectus", **self._with_date_range(from_date, to_date, params))

    def get_sec_filings_by_symbol(self, symbol: str, **params: Any) -> Any:
        """按股票代码查询 SEC filings。"""
        return self._get_symbol_resource("sec-filings-search/symbol", symbol, **params)

    def get_latest_sec_filings(
        self,
        *,
        from_date: str = "",
        to_date: str = "",
        **params: Any,
    ) -> Any:
        """获取最新 SEC filings 列表。"""
        return self._get(
            "sec-filings-financials",
            **self._with_date_range(from_date, to_date, params),
        )

    def get_financial_report_json(
        self,
        symbol: str,
        *,
        year: int | None = None,
        period: str = "FY",
        **params: Any,
    ) -> Any:
        """获取 10-K/10-Q JSON 财报明细。

        Args:
            symbol: 股票代码。
            year: 财年。为空时由 FMP 自行决定默认值。
            period: 财报周期，通常使用 `FY`、`Q1`、`Q2`、`Q3`。
            **params: 其他需要透传给 FMP 的查询参数。

        Returns:
            FMP 返回的财报 JSON 原始结果。
        """
        return self._get_symbol_resource(
            "financial-reports-json",
            symbol,
            year=year,
            period=period,
            **params,
        )

    def get_profile(self, symbol: str, **params: Any) -> Any:
        """获取公司概况。"""
        return self._get_symbol_resource("profile", symbol, **params)

    def get_quote(self, symbol: str, **params: Any) -> Any:
        """获取最新报价。"""
        return self._get_symbol_resource("quote", symbol, **params)

    def get_shares_float(self, symbol: str, **params: Any) -> Any:
        """获取流通股本信息。"""
        return self._get_symbol_resource("shares-float", symbol, **params)

    def get_historical_price_eod_light(self, symbol: str, **params: Any) -> Any:
        """获取轻量化 EOD 历史价格。"""
        return self._get_symbol_resource("historical-price-eod/light", symbol, **params)

    def get_historical_price_eod_full(
        self,
        symbol: str,
        *,
        from_date: str = "",
        to_date: str = "",
        **params: Any,
    ) -> Any:
        """获取完整 EOD 历史价格。

        Args:
            symbol: 股票代码。
            from_date: 开始日期，最终会映射到 FMP 的 `from` query 参数。
            to_date: 结束日期，最终会映射到 FMP 的 `to` query 参数。
            **params: 其他需要透传给 FMP 的查询参数。

        Returns:
            FMP 返回的完整 EOD 历史价格原始 JSON。
        """
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol 不能为空。")
        return self._get(
            "historical-price-eod/full",
            symbol=normalized_symbol,
            **self._with_date_range(from_date, to_date, params),
        )

    def get_historical_market_cap(
        self,
        symbol: str,
        *,
        from_date: str = "",
        to_date: str = "",
        **params: Any,
    ) -> Any:
        """获取历史市值序列。

        Args:
            symbol: 股票代码。
            from_date: 开始日期，最终会映射到 FMP 的 `from` query 参数。
            to_date: 结束日期，最终会映射到 FMP 的 `to` query 参数。
            **params: 其他需要透传给 FMP 的查询参数。

        Returns:
            FMP 返回的历史市值原始 JSON。
        """
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol 不能为空。")
        return self._get(
            "historical-market-capitalization",
            symbol=normalized_symbol,
            **self._with_date_range(from_date, to_date, params),
        )

    def get_company_screener(self, **params: Any) -> Any:
        """获取公司筛选结果。"""
        return self._get("company-screener", **params)

    def get_income_statement(self, symbol: str, **params: Any) -> Any:
        """获取利润表。"""
        return self._get_symbol_resource("income-statement", symbol, **params)

    def get_balance_sheet_statement(self, symbol: str, **params: Any) -> Any:
        """获取资产负债表。"""
        return self._get_symbol_resource("balance-sheet-statement", symbol, **params)

    def get_cashflow_statement(self, symbol: str, **params: Any) -> Any:
        """获取现金流量表。"""
        return self._get_symbol_resource("cash-flow-statement", symbol, **params)

    def get_as_reported_financial_statements(self, symbol: str, **params: Any) -> Any:
        """获取 as reported 财报。"""
        return self._get_symbol_resource("as-reported-financial-statements", symbol, **params)

    def get_financial_statement_growth(self, symbol: str, **params: Any) -> Any:
        """获取财务增长数据。"""
        return self._get_symbol_resource("financial-statement-growth", symbol, **params)

    def get_latest_financial_statements(self, symbol: str, **params: Any) -> Any:
        """获取最新财务报表。"""
        return self._get_symbol_resource("latest-financial-statements", symbol, **params)

    def get_key_metrics(self, symbol: str, **params: Any) -> Any:
        """获取关键指标。"""
        return self._get_symbol_resource("key-metrics", symbol, **params)

    def get_key_metrics_ttm(self, symbol: str, **params: Any) -> Any:
        """获取 TTM 关键指标。"""
        return self._get_symbol_resource("key-metrics-ttm", symbol, **params)

    def get_financial_ratios(self, symbol: str, **params: Any) -> Any:
        """获取财务比率。"""
        return self._get_symbol_resource("ratios", symbol, **params)

    def get_financial_ratios_ttm(self, symbol: str, **params: Any) -> Any:
        """获取 TTM 财务比率。"""
        return self._get_symbol_resource("ratios-ttm", symbol, **params)

    def get_enterprise_values(self, symbol: str, **params: Any) -> Any:
        """获取企业价值相关数据。"""
        return self._get_symbol_resource("enterprise-values", symbol, **params)

    def get_owner_earnings(self, symbol: str, **params: Any) -> Any:
        """获取 owner earnings 数据。"""
        return self._get_symbol_resource("owner-earnings", symbol, **params)

    def get_dcf_advanced(self, symbol: str, **params: Any) -> Any:
        """获取 DCF 估值结果。"""
        return self._get_symbol_resource("discounted-cash-flow", symbol, **params)

    def get_levered_dcf(self, symbol: str, **params: Any) -> Any:
        """获取 levered DCF 估值结果。"""
        return self._get_symbol_resource("levered-discounted-cash-flow", symbol, **params)

    def get_custom_dcf_advanced(self, symbol: str, **params: Any) -> Any:
        """获取 custom DCF 估值结果。"""
        return self._get_symbol_resource("custom-discounted-cash-flow", symbol, **params)

    def get_financial_estimates(self, symbol: str, **params: Any) -> Any:
        """获取卖方一致预期。"""
        return self._get_symbol_resource("financial-estimates", symbol, **params)

    def get_price_target_consensus(self, symbol: str, **params: Any) -> Any:
        """获取目标价一致预期。"""
        return self._get_symbol_resource("price-target-consensus", symbol, **params)

    def get_stock_peers(self, symbol: str, **params: Any) -> Any:
        """获取可比公司列表。"""
        return self._get_symbol_resource("stock-peers", symbol, **params)

    def get_company_executives(self, symbol: str, **params: Any) -> Any:
        """获取管理层信息。"""
        return self._get_symbol_resource("company-executives", symbol, **params)

    def get_executive_compensation(self, symbol: str, **params: Any) -> Any:
        """获取高管薪酬信息。"""
        return self._get_symbol_resource("governance-executive-compensation", symbol, **params)

    def get_earnings_transcripts(
        self,
        symbol: str,
        *,
        year: int | None = None,
        quarter: int | None = None,
        **params: Any,
    ) -> Any:
        """获取业绩会纪要。"""
        return self._get_symbol_resource(
            "earning-call-transcript",
            symbol,
            year=year,
            quarter=quarter,
            **params,
        )

    def get_positions_summary(self, symbol: str, **params: Any) -> Any:
        """获取机构持仓摘要。"""
        return self._get_symbol_resource(
            "institutional-ownership/symbol-positions-summary",
            symbol,
            **params,
        )

    def get_latest_insider_trades(self, **params: Any) -> Any:
        """获取最新内部人交易列表。"""
        return self._get("insider-trading/latest", **params)

    def search_insider_trades(self, **params: Any) -> Any:
        """按条件搜索内部人交易。"""
        return self._get("insider-trading/search", **params)

    def get_insider_trade_statistics(self, symbol: str, **params: Any) -> Any:
        """获取内部人交易统计。"""
        return self._get_symbol_resource("insider-trading/statistics", symbol, **params)

    def get_treasury_rates(self, **params: Any) -> Any:
        """获取美债利率。"""
        return self._get("treasury-rates", **params)

    def get_market_risk_premium(self, **params: Any) -> Any:
        """获取市场风险溢价。"""
        return self._get("market-risk-premium", **params)

    def get_economic_indicators(self, **params: Any) -> Any:
        """获取宏观经济指标。"""
        return self._get("economic-indicators", **params)

    def _get_symbol_resource(self, path: str, symbol: str, **params: Any) -> Any:
        """以统一方式请求股票代码维度的 FMP 资源。

        Args:
            path: FMP stable API 路径，不包含 base URL。
            symbol: 股票代码。
            **params: 其他需要透传给 FMP 的查询参数。

        Returns:
            FMP 返回的原始 JSON 结果。
        """
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol 不能为空。")
        return self._get(path, symbol=normalized_symbol, **params)

    def _get(self, path: str, **params: Any) -> Any:
        """统一执行一次 FMP GET 请求。

        Args:
            path: FMP stable API 路径，不包含 base URL。
            **params: 业务查询参数。

        Returns:
            FMP 返回的原始 JSON 结果。

        Raises:
            RuntimeError: 当未找到 API Key 时抛出。
            requests.HTTPError: 当 FMP 返回非 2xx 状态时抛出。
        """
        if not self._api_key:
            raise RuntimeError("未找到 FMP API Key，请显式传入或配置 FMP_API_KEY。")
        normalized_path = path.strip().lstrip("/")
        url = f"{self._api_base}/{normalized_path}"
        response = self._session.get(
            url,
            params=self._build_query_params(params),
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()

    def _build_query_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """构造 FMP 查询参数。

        Args:
            params: 调用方传入的业务参数字典。

        Returns:
            过滤空值后、并自动补齐 `apikey` 的 query 参数字典。
        """
        query_params = {"apikey": self._api_key}
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            query_params[key] = value
        return query_params

    @staticmethod
    def _with_date_range(
        from_date: str,
        to_date: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """把 Python 友好的日期参数名映射成 FMP query 字段。"""
        merged = dict(params)
        if from_date.strip():
            merged["from"] = from_date.strip()
        if to_date.strip():
            merged["to"] = to_date.strip()
        return merged

    @staticmethod
    def _resolve_api_key() -> str:
        """按项目约定解析 FMP API Key。"""
        return os.getenv("FMP_API_KEY", "").strip()

    @staticmethod
    def _resolve_api_base() -> str:
        """按项目约定解析 FMP API Base。"""
        return os.getenv("FMP_API_BASE", DEFAULT_FMP_API_BASE).strip()


def create_fmp_client(
    api_key: str = "",
    api_base: str = "",
    timeout: int = DEFAULT_FMP_TIMEOUT_SECONDS,
    session: requests.Session | None = None,
) -> FmpClient:
    """创建一个最小可用的 FMP 客户端。

    Args:
        api_key: 可选的显式 API Key。为空时回退到环境变量。
        api_base: 可选的显式 API Base。为空时回退到环境变量或默认值。
        timeout: HTTP 请求超时时间，单位为秒。
        session: 可选的 `requests.Session`，测试场景可注入 fake session。

    Returns:
        一个可直接用于美股 IPO 与估值研究的 `FmpClient`。
    """
    return FmpClient(
        api_key=api_key,
        api_base=api_base,
        timeout=timeout,
        session=session,
    )
