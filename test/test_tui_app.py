"""Textual workbench 冒烟测试。

该文件验证本地工作台的最小交互闭环：提交一条任务后，时间线会按顺序展示
用户消息、工具过程和 assistant 流式输出。
"""

from __future__ import annotations

import time
import unittest
from textual.widgets import Input

from src.core.agent import SessionTurn
from src.core.events import build_loop_event
from src.core.strands_runtime import StrandsRunResult
from src.tui.app import AgentWorkbenchApp, DEFAULT_WORKBENCH_TOOL_NAMES


class _BaseUiSessionLoop:
    """用于驱动 TUI 测试的假 Agent 基类。"""

    def __init__(self) -> None:
        self.event_sink = None
        self._history: list[SessionTurn] = []

    @property
    def history(self) -> tuple[SessionTurn, ...]:
        return tuple(self._history)

    def reset(self) -> None:
        self._history = []

    def _emit_tool_completed(self) -> None:
        """发送工具完成事件。"""

        if self.event_sink is None:
            return
        self.event_sink(
            build_loop_event(
                "progress",
                "tool_completed",
                tool_name="text.read",
                tool_kind="fileglide",
                tool_use_id="tool-1",
                duration_ms=12,
                result_preview="README.md",
                result_detail="README.md\nline 2\nline 3",
                collapsible=True,
                collapsed_by_default=True,
            )
        )

    def _emit_assistant_completed(self) -> None:
        """发送 assistant 完成事件。"""

        if self.event_sink is None:
            return
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


class _FakeUiSessionLoop(_BaseUiSessionLoop):
    """用于驱动 TUI 冒烟测试的假 Agent。"""

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
                    "tool_attempt_started",
                    tool_name="text.read",
                    tool_kind="fileglide",
                    tool_use_id="tool-1",
                )
            )
            self.event_sink(
                build_loop_event(
                    "progress",
                    "tool_started",
                    tool_name="text.read",
                    tool_kind="fileglide",
                    tool_use_id="tool-1",
                )
            )
            self._emit_tool_completed()
            self._emit_assistant_completed()
        self._history.append(SessionTurn(role="assistant", content="已完成"))
        return StrandsRunResult(text="已完成")


class _SlowToolSessionLoop(_BaseUiSessionLoop):
    """用于验证运行中工具条目和计时可见性的假 Agent。"""

    def run(self, prompt: str) -> StrandsRunResult:
        self._history.append(SessionTurn(role="user", content=prompt))
        if self.event_sink is not None:
            self.event_sink(
                build_loop_event(
                    "progress",
                    "tool_attempt_started",
                    tool_name="text.read",
                    tool_kind="fileglide",
                    tool_use_id="tool-1",
                )
            )
            self.event_sink(
                build_loop_event(
                    "progress",
                    "tool_started",
                    tool_name="text.read",
                    tool_kind="fileglide",
                    tool_use_id="tool-1",
                )
            )
            time.sleep(0.35)
            self._emit_tool_completed()
        self._history.append(SessionTurn(role="assistant", content="已完成"))
        return StrandsRunResult(text="已完成")


class _FastToolSessionLoop(_BaseUiSessionLoop):
    """用于验证快速工具也会先显示运行态的假 Agent。"""

    def run(self, prompt: str) -> StrandsRunResult:
        self._history.append(SessionTurn(role="user", content=prompt))
        if self.event_sink is not None:
            self.event_sink(
                build_loop_event(
                    "progress",
                    "tool_attempt_started",
                    tool_name="text.read",
                    tool_kind="fileglide",
                    tool_use_id="tool-1",
                )
            )
            self.event_sink(
                build_loop_event(
                    "progress",
                    "tool_started",
                    tool_name="text.read",
                    tool_kind="fileglide",
                    tool_use_id="tool-1",
                )
            )
            self._emit_tool_completed()
        self._history.append(SessionTurn(role="assistant", content="已完成"))
        return StrandsRunResult(text="已完成")


