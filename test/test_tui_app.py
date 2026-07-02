"""Textual workbench 冒烟测试。

该文件验证本地工作台的最小交互闭环：提交一条任务后，时间线会按顺序展示
用户消息、工具过程和 assistant 流式输出。
"""

from __future__ import annotations

import unittest
from textual.widgets import Input

from src.core.agent import SessionTurn
from src.core.events import build_loop_event
from src.core.strands_runtime import StrandsRunResult
from src.tui.app import AgentWorkbenchApp


class _FakeUiSessionLoop:
    """用于驱动 TUI 冒烟测试的假 Agent。"""

    def __init__(self) -> None:
        self.event_sink = None
        self._history: list[SessionTurn] = []

    @property
    def history(self) -> tuple[SessionTurn, ...]:
        return tuple(self._history)

    def reset(self) -> None:
        self._history = []

    def run(self, prompt: str) -> StrandsRunResult:
        self._history.append(SessionTurn(role="user", content=prompt))
        if self.event_sink is not None:
            self.event_sink(
                build_loop_event(
                    "progress",
                    "thinking_started",
                    message="正在思考下一步。",
                )
            )
            self.event_sink(
                build_loop_event(
                    "progress",
                    "tool_started",
                    tool_name="text.read",
                    display_name="Text read",
                    tool_kind="fileglide",
                    message="开始调用 Text read。",
                )
            )
            self.event_sink(
                build_loop_event(
                    "progress",
                    "tool_completed",
                    tool_name="text.read",
                    display_name="Text read",
                    tool_kind="fileglide",
                    duration_ms=12,
                    result_summary="README.md",
                    message="Text read 调用完成。",
                )
            )
            self.event_sink(
                build_loop_event(
                    "assistant",
                    "assistant_stream_started",
                    message="正在生成回复。",
                )
            )
            self.event_sink(
                build_loop_event(
                    "assistant",
                    "assistant_stream_delta",
                    text="已完成",
                )
            )
            self.event_sink(
                build_loop_event(
                    "assistant",
                    "assistant_stream_completed",
                    text="已完成",
                    fallback=False,
                )
            )
        self._history.append(SessionTurn(role="assistant", content="已完成"))
        return StrandsRunResult(text="已完成")


class AgentWorkbenchAppTests(unittest.IsolatedAsyncioTestCase):
    """验证 Textual 工作台的最小交互闭环。"""

    async def test_submit_task_renders_streaming_timeline(self) -> None:
        """提交任务后时间线应展示用户消息、工具过程和 assistant 输出。"""

        session_loop = _FakeUiSessionLoop()
        app = AgentWorkbenchApp(session_loop=session_loop)
        session_loop.event_sink = app._dispatch_runtime_event

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            input_widget.value = "整理 README"
            fake_event = type(
                "FakeSubmittedEvent",
                (),
                {"input": input_widget, "value": "整理 README"},
            )()
            app.on_input_submitted(fake_event)
            await pilot.pause()
            await pilot.pause()
            text = app._render_timeline_text()

        self.assertIn("你: 整理 README", text)
        self.assertIn("文件工具 · Text read", text)
        self.assertIn("AI: 已完成", text)


if __name__ == "__main__":
    unittest.main()
