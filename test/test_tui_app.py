"""EasyHarness 事件流驱动的 Textual 工作台测试。

该文件验证 TUI 只消费 `easyharness.AgentEvent`，并在展示层本地维护
thinking、tool、assistant 和 system 的渲染状态，不再依赖项目私有事件流。
"""

from __future__ import annotations

import time
import unittest
from datetime import datetime, timezone

from easyharness import AgentEvent
from rich.panel import Panel
from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import Input, Static

from src.tui.app import (
    AgentWorkbenchApp,
    _CHAT_PREFIX_STYLE,
    _THINKING_HISTORY_BODY_STYLE,
    _THINKING_HISTORY_PREFIX_STYLE,
)


class _FakeStreamingAgent:
    """用于驱动 TUI 测试的 EasyHarness agent 兼容假对象。"""

    def __init__(self, events: list[AgentEvent]) -> None:
        self.events = events
        self.reset_count = 0
        self.prompts: list[str] = []

    def stream(self, prompt: str):
        """按顺序返回预设事件。"""

        self.prompts.append(prompt)
        yield from self.events

    def reset(self) -> None:
        """记录重置次数。"""

        self.reset_count += 1


class _DelayedStreamingAgent(_FakeStreamingAgent):
    """用于验证提交后等待态展示的带延迟假对象。"""

    def __init__(self, events: list[AgentEvent], *, delay_seconds: float) -> None:
        super().__init__(events)
        self.delay_seconds = delay_seconds

    def stream(self, prompt: str):
        """先等待一小段时间，再返回预设事件。"""

        self.prompts.append(prompt)
        time.sleep(self.delay_seconds)
        yield from self.events


class _ScriptedStreamingAgent:
    """按 prompt 返回不同脚本，用于验证队列串行与失败续跑。"""

    def __init__(
        self,
        scripts: dict[str, list[AgentEvent]],
        *,
        delays: dict[str, float] | None = None,
        errors: dict[str, BaseException] | None = None,
    ) -> None:
        self.scripts = scripts
        self.delays = delays or {}
        self.errors = errors or {}
        self.prompts: list[str] = []
        self.reset_count = 0

    def stream(self, prompt: str):
        """按 prompt 执行预设脚本，可选延迟或抛错。"""

        self.prompts.append(prompt)
        delay_seconds = self.delays.get(prompt, 0)
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        error = self.errors.get(prompt)
        if error is not None:
            raise error
        yield from self.scripts.get(prompt, [])

    def reset(self) -> None:
        """记录重置次数。"""

        self.reset_count += 1


class _RuntimeCancelableAgent:
    """模拟支持 runtime cancel 的 EasyHarness agent。"""

    def __init__(
        self,
        scripts: dict[str, list[AgentEvent]],
        *,
        cancelled_scripts: dict[str, list[AgentEvent]] | None = None,
        tail_scripts: dict[str, list[AgentEvent]] | None = None,
        wait_timeout_seconds: float = 1.0,
    ) -> None:
        self.scripts = scripts
        self.cancelled_scripts = cancelled_scripts or {}
        self.tail_scripts = tail_scripts or {}
        self.wait_timeout_seconds = wait_timeout_seconds
        self.prompts: list[str] = []
        self.cancel_count = 0
        self.reset_count = 0
        self._cancel_requested = False

    def stream(self, prompt: str):
        """先输出前置脚本；若该 prompt 支持取消，则等待 cancel 后再输出 cancelled 终态。"""

        self.prompts.append(prompt)
        for event in self.scripts.get(prompt, []):
            yield event

        cancelled_script = self.cancelled_scripts.get(prompt)
        if cancelled_script is not None:
            deadline = time.time() + self.wait_timeout_seconds
            while not self._cancel_requested and time.time() < deadline:
                time.sleep(0.01)
            if self._cancel_requested:
                yield from cancelled_script
                self._cancel_requested = False
                return

        yield from self.tail_scripts.get(prompt, [])

    def cancel(self) -> None:
        """记录取消并唤醒等待中的流。"""

        self.cancel_count += 1
        self._cancel_requested = True

    def reset(self) -> None:
        """记录重置次数。"""

        self.reset_count += 1


