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
    purpose="Evaluate or simplify one math expression with SymPy.",
    when_to_use=(
        "Use when the task needs a quick arithmetic calculation or symbolic "
        "simplification from a single math expression."
    ),
    parameters={
        "expression": "A single math expression string, such as '(2 + 2) * 5' or 'sin(x)**2 + cos(x)**2'.",
    },
    returns="Returns the original expression and the computed or simplified result string.",
    common_failures=(
        "The expression is empty.",
        "SymPy cannot parse the input expression.",
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
    purpose="Return the current local date and time with millisecond precision.",
    when_to_use="Use when the task needs the current year, date, time, timezone, or millisecond timestamp.",
    parameters={},
    returns=(
        "Returns the current local year, date, time, ISO 8601 datetime string, timezone, "
        "and Unix timestamp in milliseconds."
    ),
    common_failures=(
        "System clock access fails unexpectedly.",
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
    purpose="Fetch one web page and return a lightweight text summary.",
    when_to_use=(
        "Use when the task only needs a simple HTTP fetch of a public page and does not "
        "need browser automation, clicks, screenshots, or JavaScript execution."
    ),
    parameters={
        "url": "The target http or https URL to fetch.",
        "timeout_seconds": "Optional request timeout in seconds. Defaults to 10.",
    },
    returns=(
        "Returns the response status, final URL, content type, page title if present, "
        "and a plain-text excerpt."
    ),
    common_failures=(
        "The URL is empty or does not use http/https.",
        "The network request fails or the server returns an HTTP error.",
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
