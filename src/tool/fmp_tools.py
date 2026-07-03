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


@dataclass(slots=True, frozen=True)
class _FmpToolSpec:
    """描述一个 FMP 方法到 EasyHarness 工具的映射关系。"""

    method_name: str
    tool_name: str
    purpose: str
    when_to_use: str
    family: str


def _iter_public_fmp_methods() -> list[tuple[str, object]]:
    """按定义顺序返回 `FmpClient` 的公开方法。"""

    methods: list[tuple[str, object]] = []
    for name, value in FmpClient.__dict__.items():
        if name.startswith("_") or not callable(value):
            continue
        methods.append((name, value))
    return methods


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
        purpose = doc.splitlines()[0].strip().rstrip("。")
        specs.append(
            _FmpToolSpec(
                method_name=method_name,
                tool_name=f"fmp_{method_name}",
                purpose=purpose,
                when_to_use=(
                    f"当任务明确需要通过 Financial Modeling Prep {purpose} 时使用；"
                    "优先用于美股 IPO、财报、估值和研究数据查询，不要把它当成通用文件工具。"
                ),
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
            "from_date": "开始日期，格式为 YYYY-MM-DD；留空时交给 FMP 默认逻辑。",
            "to_date": "结束日期，格式为 YYYY-MM-DD；留空时交给 FMP 默认逻辑。",
            "extra_params": "额外 FMP 查询参数 JSON 对象；显式参数优先于同名附加参数。",
        },
        returns="返回 FMP 原始 JSON 结果与最小摘要，不生成业务结论。",
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
            "symbol": "美股股票代码，例如 AAPL、MSFT、NVDA。",
            "extra_params": "额外 FMP 查询参数 JSON 对象；显式参数优先于同名附加参数。",
        },
        returns="返回 FMP 原始 JSON 结果与最小摘要，不生成业务结论。",
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


def _build_symbol_year_period_tool(spec: _FmpToolSpec) -> object:
    """构造 symbol + year + period 类 FMP 工具。"""

    @tool(
        name=spec.tool_name,
        purpose=spec.purpose,
        when_to_use=spec.when_to_use,
        parameters={
            "symbol": "美股股票代码，例如 AAPL、MSFT、NVDA。",
            "year": "可选财年；留空时交给 FMP 默认逻辑。",
            "period": "财报周期，例如 FY、Q1、Q2、Q3。",
            "extra_params": "额外 FMP 查询参数 JSON 对象；显式参数优先于同名附加参数。",
        },
        returns="返回 FMP 原始 JSON 结果与最小摘要，不生成业务结论。",
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
            "symbol": "美股股票代码，例如 AAPL、MSFT、NVDA。",
            "year": "可选年份；留空时交给 FMP 默认逻辑。",
            "quarter": "可选季度，通常为 1 到 4。",
            "extra_params": "额外 FMP 查询参数 JSON 对象；显式参数优先于同名附加参数。",
        },
        returns="返回 FMP 原始 JSON 结果与最小摘要，不生成业务结论。",
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
            "extra_params": "额外 FMP 查询参数 JSON 对象；为空时使用 FMP 默认逻辑。",
        },
        returns="返回 FMP 原始 JSON 结果与最小摘要，不生成业务结论。",
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