def _started_event(kind: str, *, name: str | None = None) -> AgentEvent:
    """构造 started 阶段测试事件。"""

    return AgentEvent(kind=kind, status="started", name=name)


class AgentWorkbenchAppTests(unittest.IsolatedAsyncioTestCase):
    """验证 Textual 工作台的 EasyHarness 事件流闭环。"""

    async def test_submit_task_renders_agent_event_stream(self) -> None:
        """提交任务后应按 AgentEvent 流展示用户、工具和 assistant 输出。"""

        agent = _FakeStreamingAgent(
            [
                _started_event("thinking"),
                _started_event("tool", name="fileglide_read_text"),
                AgentEvent(
                    kind="tool",
                    status="completed",
                    name="fileglide_read_text",
                    duration_ms=12,
                    data={
                        "tool_use_id": "tool-1",
                        "output": {
                            "preview": "fileglide_read_text: README.md",
                            "detail": "README.md\nline 2\nline 3",
                        },
                    },
                ),
                _started_event("assistant"),
                AgentEvent(kind="assistant", status="delta", text="已"),
                AgentEvent(kind="assistant", status="delta", text="完成"),
                AgentEvent(kind="assistant", status="completed", text="已完成"),
            ]
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            input_widget.value = "整理 README"
            fake_event = type(
                "FakeSubmittedEvent",
                (),
                {"input": input_widget, "value": "整理 README"},
            )()
            app.on_input_submitted(fake_event)
            await pilot.pause(0.5)
            text = app._render_timeline_text()

        self.assertEqual(agent.prompts, ["整理 README"])
        self.assertIn("User > 整理 README", text)
        tool_line = next(
            line for line in text.splitlines() if "Tool fileglide_read_text" in line
        )
        self.assertRegex(
            tool_line,
            r"^\d+\.\d{2}s · \{ Tool fileglide_read_text · Done \} · fileglide_read_text: README\.md$",
        )
        self.assertNotIn("Call tool-1", text)
        self.assertNotIn("Result README.md", text)
        self.assertIn("Assistant > 已完成", text)

    async def test_failed_tool_event_is_visible(self) -> None:
        """工具失败事件必须在 TUI 中明确展示为失败。"""

        agent = _FakeStreamingAgent(
            [
                _started_event("tool", name="fileglide_edit_text"),
                AgentEvent(
                    kind="tool",
                    status="failed",
                    name="fileglide_edit_text",
                    duration_ms=3,
                    text="permission denied",
                    data={"tool_use_id": "tool-2", "error": "permission denied"},
                ),
            ]
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            fake_event = type(
                "FakeSubmittedEvent",
                (),
                {"input": input_widget, "value": "写文件"},
            )()
            app.on_input_submitted(fake_event)
            await pilot.pause(0.35)
            text = app._render_timeline_text()

        tool_line = next(
            line for line in text.splitlines() if "Tool fileglide_edit_text" in line
        )
        self.assertRegex(
            tool_line,
            r"^\d+\.\d{2}s · \{ Tool fileglide_edit_text · Failed \} · Error: permission denied$",
        )

    async def test_system_failure_is_rendered(self) -> None:
        """系统失败事件应进入本地展示态。"""

        agent = _FakeStreamingAgent(
            [AgentEvent(kind="system", status="failed", text="模型调用失败")]
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            fake_event = type(
                "FakeSubmittedEvent",
                (),
                {"input": input_widget, "value": "你好"},
            )()
            app.on_input_submitted(fake_event)
            await pilot.pause(0.35)
            text = app._render_timeline_text()

        self.assertIn("SmartIPO · 模型调用失败", text)

    async def test_submit_starts_local_thinking_before_first_agent_event(self) -> None:
        """用户提交后应先看到本地 thinking 计时，再等真实输出到来。"""

        agent = _DelayedStreamingAgent(
            [
                _started_event("assistant"),
                AgentEvent(kind="assistant", status="delta", text="收到"),
                AgentEvent(kind="assistant", status="completed", text="收到"),
            ],
            delay_seconds=0.3,
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            fake_event = type(
                "FakeSubmittedEvent",
                (),
                {"input": input_widget, "value": "你好"},
            )()
            app.on_input_submitted(fake_event)
            await pilot.pause(0.02)
            waiting_text = app._render_timeline_text()
            await pilot.pause(0.35)
            final_text = app._render_timeline_text()

        self.assertIn("Thinking ...", waiting_text)
        self.assertIn("Assistant > 收到", final_text)
        self.assertNotIn("Thinking ...", final_text)

    async def test_agent_event_follows_bottom_when_user_is_near_bottom(self) -> None:
        """用户靠近底部时，新事件到来仍应自动跟随到底部。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))

        async with app.run_test() as pilot:
            for index in range(40):
                app._append_user_message(f"历史消息 {index}")
            app._refresh_view()
            await pilot.pause(0.1)

            scroll_widget = app.query_one("#timeline-scroll", VerticalScroll)
            self.assertGreater(scroll_widget.max_scroll_y, 0)
            scroll_widget.scroll_end(animate=False)
            await pilot.pause(0.1)

            app._apply_agent_event(
                AgentEvent(kind="assistant", status="delta", text="新输出")
            )
            await pilot.pause(0.1)

            self.assertEqual(scroll_widget.scroll_y, scroll_widget.max_scroll_y)

    async def test_agent_event_keeps_manual_scroll_position_when_user_away_from_bottom(self) -> None:
        """用户滚离底部后，新事件到来不应强制把 timeline 拉回到底部。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))

        async with app.run_test() as pilot:
            for index in range(40):
                app._append_user_message(f"历史消息 {index}")
            app._refresh_view()
            await pilot.pause(0.1)

            scroll_widget = app.query_one("#timeline-scroll", VerticalScroll)
            scroll_widget.scroll_home(animate=False)
            await pilot.pause(0.1)
            old_scroll_y = scroll_widget.scroll_y

            app._apply_agent_event(
                AgentEvent(kind="assistant", status="delta", text="新输出")
            )
            await pilot.pause(0.1)

            self.assertEqual(scroll_widget.scroll_y, old_scroll_y)
            self.assertLess(scroll_widget.scroll_y, scroll_widget.max_scroll_y)

    async def test_multiple_submissions_are_queued_and_run_in_order(self) -> None:
        """多次提交应按顺序串行执行，排队消息只显示在独立托盘。"""

        agent = _ScriptedStreamingAgent(
            {
                "第一条": [
                    _started_event("assistant"),
                    AgentEvent(kind="assistant", status="completed", text="第一条完成"),
                ],
                "第二条": [
                    _started_event("assistant"),
                    AgentEvent(kind="assistant", status="completed", text="第二条完成"),
                ],
                "第三条": [
                    _started_event("assistant"),
                    AgentEvent(kind="assistant", status="completed", text="第三条完成"),
                ],
            },
            delays={"第一条": 0.2, "第二条": 0.1},
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            for prompt in ("第一条", "第二条", "第三条"):
                fake_event = type(
                    "FakeSubmittedEvent",
                    (),
                    {"input": input_widget, "value": prompt},
                )()
                app.on_input_submitted(fake_event)
            await pilot.pause(0.05)
            queue_widget = app.query_one("#queue-tray", Static)
            waiting_text = app._render_timeline_text()
            queue_text = app._render_queue_tray_text()
            queue_renderable = app._render_queue_tray_renderable()
            queue_visible_during_wait = queue_widget.display
            await pilot.pause(0.65)
            final_text = app._render_timeline_text()
            final_queue_text = app._render_queue_tray_text()
            final_queue_visible = queue_widget.display

        self.assertEqual(agent.prompts, ["第一条", "第二条", "第三条"])
        self.assertIn("User > 第一条", waiting_text)
        self.assertNotIn("第二条", waiting_text)
        self.assertNotIn("第三条", waiting_text)
        self.assertTrue(queue_visible_during_wait)
        self.assertTrue(
            all(
                not isinstance(aligned.renderable, Panel)
                for aligned in queue_renderable.renderables[1:]
            )
        )
        self.assertEqual(queue_renderable.renderables[0].renderable.plain, "Queued")
        self.assertIn("第二条", queue_text)
        self.assertIn("第三条", queue_text)
        self.assertIn("Assistant > 第一条完成", final_text)
        self.assertIn("Assistant > 第二条完成", final_text)
        self.assertIn("Assistant > 第三条完成", final_text)
        self.assertEqual(final_queue_text, "")
        self.assertFalse(final_queue_visible)

    async def test_failed_turn_continues_with_next_queued_turn(self) -> None:
        """当前轮次失败后，下一条排队消息仍应继续执行。"""

        agent = _ScriptedStreamingAgent(
            {
                "第二条": [
                    _started_event("assistant"),
                    AgentEvent(kind="assistant", status="completed", text="第二条完成"),
                ]
            },
            delays={"第一条": 0.05},
            errors={"第一条": RuntimeError("boom")},
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            for prompt in ("第一条", "第二条"):
                fake_event = type(
                    "FakeSubmittedEvent",
                    (),
                    {"input": input_widget, "value": prompt},
                )()
                app.on_input_submitted(fake_event)
            await pilot.pause(0.4)
            text = app._render_timeline_text()

        self.assertEqual(agent.prompts, ["第一条", "第二条"])
        self.assertIn("User > 第一条", text)
        self.assertIn("Request failed: boom", text)
        self.assertIn("Assistant > 第二条完成", text)

    def test_running_thinking_entry_renders_english_waiting_label(self) -> None:
        """thinking started 条目应以英文等待标签渲染。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))
        app._append_user_message("你好")
        app._apply_agent_event(_started_event("thinking"))
        thinking_entry = app._items[-1]
        thinking_entry.duration_ms = 800

        text = app._render_timeline_text()

        self.assertIn("0.80s · Thinking ...", text)

    def test_running_thinking_entry_uses_utc_started_at_for_timer(self) -> None:
        """UTC started_at 不应被当成本地时间，避免计时跳到数小时。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))
        app._apply_agent_event(
            AgentEvent(
                kind="thinking",
                status="started",
                started_at=datetime.now(timezone.utc).isoformat(),
            )
        )

        time.sleep(0.05)
        app._refresh_running_items()

        self.assertLess(app._items[-1].duration_ms, 5000)

    def test_runtime_thinking_started_reuses_local_placeholder(self) -> None:
        """真实 thinking started 到来时应复用本地占位，而不是新增重复条目。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))
        app._start_local_thinking()
        first_item = app._items[-1]
        first_started_at = first_item.started_at

        time.sleep(0.02)
        app._apply_agent_event(_started_event("thinking"))

        thinking_items = [item for item in app._items if item.kind == "thinking"]
        self.assertEqual(len(thinking_items), 1)
        self.assertIs(thinking_items[0], first_item)
        self.assertEqual(thinking_items[0].started_at, first_started_at)
        self.assertFalse(thinking_items[0].metadata.get("provisional", False))
        self.assertTrue(thinking_items[0].metadata.get("ephemeral", False))

    def test_tool_event_removes_waiting_only_placeholder(self) -> None:
        """在 assistant 真正输出前，非 assistant 事件不应移除本地 thinking。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))
        app._start_local_thinking()

        time.sleep(0.02)
        app._apply_agent_event(_started_event("tool", name="fileglide_read_text"))

        text = app._render_timeline_text()

        self.assertNotIn("Thinking ...", text)
        self.assertIn("{ Tool fileglide_read_text · Running }", text)

    def test_runtime_thinking_text_becomes_visible_history(self) -> None:
        """收到真实 thinking 文本后，应通过 assistant 表面保留为可见历史。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))
        app._start_local_thinking()

        app._apply_agent_event(_started_event("thinking"))
        app._apply_agent_event(
            AgentEvent(kind="thinking", status="delta", text="Reviewing the filing.")
        )
        app._apply_agent_event(
            AgentEvent(
                kind="thinking",
                status="completed",
                text="Reviewing the filing.",
            )
        )

        thinking_item = [item for item in app._items if item.kind == "thinking"][-1]
        text = app._render_timeline_text()

        self.assertIn("Assistant (Thinking) > Reviewing the filing.", text)
        self.assertNotIn("Thinking ...", text)
        self.assertFalse(thinking_item.metadata.get("ephemeral", True))
        self.assertTrue(thinking_item.metadata.get("history", False))
        self.assertEqual(thinking_item.body, "Reviewing the filing.")

    def test_assistant_reply_appends_after_visible_thinking_history(self) -> None:
        """只有真实 thinking 和 assistant 时，最终回复也应作为后续阶段追加。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))

        app._apply_agent_event(_started_event("thinking"))
        app._apply_agent_event(
            AgentEvent(kind="thinking", status="delta", text="Planning the answer.")
        )
        app._apply_agent_event(_started_event("assistant"))
        app._apply_agent_event(
            AgentEvent(kind="assistant", status="completed", text="Final answer.")
        )

        text = app._render_timeline_text()
        thinking_index = text.index("Assistant (Thinking) > Planning the answer.")
        assistant_index = text.index("Assistant > Final answer.")

        self.assertLess(thinking_index, assistant_index)

    def test_thinking_history_renderable_uses_darker_styles(self) -> None:
        """真实 thinking 历史应使用专属暗色前缀和正文样式。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))
        app._apply_agent_event(_started_event("thinking"))
        app._apply_agent_event(
            AgentEvent(kind="thinking", status="delta", text="Reviewing the filing.")
        )

        history_item = [item for item in app._items if item.kind == "thinking"][-1]
        assistant_key = app._append_item(
            kind="assistant",
            title="Assistant > ",
            body="Final answer.",
        )
        assistant_item = app._get_item(assistant_key)

        self.assertIsNotNone(assistant_item)
        history_renderable = app._render_timeline_item_renderable(history_item)
        assistant_renderable = app._render_timeline_item_renderable(assistant_item)

        self.assertIsInstance(history_renderable, Text)
        self.assertIsInstance(assistant_renderable, Text)
        self.assertEqual(
            history_renderable.plain,
            "Assistant (Thinking) > Reviewing the filing.",
        )
        self.assertIn(
            _THINKING_HISTORY_PREFIX_STYLE,
            [span.style for span in history_renderable.spans],
        )
        self.assertIn(
            _THINKING_HISTORY_BODY_STYLE,
            [span.style for span in history_renderable.spans],
        )
        self.assertIn(
            _CHAT_PREFIX_STYLE,
            [span.style for span in assistant_renderable.spans],
        )
        self.assertIn("white", [span.style for span in assistant_renderable.spans])
        self.assertNotIn(_CHAT_PREFIX_STYLE, [span.style for span in history_renderable.spans])
        self.assertNotIn("white", [span.style for span in history_renderable.spans])

    def test_thinking_tool_assistant_chronology_preserves_thinking_history(self) -> None:
        """真实 thinking 历史在 tool 和最终 assistant 之后仍应可见。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))

        app._apply_agent_event(_started_event("thinking"))
        app._apply_agent_event(
            AgentEvent(kind="thinking", status="delta", text="Inspecting the filing.")
        )
        app._apply_agent_event(
            AgentEvent(
                kind="tool",
                status="started",
                name="fileglide_read_text",
                data={"tool_use_id": "tool-1"},
            )
        )
        app._apply_agent_event(
            AgentEvent(
                kind="tool",
                status="completed",
                name="fileglide_read_text",
                duration_ms=12,
                data={
                    "tool_use_id": "tool-1",
                    "output": {"preview": "fileglide_read_text: prospectus.md"},
                },
            )
        )
        app._apply_agent_event(_started_event("assistant"))
        app._apply_agent_event(
            AgentEvent(kind="assistant", status="completed", text="Done reviewing.")
        )

        text = app._render_timeline_text()
        thinking_index = text.index("Assistant (Thinking) > Inspecting the filing.")
        tool_index = text.index("Tool fileglide_read_text")
        assistant_index = text.index("Assistant > Done reviewing.")

        self.assertLess(thinking_index, tool_index)
        self.assertLess(tool_index, assistant_index)

    def test_new_session_resets_agent_and_local_state(self) -> None:
        """新会话应同时重置 agent 和 TUI 本地展示态。"""

        agent = _FakeStreamingAgent([])
        app = AgentWorkbenchApp(agent=agent)
        app._append_user_message("旧消息")

        app.action_new_session()

        self.assertEqual(agent.reset_count, 1)
        self.assertEqual(app._turn_count, 0)
        self.assertEqual(app._render_timeline_text(), "No messages yet.")
        self.assertEqual(app._render_queue_tray_text(), "")

    async def test_queue_tray_is_hidden_without_pending_turns(self) -> None:
        """空队列时 queue tray 应隐藏，且不显示空态文案。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))

        async with app.run_test() as pilot:
            await pilot.pause(0.05)
            queue_widget = app.query_one("#queue-tray", Static)

        self.assertFalse(queue_widget.display)
        self.assertEqual(app._render_queue_tray_text(), "")

    async def test_input_placeholder_and_text_prefixes_are_updated(self) -> None:
        """输入框文案和对话前缀应切换到新的聊天视觉语言。"""

        agent = _FakeStreamingAgent(
            [
                _started_event("assistant"),
                AgentEvent(kind="assistant", status="completed", text="你好，我是 SmartIPO"),
            ]
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            self.assertEqual(
                input_widget.placeholder,
                "Send a message. /stop interrupts, /new resets, /help shows commands.",
            )
            self.assertEqual(app.title, "SmartIPO")
            fake_event = type(
                "FakeSubmittedEvent",
                (),
                {"input": input_widget, "value": "hi"},
            )()
            app.on_input_submitted(fake_event)
            await pilot.pause(0.35)
            text = app._render_timeline_text()

        self.assertIn("User > hi", text)
        self.assertIn("Assistant > 你好，我是 SmartIPO", text)

    async def test_help_command_is_handled_inside_tui(self) -> None:
        """/help 应直接在 TUI 内部处理，而不是进入 agent 排队。"""

        agent = _FakeStreamingAgent([])
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            fake_event = type(
                "FakeSubmittedEvent",
                (),
                {"input": input_widget, "value": "/help"},
            )()
            app.on_input_submitted(fake_event)
            await pilot.pause(0.1)
            text = app._render_timeline_text()

        self.assertEqual(agent.prompts, [])
        self.assertIn("Available commands: /stop interrupts the active reply", text)
        self.assertEqual(app._render_queue_tray_text(), "")

    async def test_tab_binding_action_autocompletes_supported_slash_command(self) -> None:
        """Tab 绑定触发的命令补全应选出闭集中的最佳匹配。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            input_widget.focus()
            await pilot.pause(0.05)
            input_widget.value = "/stp"
            app.action_autocomplete_command()
            await pilot.pause(0.1)

        self.assertEqual(input_widget.value, "/stop")

    async def test_stop_command_preserves_partial_assistant_reply(self) -> None:
        """/stop 应调用 runtime cancel，保留半截 assistant，并留下 stopped 事件。"""

        agent = _RuntimeCancelableAgent(
            {
                "分析一下": [
                    _started_event("assistant"),
                    AgentEvent(kind="assistant", status="delta", text="这是半句"),
                ]
            },
            cancelled_scripts={
                "分析一下": [
                    AgentEvent(
                        kind="assistant",
                        status="cancelled",
                        text="这是半句",
                        duration_ms=10,
                    ),
                    AgentEvent(
                        kind="system",
                        status="cancelled",
                        text="这是半句",
                        data={"stop_reason": "cancelled"},
                    ),
                ]
            },
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            submit_event = type(
                "FakeSubmittedEvent",
                (),
                {"input": input_widget, "value": "分析一下"},
            )()
            app.on_input_submitted(submit_event)
            await pilot.pause(0.1)
            fake_event = type(
                "FakeSubmittedEvent",
                (),
                {"input": input_widget, "value": "/stop"},
            )()
            app.on_input_submitted(fake_event)
            await pilot.pause(0.25)
            text = app._render_timeline_text()

        self.assertIn("Assistant > 这是半句", text)
        self.assertIn("SmartIPO · Reply stopped.", text)
        self.assertEqual(agent.cancel_count, 1)
        self.assertIsNone(app._active_turn)
        self.assertEqual(app._turn_count, 1)

    async def test_stop_command_settles_cancelled_tool_without_marking_failure(self) -> None:
        """/stop 收到 cancelled tool 终态后，应显示 stopped 而不是 failed。"""

        agent = _RuntimeCancelableAgent(
            {
                "调用工具": [
                    AgentEvent(
                        kind="tool",
                        status="started",
                        name="fileglide_read_text",
                        data={"tool_use_id": "tool-1"},
                    )
                ]
            },
            cancelled_scripts={
                "调用工具": [
                    AgentEvent(
                        kind="tool",
                        status="cancelled",
                        name="fileglide_read_text",
                        duration_ms=8,
                        data={"tool_use_id": "tool-1"},
                    ),
                    AgentEvent(
                        kind="system",
                        status="cancelled",
                        data={"stop_reason": "cancelled"},
                    ),
                ]
            },
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            app.on_input_submitted(
                type(
                    "FakeSubmittedEvent",
                    (),
                    {"input": input_widget, "value": "调用工具"},
                )()
            )
            await pilot.pause(0.1)
            app.on_input_submitted(
                type(
                    "FakeSubmittedEvent",
                    (),
                    {"input": input_widget, "value": "/stop"},
                )()
            )
            await pilot.pause(0.25)
            text = app._render_timeline_text()

        self.assertIn("0.01s · { Tool fileglide_read_text · Stopped }", text)
        self.assertNotIn("Failed", text)
        self.assertIn("SmartIPO · Reply stopped.", text)

    async def test_cancelled_turn_ignores_late_events_and_continues_queue(self) -> None:
        """取消收口后，旧 turn 迟到事件不应污染后续排队 turn。"""

        agent = _RuntimeCancelableAgent(
            {
                "第一条": [
                    _started_event("assistant"),
                    AgentEvent(kind="assistant", status="delta", text="第一条半句"),
                ],
                "第二条": [_started_event("assistant")],
            },
            cancelled_scripts={
                "第一条": [
                    AgentEvent(
                        kind="assistant",
                        status="cancelled",
                        text="第一条半句",
                        duration_ms=10,
                    ),
                    AgentEvent(
                        kind="system",
                        status="cancelled",
                        data={"stop_reason": "cancelled"},
                    ),
                ]
            },
            tail_scripts={
                "第二条": [
                    AgentEvent(kind="assistant", status="completed", text="第二条完成"),
                ]
            },
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            for prompt in ("第一条", "第二条"):
                app.on_input_submitted(
                    type(
                        "FakeSubmittedEvent",
                        (),
                        {"input": input_widget, "value": prompt},
                    )()
                )
            await pilot.pause(0.1)
            stopped_turn_id = app._active_turn.turn_id  # type: ignore[union-attr]
            app.on_input_submitted(
                type(
                    "FakeSubmittedEvent",
                    (),
                    {"input": input_widget, "value": "/stop"},
                )()
            )
            await pilot.pause(0.45)

        app._apply_agent_event_for_turn(
            stopped_turn_id,
            AgentEvent(kind="assistant", status="delta", text="旧输出"),
        )
        text = app._render_timeline_text()

        self.assertEqual(agent.prompts, ["第一条", "第二条"])
        self.assertIn("SmartIPO · Reply stopped.", text)
        self.assertIn("Assistant > 第二条完成", text)
        self.assertNotIn("旧输出", text)

    async def test_stop_command_without_active_reply_reports_noop(self) -> None:
        """/stop 在空闲状态下应提示无活跃回复。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            app.on_input_submitted(
                type(
                    "FakeSubmittedEvent",
                    (),
                    {"input": input_widget, "value": "/stop"},
                )()
            )
            await pilot.pause(0.1)
            text = app._render_timeline_text()

        self.assertIn("SmartIPO · There is no active reply to interrupt.", text)

    async def test_new_command_resets_session_and_ignores_old_turn_events(self) -> None:
        """/new 应重置本地会话，并继续忽略旧 turn 的迟到事件。"""

        agent = _FakeStreamingAgent([])
        app = AgentWorkbenchApp(agent=agent)
        app._enqueue_turn("旧消息")
        app._active_turn = app._pending_turns.popleft()
        app._refresh_turn_queue_metadata()
        old_turn_id = app._active_turn.turn_id  # type: ignore[union-attr]

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            fake_event = type(
                "FakeSubmittedEvent",
                (),
                {"input": input_widget, "value": "/new"},
            )()
            app.on_input_submitted(fake_event)
            await pilot.pause(0.1)

        app._apply_agent_event_for_turn(
            old_turn_id,
            AgentEvent(kind="assistant", status="delta", text="旧输出"),
        )

        self.assertEqual(agent.reset_count, 1)
        self.assertEqual(app._render_timeline_text(), "No messages yet.")
        self.assertEqual(app._render_queue_tray_text(), "")

    def test_stale_turn_event_is_ignored_after_new_session(self) -> None:
        """新会话后到达的旧轮次事件不应污染当前界面。"""

        app = AgentWorkbenchApp(agent=_FakeStreamingAgent([]))
        app._enqueue_turn("旧消息")
        app._active_turn = app._pending_turns.popleft()
        app._refresh_turn_queue_metadata()
        old_turn_id = app._active_turn.turn_id  # type: ignore[union-attr]

        app.action_new_session()
        app._apply_agent_event_for_turn(
            old_turn_id,
            AgentEvent(kind="assistant", status="delta", text="旧输出"),
        )

        self.assertEqual(app._render_timeline_text(), "No messages yet.")

    async def test_failed_tool_hides_traceback_but_keeps_internal_detail(self) -> None:
        """工具失败时主 timeline 不应直接展示 traceback，但内部 detail 仍应保留。"""

        traceback_text = "Traceback (most recent call last):\n  ...\nValueError: boom"
        agent = _FakeStreamingAgent(
            [
                AgentEvent(
                    kind="tool",
                    status="started",
                    name="fileglide_edit_text",
                    data={"tool_use_id": "tool-2"},
                ),
                AgentEvent(
                    kind="tool",
                    status="failed",
                    name="fileglide_edit_text",
                    duration_ms=3,
                    text="boom",
                    data={
                        "tool_use_id": "tool-2",
                        "error": "boom",
                        "output": {
                            "preview": "Error: boom",
                            "detail": traceback_text,
                            "model_text": "Error: boom",
                        },
                    },
                ),
            ]
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            app.on_input_submitted(
                type(
                    "FakeSubmittedEvent",
                    (),
                    {"input": input_widget, "value": "写文件"},
                )()
            )
            await pilot.pause(0.35)
            text = app._render_timeline_text()

        tool_item = [item for item in app._items if item.kind == "tool"][-1]
        tool_line = next(
            line for line in text.splitlines() if "Tool fileglide_edit_text" in line
        )
        self.assertRegex(
            tool_line,
            r"^\d+\.\d{2}s · \{ Tool fileglide_edit_text · Failed \} · Error: boom$",
        )
        self.assertNotIn("Traceback (most recent call last):", text)
        self.assertEqual(tool_item.detail, traceback_text)

    async def test_failed_system_message_is_summarized_but_raw_text_is_retained(self) -> None:
        """系统失败消息应做摘要展示，同时保留原始异常文本。"""

        traceback_text = "Traceback (most recent call last):\n  ...\nRuntimeError: boom"
        agent = _FakeStreamingAgent(
            [AgentEvent(kind="system", status="failed", text=traceback_text)]
        )
        app = AgentWorkbenchApp(agent=agent)

        async with app.run_test() as pilot:
            input_widget = app.query_one("#chat-input", Input)
            app.on_input_submitted(
                type(
                    "FakeSubmittedEvent",
                    (),
                    {"input": input_widget, "value": "你好"},
                )()
            )
            await pilot.pause(0.35)
            text = app._render_timeline_text()

        system_item = next(item for item in app._items if item.kind == "system")
        self.assertIn("SmartIPO · RuntimeError: boom", text)
        self.assertNotIn("Traceback (most recent call last):", text)
        self.assertEqual(system_item.metadata.get("raw_text"), traceback_text)


if __name__ == "__main__":
    unittest.main()