class _AttemptFailureSessionLoop(_BaseUiSessionLoop):
    """用于验证 provider-side tool attempt failure 可见性的假 Agent。"""

    def run(self, prompt: str) -> StrandsRunResult:
        self._history.append(SessionTurn(role="user", content=prompt))
        if self.event_sink is not None:
            self.event_sink(
                build_loop_event(
                    "progress",
                    "tool_attempt_started",
                    tool_name="path.list",
                    tool_kind="fileglide",
                    tool_use_id="tool-attempt-1",
                )
            )
            self.event_sink(
                build_loop_event(
                    "progress",
                    "tool_attempt_failed",
                    tool_name="path.list",
                    tool_kind="fileglide",
                    tool_use_id="tool-attempt-1",
                    error="provider-side tool call did not reach local execution",
                    failure_stage="attempt",
                )
            )
        self._history.append(SessionTurn(role="assistant", content="未能完成"))
        return StrandsRunResult(text="未能完成")


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
            await pilot.pause(0.35)
            text = app._render_timeline_text()

        self.assertIn("你: 整理 README", text)
        self.assertIn("text.read [fileglide]", text)
        self.assertIn("概要: README.md", text)
        self.assertIn("结果: [详细结果已收起]", text)
        self.assertIn("AI: 已完成", text)

    async def test_running_thinking_entry_renders_local_animation(self) -> None:
        """thinking 条目应以本地动画渲染 `. .. ...`。"""

        app = AgentWorkbenchApp(session_loop=_FakeUiSessionLoop())
        app._timeline.append_user_message("你好")
        app._timeline.apply_event(
            build_loop_event(
                "progress",
                "thinking_started",
                message="正在思考下一步。",
            )
        )
        thinking_entry = app._timeline.entries[-1]
        thinking_entry.duration_ms = 800

        text = app._render_timeline_text()

        self.assertIn("thinking ...", text)

    def test_default_workbench_tool_set_is_minimal_and_read_only(self) -> None:
        """默认 workbench 只暴露最小高频只读工具集合。"""

        self.assertEqual(
            DEFAULT_WORKBENCH_TOOL_NAMES,
            ("path.list", "file.list", "text.read", "text.grep"),
        )

    async def test_running_tool_entry_and_timer_are_visible_before_completion(self) -> None:
        """工具运行中时，时间线里应先看到运行态和计时。"""

        session_loop = _SlowToolSessionLoop()
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
            await pilot.pause(0.15)
            mid_text = app._render_timeline_text()
            await pilot.pause(0.35)
            final_text = app._render_timeline_text()

        self.assertIn("text.read [fileglide]", mid_text)
        self.assertIn("进行中", mid_text)
        self.assertRegex(mid_text, r"0\.\d{2}s")
        self.assertIn("完成", final_text)
        self.assertIn("概要: README.md", final_text)

    async def test_fast_tool_stays_running_for_one_visible_frame(self) -> None:
        """极快完成的工具也应先显示一次运行态，再切到完成态。"""

        session_loop = _FastToolSessionLoop()
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
            await pilot.pause(0.05)
            running_text = app._render_timeline_text()
            await pilot.pause(0.30)
            done_text = app._render_timeline_text()

        self.assertIn("text.read [fileglide]", running_text)
        self.assertIn("进行中", running_text)
        self.assertIn("完成", done_text)
        self.assertIn("概要: README.md", done_text)

    async def test_provider_side_tool_attempt_failure_is_visible(self) -> None:
        """provider-side tool attempt failure 也应出现在时间线中。"""

        session_loop = _AttemptFailureSessionLoop()
        app = AgentWorkbenchApp(session_loop=session_loop)
        session_loop.event_sink = app._dispatch_runtime_event

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            input_widget.value = "看看目录"
            fake_event = type(
                "FakeSubmittedEvent",
                (),
                {"input": input_widget, "value": "看看目录"},
            )()
            app.on_input_submitted(fake_event)
            await pilot.pause(0.10)
            text = app._render_timeline_text()

        self.assertIn("path.list [fileglide]", text)
        self.assertIn("阶段: 调用尝试", text)
        self.assertIn("失败", text)
        self.assertIn(
            "错误: provider-side tool call did not reach local execution",
            text,
        )


if __name__ == "__main__":
    unittest.main()
