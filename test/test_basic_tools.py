"""基础 EasyHarness 工具最小回归测试。

该文件验证 `src/tool/basic_tools.py` 提供的三个基础工具已经形成最小可靠闭环：

1. SymPy 计算器可以完成单表达式化简；
2. 当前时间工具返回毫秒级时间字段；
3. 简易网页抓取工具可以解析标题与正文摘录。
"""

from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from src.tool.basic_tools import BASIC_TOOL_NAMES, build_basic_tools


def _find_tool(tool_name: str) -> object:
    """从默认基础工具集合中找到目标工具。"""

    for item in build_basic_tools():
        if getattr(item, "tool_name", "") == tool_name:
            return item
    raise AssertionError(f"未找到工具: {tool_name}")


class _FakeResponse:
    """用于模拟 requests.Response 的最小替身。"""

    def __init__(
        self,
        *,
        text: str,
        url: str,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self) -> None:
        """测试默认使用成功响应，不做额外处理。"""


class BasicEasyHarnessToolTests(unittest.TestCase):
    """验证基础 EasyHarness 工具的核心边界行为。"""

    def test_build_basic_tools_exposes_expected_names(self) -> None:
        """基础工具集合应暴露稳定公开名。"""

        self.assertEqual(
            BASIC_TOOL_NAMES,
            ("calculator", "now", "web_fetch_page"),
        )
        self.assertEqual(len(build_basic_tools()), 3)

    def test_basic_calculator_simplifies_one_expression(self) -> None:
        """计算器工具应返回 SymPy 化简结果。"""

        tool_obj = _find_tool("calculator")
        output = tool_obj(expression="sin(x)**2 + cos(x)**2")

        self.assertEqual(output.data["result"], "1")
        self.assertIn("计算结果: 1", output.preview)

    def test_now_returns_millisecond_precision_fields(self) -> None:
        """当前时间工具应返回毫秒级字段。"""

        tool_obj = _find_tool("now")
        output = tool_obj()

        self.assertRegex(output.data["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(output.data["time"], r"^\d{2}:\d{2}:\d{2}\.\d{3}$")
        self.assertRegex(
            output.data["datetime_local"],
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}$",
        )
        self.assertIsInstance(output.data["timestamp_ms"], int)
        self.assertEqual(output.data["year"], int(output.data["date"][:4]))

    def test_web_fetch_page_extracts_title_and_excerpt(self) -> None:
        """网页抓取工具应返回标题与正文摘录。"""

        tool_obj = _find_tool("web_fetch_page")
        response = _FakeResponse(
            text=(
                "<html><head><title>Example Page</title></head>"
                "<body><h1>Hello</h1><p>SmartIPO fetch test.</p></body></html>"
            ),
            url="https://example.com/final",
        )

        with patch("src.tool.basic_tools.requests.get", return_value=response) as mocked_get:
            output = tool_obj(url="https://example.com")

        mocked_get.assert_called_once()
        self.assertEqual(output.data["status_code"], 200)
        self.assertEqual(output.data["final_url"], "https://example.com/final")
        self.assertEqual(output.data["title"], "Example Page")
        self.assertIn("Hello SmartIPO fetch test.", output.data["text_excerpt"])
        self.assertIn("抓取成功", output.preview)

    def test_web_fetch_page_rejects_non_http_scheme(self) -> None:
        """网页抓取工具应拒绝非 HTTP(S) 地址。"""

        tool_obj = _find_tool("web_fetch_page")

        with self.assertRaisesRegex(ValueError, "http"):
            tool_obj(url="ftp://example.com")


if __name__ == "__main__":
    unittest.main()
