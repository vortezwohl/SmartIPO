"""SmartIPO 通用基础工具集合。

该文件提供三类与业务无关、但 agent 日常执行常会用到的最小工具：

1. 使用 SymPy 计算或化简单个数学表达式的计算器；
2. 返回当前本地日期时间与毫秒时间戳的时钟；
3. 使用 requests 抓取单个网页并提取标题与正文摘录的简易网页访问工具。

这些工具刻意保持宽松与轻量，只处理最基本的输入边界，不额外引入复杂
校验、浏览器自动化或领域建模。
"""

from __future__ import annotations

from datetime import datetime
from html import unescape
import re
from typing import Any
from urllib.parse import urlparse

from easyharness import ToolOutput, tool
import requests
from sympy import simplify

_DETAIL_TEXT_LIMIT = 4000
_DEFAULT_TIMEOUT_SECONDS = 10

BASIC_TOOL_NAMES = (
    "calculator",
    "now",
    "web_fetch_page",
)


def _stringify_payload(payload: object) -> str:
    """把结果对象转成适合 detail 通道展示的文本。"""

    text = str(payload)
    if len(text) <= _DETAIL_TEXT_LIMIT:
        return text
    return f"{text[:_DETAIL_TEXT_LIMIT]}\n...<truncated>"


def _extract_html_title(html_text: str) -> str:
    """从 HTML 文本中提取标题。"""

    matched = re.search(
        r"<title[^>]*>(.*?)</title>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not matched:
        return ""
    return re.sub(r"\s+", " ", unescape(matched.group(1))).strip()


def _extract_text_excerpt(raw_text: str, content_type: str) -> str:
    """从响应文本中提取可读摘要。"""

    normalized = raw_text
    if "html" in content_type.lower():
        normalized = re.sub(
            r"<(script|style)[^>]*>.*?</\1>",
            " ",
            normalized,
            flags=re.IGNORECASE | re.DOTALL,
        )
        normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = re.sub(r"\s+", " ", unescape(normalized)).strip()
    if len(normalized) <= _DETAIL_TEXT_LIMIT:
        return normalized
    return normalized[:_DETAIL_TEXT_LIMIT]


@tool(
    name="calculator",
    purpose="计算或化简单个数学表达式。",
    when_to_use=(
        "当任务只需要一次快速算术计算、代数化简或符号表达式求值时使用；"
        "不适合多步骤数据分析或需要外部数据源的计算。"
    ),
    parameters={
        "expression": "单个数学表达式字符串，例如 '(2 + 2) * 5'、'sin(x)**2 + cos(x)**2'。",
    },
    returns="返回原始表达式与计算结果字符串，适合直接继续推理或写入结论。",
    common_failures=(
        "expression 为空。",
        "SymPy 无法解析输入表达式。",
    ),
)
def basic_calculator(expression: str) -> ToolOutput:
    """使用 SymPy 计算或化简一个数学表达式。"""

    if not expression.strip():
        raise ValueError("expression 不能为空。")

    result = simplify(expression)
    result_text = str(result)
    detail = "\n".join(
        [
            "tool: calculator",
            f"expression: {expression}",
            f"result: {result_text}",
        ]
    )
    return ToolOutput(
        data={
            "expression": expression,
            "result": result_text,
        },
        model_text=f"表达式结果: {result_text}",
        preview=f"计算结果: {result_text}",
        detail=detail,
    )


@tool(
    name="now",
    purpose="返回当前本地日期时间与毫秒时间戳。",
    when_to_use="当任务需要当前年份、日期、时间、时区或毫秒时间戳时使用。",
    parameters={},
    returns=(
        "返回当前本地 year、date、time、ISO 8601 时间串、timezone 和毫秒级 Unix 时间戳。"
    ),
    common_failures=(
        "系统时钟访问异常失败。",
    ),
)
def now() -> ToolOutput:
    """返回当前本地时间，精确到毫秒。"""

    current = datetime.now().astimezone()
    iso_text = current.isoformat(timespec="milliseconds")
    payload = {
        "year": current.year,
        "date": current.strftime("%Y-%m-%d"),
        "time": current.strftime("%H:%M:%S.%f")[:-3],
        "datetime_local": current.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "iso8601": iso_text,
        "timestamp_ms": int(current.timestamp() * 1000),
        "timezone": str(current.tzinfo) if current.tzinfo is not None else "",
    }
    detail = "\n".join(
        [
            "tool: now",
            f"payload: {_stringify_payload(payload)}",
        ]
    )
    return ToolOutput(
        data=payload,
        model_text=f"当前本地时间: {payload['datetime_local']}",
        preview=f"当前时间: {payload['datetime_local']}",
        detail=detail,
    )


@tool(
    name="web_fetch_page",
    purpose="抓取单个网页并返回轻量文本摘要。",
    when_to_use=(
        "当任务只需要对公开网页做一次简单 HTTP 抓取，并不需要浏览器自动化、点击、截图"
        "或 JavaScript 执行时使用。"
    ),
    parameters={
        "url": "需要抓取的 http 或 https URL。",
        "timeout_seconds": "可选请求超时时间，单位为秒；默认 10 秒。",
    },
    returns=(
        "返回响应状态、最终 URL、内容类型、页面标题（若存在）与正文摘录；"
        "正文摘录可能被截断，且不会执行页面脚本。"
    ),
    common_failures=(
        "URL 为空或不属于 http/https。",
        "网络请求失败或服务端返回 HTTP 错误。",
    ),
)
def web_fetch_page(url: str, timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS) -> ToolOutput:
    """抓取一个网页并返回最小文本摘要。"""

    target = url.strip()
    if not target:
        raise ValueError("url 不能为空。")

    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("url 仅支持 http 或 https。")

    response = requests.get(
        target,
        timeout=timeout_seconds,
        allow_redirects=True,
        headers={
            "User-Agent": "SmartIPO/0.1 web_fetch_page",
        },
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    title = _extract_html_title(response.text) if "html" in content_type.lower() else ""
    excerpt = _extract_text_excerpt(response.text, content_type)
    payload: dict[str, Any] = {
        "url": target,
        "final_url": response.url,
        "status_code": response.status_code,
        "content_type": content_type,
        "title": title,
        "text_excerpt": excerpt,
    }
    detail = "\n".join(
        [
            "tool: web_fetch_page",
            f"payload: {_stringify_payload(payload)}",
        ]
    )
    summary = title or excerpt[:120] or response.url
    return ToolOutput(
        data=payload,
        model_text=f"网页抓取完成。摘要: {summary}",
        preview=f"抓取成功: {summary}",
        detail=detail,
    )


def build_basic_tools() -> list[object]:
    """返回默认基础工具对象列表。"""

    return [
        basic_calculator,
        now,
        web_fetch_page,
    ]
