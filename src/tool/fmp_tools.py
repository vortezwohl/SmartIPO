"""FMP EasyHarness 工具包装层。

该文件负责把 `src.ext.fmp.FmpClient` 的公开查询方法暴露为标准 EasyHarness
工具。工具层只做三件事：

1. 维持稳定的工具名、参数合同和用途描述；
2. 复用底层 `FmpClient` 处理 HTTP、鉴权和 query 参数清洗；
3. 为模型与 TUI 统一返回 `ToolOutput`，但不追加业务结论。
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import json
from typing import Any

from easyharness import ToolOutput, tool

from src.ext.fmp import FmpClient, create_fmp_client

_COMMON_FAILURES = (
    "FMP_API_KEY 未配置，导致底层客户端无法发起请求。",
    "输入参数格式不合法，导致工具 schema 校验失败。",
    "FMP 返回非 2xx 响应或网络调用异常。",
)
_DETAIL_TEXT_LIMIT = 4000

_SYMBOL_PARAMETER_DESCRIPTION = (
    "美股股票代码，例如 AAPL、MSFT、NVDA；系统会在调用前自动标准化为大写。"
)
_FROM_DATE_PARAMETER_DESCRIPTION = (
    "开始日期，格式为 YYYY-MM-DD；底层会映射到 FMP 的 `from` 参数，留空时使用 FMP 默认逻辑。"
)
_TO_DATE_PARAMETER_DESCRIPTION = (
    "结束日期，格式为 YYYY-MM-DD；底层会映射到 FMP 的 `to` 参数，留空时使用 FMP 默认逻辑。"
)
_YEAR_PARAMETER_DESCRIPTION = (
    "可选年份或财年；留空时使用 FMP 默认逻辑。若 `extra_params` 中也传入 `year`，以显式参数为准。"
)
_PERIOD_PARAMETER_DESCRIPTION = (
    "财报周期，例如 FY、Q1、Q2、Q3；若 `extra_params` 中也传入 `period`，以显式参数为准。"
)
_QUARTER_PARAMETER_DESCRIPTION = (
    "可选季度，通常为 1 到 4；若 `extra_params` 中也传入 `quarter`，以显式参数为准。"
)


@dataclass(slots=True, frozen=True)
class _FmpMetadataTemplate:
    """描述一类 FMP 工具共享的元数据模板。"""

    when_to_use: str
    returns: str
    extra_params: str


@dataclass(slots=True, frozen=True)
class _FmpMetadataProfile:
    """描述单个 FMP 工具的元数据来源。"""

    category: str
    purpose: str | None = None
    when_to_use: str | None = None
    returns: str | None = None
    extra_params: str | None = None


@dataclass(slots=True, frozen=True)
class _FmpToolSpec:
    """描述一个 FMP 方法到 EasyHarness 工具的映射关系。"""

    method_name: str
    tool_name: str
    purpose: str
    when_to_use: str
    returns_description: str
    extra_params_description: str
    family: str


_FMP_METADATA_TEMPLATES = {
    "ipo_window": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要按日期窗口查看 IPO 排期、披露节奏或 prospectus 列表时使用；"
            "适合观察发行窗口与事件时间线，不适合读取单家公司深度财务细节。"
        ),
        returns=(
            "返回 IPO 相关事件列表；常见字段会随 endpoint 不同包含 symbol、companyName、date、exchange、priceRange 等。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；常见字段包括 `page`、`limit` 或底层支持的其他筛选字段。"
        ),
    ),
    "sec_filings": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要 SEC filings 列表、最近披露或按股票代码回查申报材料时使用；"
            "适合定位一级披露入口，不适合直接替代财报底表分析。"
        ),
        returns=(
            "返回 SEC filings 记录列表；常见字段包括 symbol、filingDate、acceptedDate、formType、finalLink。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；常见字段包括 `page`、`limit`、`from`、`to`。"
        ),
    ),
    "company_snapshot": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要单家公司当前快照信息时使用；适合拿公司概况、最新价格或流通股本，"
            "不适合做历史区间走势与时间序列分析。"
        ),
        returns=(
            "返回单公司快照列表，通常只有 1 条记录；关键字段会随 endpoint 不同包含 companyName、price、marketCap、sharesFloat 等。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；大多数场景通常不需要，仅在底层 endpoint 支持额外过滤字段时传入。"
        ),
    ),
    "historical_series": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要历史时间序列时使用；适合做上市后走势、波动、成交量或估值区间复盘，"
            "不适合只看当前价格快照。"
        ),
        returns=(
            "返回按日期排列的历史时间序列列表；关键字段会随 endpoint 不同包含 date、close、volume、marketCap 等。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；常见字段包括 `limit`，显式日期参数仍优先于同名透传字段。"
        ),
    ),
    "company_screener": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要按行业、市值、交易所或流动性自定义筛选可比公司样本时使用；"
            "适合先构建研究样本池，不适合替代单家公司详细财报读取。"
        ),
        returns=(
            "返回满足筛选条件的公司列表；常见字段包括 symbol、companyName、sector、industry、marketCap、price。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；常见字段包括 `sector`、`industry`、`exchange`、"
            "`marketCapMoreThan`、`marketCapLowerThan`、`priceMoreThan`、`volumeMoreThan`。"
        ),
    ),
    "financial_statements": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要利润表、资产负债表、现金流量表、as reported 财报或增长底表时使用；"
            "适合估值建模和财务质量拆解。"
        ),
        returns=(
            "返回财务报表或报表记录列表；常见字段包括 date、period、revenue、netIncome、totalAssets、operatingCashFlow。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；常见字段包括 `period`、`limit`、`page`，显式参数优先于同名透传字段。"
        ),
    ),
    "metrics_and_ratios": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要经营质量、盈利能力、资本结构或倍数口径指标时使用；"
            "适合在财报底表之上做横向对比和估值框架搭建。"
        ),
        returns=(
            "返回指标或比率记录列表；常见字段包括 peRatio、pbRatio、roe、netDebt、enterpriseValue、ownerEarnings。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；常见字段包括 `period`、`limit`，显式参数优先于同名透传字段。"
        ),
    ),
    "valuation_outputs": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要绝对估值结果或卖方一致预期时使用；适合拿 DCF 结果、收入/EPS 预期或目标价区间，"
            "不适合替代底表和业务分析本身。"
        ),
        returns=(
            "返回估值结果或一致预期记录；关键字段会随 endpoint 不同包含 dcf、stockPrice、epsAvg、revenueAvg、targetHigh、targetLow。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；常见字段包括 `limit`、`period` 或底层 endpoint 支持的其他参数。"
        ),
    ),
    "comparables": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要以单个股票代码为起点获取 FMP 内建可比公司列表时使用；"
            "若需要按行业、市值或交易所自定义构建样本池，优先使用 company screener。"
        ),
        returns=(
            "返回单家公司对应的 FMP 内建可比公司列表，通常以股票代码序列或简短对象列表表达。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；大多数场景通常不需要，仅在底层 endpoint 支持附加字段时传入。"
        ),
    ),
    "governance_and_ownership": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要查看管理层、薪酬或机构持仓摘要时使用；"
            "适合补充治理结构与持仓背景，不适合替代价格或财务分析。"
        ),
        returns=(
            "返回治理或持仓记录列表；常见字段包括 name、title、pay、investorName、sharesNumber 等。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；常见字段包括 `limit`，具体支持范围以底层 endpoint 为准。"
        ),
    ),
    "transcripts": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要阅读业绩会纪要、管理层表述或季度问答原文时使用；"
            "适合补充定性信息，不适合替代结构化财务数据。"
        ),
        returns=(
            "返回业绩会纪要记录列表或文本内容；常见字段包括 symbol、year、quarter、date、content。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；常见字段包括 `limit`，显式 `year` 与 `quarter` 参数优先于同名透传字段。"
        ),
    ),
    "insiders": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要观察内部人最新交易、条件搜索或统计口径时使用；"
            "适合辅助判断交易行为与情绪，不适合直接推出投资结论。"
        ),
        returns=(
            "返回内部人交易记录或统计结果；常见字段包括 filingDate、transactionDate、transactionType、securitiesTransacted。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；常见字段包括 `from`、`to`、`reportingCik`、`transactionType`、`page`、`limit`。"
        ),
    ),
    "macro": _FmpMetadataTemplate(
        when_to_use=(
            "当任务需要贴现参数或宏观背景变量时使用；"
            "适合补充美债利率、市场风险溢价和宏观指标，不适合替代公司基本面分析。"
        ),
        returns=(
            "返回宏观或市场参数记录列表；常见字段包括 date、value、year、month，具体字段随指标而变。"
        ),
        extra_params=(
            "额外 FMP 查询参数 JSON 对象；常见字段包括 `from`、`to`、`limit`、`name`。"
        ),
    ),
}

_FMP_METADATA_PROFILES = {
    "get_ipos_calendar": _FmpMetadataProfile(category="ipo_window"),
    "get_ipo_disclosures": _FmpMetadataProfile(category="ipo_window"),
    "get_ipo_prospectus": _FmpMetadataProfile(category="ipo_window"),
    "get_sec_filings_by_symbol": _FmpMetadataProfile(category="sec_filings"),
    "get_latest_sec_filings": _FmpMetadataProfile(category="sec_filings"),
    "get_financial_report_json": _FmpMetadataProfile(category="financial_statements"),
    "get_profile": _FmpMetadataProfile(
        category="company_snapshot",
        when_to_use=(
            "当任务需要单家公司静态概况时使用；适合查看公司名称、行业、国家、交易所、员工数等基础画像，"
            "不适合替代价格快照或历史走势分析。"
        ),
        returns=(
            "返回单公司概况列表，通常只有 1 条记录；常见字段包括 symbol、companyName、sector、industry、country、description。"
        ),
    ),
    "get_quote": _FmpMetadataProfile(
        category="company_snapshot",
        when_to_use=(
            "当任务只需要最新价格快照时使用；适合读取当前 price、marketCap、volume、涨跌幅，"
            "不适合分析历史区间走势或长期估值轨迹。"
        ),
        returns=(
            "返回最新价格快照列表，通常只有 1 条记录；常见字段包括 symbol、price、marketCap、volume、changesPercentage。"
        ),
    ),
    "get_shares_float": _FmpMetadataProfile(category="company_snapshot"),
    "get_historical_price_eod_light": _FmpMetadataProfile(
        category="historical_series",
        when_to_use=(
            "当任务需要较轻量的历史收盘价序列时使用；适合快速回看区间表现，"
            "若需要更完整的 OHLC 或成交量字段，优先使用完整历史价格工具。"
        ),
        returns=(
            "返回轻量历史价格时间序列列表；常见字段包括 date、close、changePercent。"
        ),
    ),
    "get_historical_price_eod_full": _FmpMetadataProfile(
        category="historical_series",
        when_to_use=(
            "当任务需要完整历史价格时间序列时使用；适合做上市后走势、波动、成交量和区间复盘，"
            "是历史行情分析的首选，不适合只看当前价格。"
        ),
        returns=(
            "返回完整历史价格时间序列列表；常见字段包括 date、open、high、low、close、volume、changePercent。"
        ),
    ),
    "get_historical_market_cap": _FmpMetadataProfile(
        category="historical_series",
        when_to_use=(
            "当任务需要观察历史估值轨迹时使用；适合把股价走势和市值变化放到同一时间轴复盘，"
            "不适合替代当前价格快照。"
        ),
        returns=(
            "返回历史市值时间序列列表；常见字段包括 date、marketCap。"
        ),
    ),
    "get_company_screener": _FmpMetadataProfile(category="company_screener"),
    "get_income_statement": _FmpMetadataProfile(category="financial_statements"),
    "get_balance_sheet_statement": _FmpMetadataProfile(category="financial_statements"),
    "get_cashflow_statement": _FmpMetadataProfile(category="financial_statements"),
    "get_as_reported_financial_statements": _FmpMetadataProfile(category="financial_statements"),
    "get_financial_statement_growth": _FmpMetadataProfile(category="financial_statements"),
    "get_latest_financial_statements": _FmpMetadataProfile(category="financial_statements"),
    "get_key_metrics": _FmpMetadataProfile(category="metrics_and_ratios"),
    "get_key_metrics_ttm": _FmpMetadataProfile(category="metrics_and_ratios"),
    "get_financial_ratios": _FmpMetadataProfile(category="metrics_and_ratios"),
    "get_financial_ratios_ttm": _FmpMetadataProfile(category="metrics_and_ratios"),
    "get_enterprise_values": _FmpMetadataProfile(category="metrics_and_ratios"),
    "get_owner_earnings": _FmpMetadataProfile(category="metrics_and_ratios"),
    "get_dcf_advanced": _FmpMetadataProfile(category="valuation_outputs"),
    "get_levered_dcf": _FmpMetadataProfile(category="valuation_outputs"),
    "get_custom_dcf_advanced": _FmpMetadataProfile(category="valuation_outputs"),
    "get_financial_estimates": _FmpMetadataProfile(
        category="valuation_outputs",
        when_to_use=(
            "当任务需要卖方一致预期时使用；适合查看未来收入、EPS 或利润预测，"
            "用于校验市场隐含预期，而不是替代公司自身指引。"
        ),
    ),
    "get_price_target_consensus": _FmpMetadataProfile(
        category="valuation_outputs",
        when_to_use=(
            "当任务需要卖方目标价区间时使用；适合快速了解市场目标价分布，"
            "不适合把它当成独立估值结论。"
        ),
    ),
    "get_stock_peers": _FmpMetadataProfile(category="comparables"),
    "get_company_executives": _FmpMetadataProfile(category="governance_and_ownership"),
    "get_executive_compensation": _FmpMetadataProfile(category="governance_and_ownership"),
    "get_earnings_transcripts": _FmpMetadataProfile(category="transcripts"),
    "get_positions_summary": _FmpMetadataProfile(category="governance_and_ownership"),
    "get_latest_insider_trades": _FmpMetadataProfile(category="insiders"),
    "search_insider_trades": _FmpMetadataProfile(category="insiders"),
    "get_insider_trade_statistics": _FmpMetadataProfile(category="insiders"),
    "get_treasury_rates": _FmpMetadataProfile(category="macro"),
    "get_market_risk_premium": _FmpMetadataProfile(category="macro"),
    "get_economic_indicators": _FmpMetadataProfile(category="macro"),
}


def _iter_public_fmp_methods() -> list[tuple[str, object]]:
    """按定义顺序返回 `FmpClient` 的公开方法。"""

    methods: list[tuple[str, object]] = []
    for name, value in FmpClient.__dict__.items():
        if name.startswith("_") or not callable(value):
            continue
        methods.append((name, value))
    return methods


def _resolve_metadata_profile(method_name: str, fallback_purpose: str) -> tuple[str, str, str, str]:
    """根据方法名解析最终使用的 FMP 元数据。"""

    profile = _FMP_METADATA_PROFILES.get(method_name)
    if profile is None:
        raise ValueError(f"FMP 方法缺少元数据分类: {method_name}")
    template = _FMP_METADATA_TEMPLATES.get(profile.category)
    if template is None:
        raise ValueError(f"FMP 方法命中了未知元数据分类: {profile.category}")
    return (
        profile.purpose or fallback_purpose,
        profile.when_to_use or template.when_to_use,
        profile.returns or template.returns,
        profile.extra_params or template.extra_params,
    )


def _detect_method_family(method: object) -> str:
    """根据底层方法签名推断工具签名家族。"""

    signature = inspect.signature(method)
    visible_parameters = []
    has_var_keyword = False
    for parameter in signature.parameters.values():
        if parameter.name == "self":
            continue
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            has_var_keyword = True
            continue
        visible_parameters.append(parameter.name)
    if not has_var_keyword:
        raise ValueError("FMP 公开方法缺少透传参数形状，无法映射为工具。")
    if visible_parameters == ["from_date", "to_date"]:
        return "date_range"
    if visible_parameters == ["symbol"]:
        return "symbol"
    if visible_parameters == ["symbol", "from_date", "to_date"]:
        return "symbol_date_range"
    if visible_parameters == ["symbol", "year", "period"]:
        return "symbol_year_period"
    if visible_parameters == ["symbol", "year", "quarter"]:
        return "symbol_year_quarter"
    if not visible_parameters:
        return "extra_params"
    raise ValueError(f"未识别的 FMP 方法签名: {visible_parameters}")


def _build_tool_specs() -> tuple[_FmpToolSpec, ...]:
    """从 `FmpClient` 公开方法构造全部工具规格。"""

    specs: list[_FmpToolSpec] = []
    for method_name, method in _iter_public_fmp_methods():
        doc = inspect.getdoc(method) or method_name
        fallback_purpose = doc.splitlines()[0].strip().rstrip("。")
        purpose, when_to_use, returns_description, extra_params_description = (
            _resolve_metadata_profile(method_name, fallback_purpose)
        )
        specs.append(
            _FmpToolSpec(
                method_name=method_name,
                tool_name=f"fmp_{method_name}",
                purpose=purpose,
                when_to_use=when_to_use,
                returns_description=returns_description,
                extra_params_description=extra_params_description,
                family=_detect_method_family(method),
            )
        )
    return tuple(specs)


def _normalize_extra_params(
    extra_params: dict[str, Any] | None,
    *,
    reserved_keys: set[str],
) -> dict[str, Any]:
    """清洗并返回可安全透传的附加查询参数。"""

    if extra_params is None:
        return {}
    normalized = dict(extra_params)
    for key in reserved_keys:
        normalized.pop(key, None)
    return normalized


def _summarize_result(result: Any) -> str:
    """生成给模型和 TUI 复用的最小结果摘要。"""

    if isinstance(result, list):
        if not result:
            return "返回空列表。"
        first = result[0]
        if isinstance(first, dict):
            keys = ", ".join(list(first.keys())[:5]) or "无字段"
            return f"返回 {len(result)} 条记录，首项字段包括: {keys}。"
        return f"返回 {len(result)} 条列表项。"
    if isinstance(result, dict):
        keys = ", ".join(list(result.keys())[:8]) or "无字段"
        return f"返回对象结果，字段包括: {keys}。"
    return f"返回 {type(result).__name__} 类型结果。"


def _stringify_payload(payload: object) -> str:
    """把结构化结果序列化为可读文本。"""

    try:
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        text = str(payload)
    if len(text) <= _DETAIL_TEXT_LIMIT:
        return text
    return f"{text[:_DETAIL_TEXT_LIMIT]}\n...<truncated>"


def _build_tool_output(
    spec: _FmpToolSpec,
    *,
    request_payload: dict[str, Any],
    result: Any,
) -> ToolOutput:
    """把底层 FMP 结果包装成统一 `ToolOutput`。"""

    summary = _summarize_result(result)
    preview = f"{spec.tool_name}: {summary}"
    detail = "\n".join(
        [
            f"tool: {spec.tool_name}",
            f"method: {spec.method_name}",
            f"summary: {summary}",
            "request:",
            _stringify_payload(request_payload),
            "result:",
            _stringify_payload(result),
        ]
    )
    return ToolOutput(
        data={
            "tool_name": spec.tool_name,
            "method_name": spec.method_name,
            "request": request_payload,
            "result": result,
        },
        model_text=f"{spec.purpose}完成。{summary}",
        preview=preview,
        detail=detail,
    )


def _create_client() -> FmpClient:
    """创建一份最小 FMP 客户端。"""

    return create_fmp_client()


def _build_date_range_tool(spec: _FmpToolSpec) -> object:
    """构造日期区间类 FMP 工具。"""

    @tool(
        name=spec.tool_name,
        purpose=spec.purpose,
        when_to_use=spec.when_to_use,
        parameters={
            "from_date": _FROM_DATE_PARAMETER_DESCRIPTION,
            "to_date": _TO_DATE_PARAMETER_DESCRIPTION,
            "extra_params": spec.extra_params_description,
        },
        returns=spec.returns_description,
        common_failures=_COMMON_FAILURES,
    )
    def wrapped_tool(
        from_date: str = "",
        to_date: str = "",
        extra_params: dict[str, Any] | None = None,
    ) -> ToolOutput:
        """执行一次日期区间类 FMP 查询。"""

        params = _normalize_extra_params(
            extra_params,
            reserved_keys={"from_date", "to_date"},
        )
        result = getattr(_create_client(), spec.method_name)(
            from_date=from_date,
            to_date=to_date,
            **params,
        )
        return _build_tool_output(
            spec,
            request_payload={
                "from_date": from_date,
                "to_date": to_date,
                "extra_params": params,
            },
            result=result,
        )

    return wrapped_tool


def _build_symbol_tool(spec: _FmpToolSpec) -> object:
    """构造 symbol 类 FMP 工具。"""

    @tool(
        name=spec.tool_name,
        purpose=spec.purpose,
        when_to_use=spec.when_to_use,
        parameters={
            "symbol": _SYMBOL_PARAMETER_DESCRIPTION,
            "extra_params": spec.extra_params_description,
        },
        returns=spec.returns_description,
        common_failures=_COMMON_FAILURES,
    )
    def wrapped_tool(
        symbol: str,
        extra_params: dict[str, Any] | None = None,
    ) -> ToolOutput:
        """执行一次 symbol 类 FMP 查询。"""

        params = _normalize_extra_params(extra_params, reserved_keys={"symbol"})
        result = getattr(_create_client(), spec.method_name)(symbol=symbol, **params)
        return _build_tool_output(
            spec,
            request_payload={
                "symbol": symbol,
                "extra_params": params,
            },
            result=result,
        )

    return wrapped_tool


def _build_symbol_date_range_tool(spec: _FmpToolSpec) -> object:
    """构造 symbol + 日期区间类 FMP 工具。"""

    @tool(
        name=spec.tool_name,
        purpose=spec.purpose,
        when_to_use=spec.when_to_use,
        parameters={
            "symbol": _SYMBOL_PARAMETER_DESCRIPTION,
            "from_date": _FROM_DATE_PARAMETER_DESCRIPTION,
            "to_date": _TO_DATE_PARAMETER_DESCRIPTION,
            "extra_params": spec.extra_params_description,
        },
        returns=spec.returns_description,
        common_failures=_COMMON_FAILURES,
    )
    def wrapped_tool(
        symbol: str,
        from_date: str = "",
        to_date: str = "",
        extra_params: dict[str, Any] | None = None,
    ) -> ToolOutput:
        """执行一次 symbol + 日期区间类 FMP 查询。"""

        params = _normalize_extra_params(
            extra_params,
            reserved_keys={"symbol", "from_date", "to_date"},
        )
        result = getattr(_create_client(), spec.method_name)(
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            **params,
        )
        return _build_tool_output(
            spec,
            request_payload={
                "symbol": symbol,
                "from_date": from_date,
                "to_date": to_date,
                "extra_params": params,
            },
            result=result,
        )

    return wrapped_tool


def _build_symbol_year_period_tool(spec: _FmpToolSpec) -> object:
    """构造 symbol + year + period 类 FMP 工具。"""

    @tool(
        name=spec.tool_name,
        purpose=spec.purpose,
        when_to_use=spec.when_to_use,
        parameters={
            "symbol": _SYMBOL_PARAMETER_DESCRIPTION,
            "year": _YEAR_PARAMETER_DESCRIPTION,
            "period": _PERIOD_PARAMETER_DESCRIPTION,
            "extra_params": spec.extra_params_description,
        },
        returns=spec.returns_description,
        common_failures=_COMMON_FAILURES,
    )
    def wrapped_tool(
        symbol: str,
        year: int | None = None,
        period: str = "FY",
        extra_params: dict[str, Any] | None = None,
    ) -> ToolOutput:
        """执行一次 symbol + year + period 类 FMP 查询。"""

        params = _normalize_extra_params(
            extra_params,
            reserved_keys={"symbol", "year", "period"},
        )
        result = getattr(_create_client(), spec.method_name)(
            symbol=symbol,
            year=year,
            period=period,
            **params,
        )
        return _build_tool_output(
            spec,
            request_payload={
                "symbol": symbol,
                "year": year,
                "period": period,
                "extra_params": params,
            },
            result=result,
        )

    return wrapped_tool


def _build_symbol_year_quarter_tool(spec: _FmpToolSpec) -> object:
    """构造 symbol + year + quarter 类 FMP 工具。"""

    @tool(
        name=spec.tool_name,
        purpose=spec.purpose,
        when_to_use=spec.when_to_use,
        parameters={
            "symbol": _SYMBOL_PARAMETER_DESCRIPTION,
            "year": _YEAR_PARAMETER_DESCRIPTION,
            "quarter": _QUARTER_PARAMETER_DESCRIPTION,
            "extra_params": spec.extra_params_description,
        },
        returns=spec.returns_description,
        common_failures=_COMMON_FAILURES,
    )
    def wrapped_tool(
        symbol: str,
        year: int | None = None,
        quarter: int | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> ToolOutput:
        """执行一次 symbol + year + quarter 类 FMP 查询。"""

        params = _normalize_extra_params(
            extra_params,
            reserved_keys={"symbol", "year", "quarter"},
        )
        result = getattr(_create_client(), spec.method_name)(
            symbol=symbol,
            year=year,
            quarter=quarter,
            **params,
        )
        return _build_tool_output(
            spec,
            request_payload={
                "symbol": symbol,
                "year": year,
                "quarter": quarter,
                "extra_params": params,
            },
            result=result,
        )

    return wrapped_tool


def _build_extra_params_tool(spec: _FmpToolSpec) -> object:
    """构造仅透传额外参数的 FMP 工具。"""

    @tool(
        name=spec.tool_name,
        purpose=spec.purpose,
        when_to_use=spec.when_to_use,
        parameters={
            "extra_params": spec.extra_params_description,
        },
        returns=spec.returns_description,
        common_failures=_COMMON_FAILURES,
    )
    def wrapped_tool(extra_params: dict[str, Any] | None = None) -> ToolOutput:
        """执行一次仅透传参数的 FMP 查询。"""

        params = _normalize_extra_params(extra_params, reserved_keys=set())
        result = getattr(_create_client(), spec.method_name)(**params)
        return _build_tool_output(
            spec,
            request_payload={"extra_params": params},
            result=result,
        )

    return wrapped_tool


def _build_tool_from_spec(spec: _FmpToolSpec) -> object:
    """根据签名家族生成一个具体的 FMP 工具对象。"""

    if spec.family == "date_range":
        return _build_date_range_tool(spec)
    if spec.family == "symbol":
        return _build_symbol_tool(spec)
    if spec.family == "symbol_date_range":
        return _build_symbol_date_range_tool(spec)
    if spec.family == "symbol_year_period":
        return _build_symbol_year_period_tool(spec)
    if spec.family == "symbol_year_quarter":
        return _build_symbol_year_quarter_tool(spec)
    if spec.family == "extra_params":
        return _build_extra_params_tool(spec)
    raise ValueError(f"未知 FMP 工具家族: {spec.family}")


FMP_TOOL_SPECS = _build_tool_specs()
FMP_TOOL_NAMES = tuple(spec.tool_name for spec in FMP_TOOL_SPECS)
FMP_TOOLS = tuple(_build_tool_from_spec(spec) for spec in FMP_TOOL_SPECS)


def build_fmp_tools() -> list[object]:
    """返回默认 FMP EasyHarness 工具对象列表。

    Returns:
        与 `FmpClient` 公开查询方法一一对应的工具对象列表。
    """

    return list(FMP_TOOLS)
