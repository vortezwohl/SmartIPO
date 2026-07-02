"""基于 Textual 的本地 agent workbench。

该文件只负责界面层：单会话输入、时间线渲染、流式 assistant 输出，以及
运行中活动的本地动画表现。事件解释和时间线归约统一由 core timeline 层承担。
"""

from __future__ import annotations

import os
from typing import Any

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Footer, Header, Input, Static

from src.core.agent import Agent
from src.core.events import LoopEvent
from src.core.timeline import ConversationTimeline, TimelineEntry
from src.service.model_hub import create_default_brain_model
from src.tool.registry import build_default_tool_registry


DEFAULT_SYSTEM_PROMPT = """
你是 SmartIPO 的本地 coding agent。
- 接到一个任务后要自己连续规划并调用工具，直到任务自然结束。
- 优先使用 fileglide 完成读取、搜索、写入、移动等本地文件系统操作。
- 先读再改，避免无根据猜测。
- 工具失败时要直接暴露失败，不要伪装成成功。
""".strip()


def build_default_agent(event_sink) -> Agent:
    """构造默认本地主脑控制器。"""

    return Agent(
        model=create_default_brain_model(),
        tool_registry=build_default_tool_registry(),
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        event_sink=event_sink,
        workspace_root=os.getcwd(),
    )


class AgentWorkbenchApp(App[None]):
    """运行 SmartIPO 本地 agent 的单列时间线工作台。"""

    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
        padding: 1;
    }

    #status-banner {
        height: auto;
        padding: 0 1 1 1;
    }

    #timeline-scroll {
        height: 1fr;
        border: round $surface;
        padding: 1;
    }

    #timeline-view {
        width: 1fr;
        height: auto;
    }

    #chat-input {
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_session", "新会话"),
    ]

    def __init__(self, *, session_loop: Any | None = None) -> None:
        """初始化工作台。"""

        super().__init__()
        self._timeline = ConversationTimeline()
        self._status_message = "工作台已就绪。"
        self._session_loop = session_loop or build_default_agent(
            self._dispatch_runtime_event
        )

    def compose(self) -> ComposeResult:
        """构建 TUI 布局。"""

        yield Header()
        with Vertical(id="body"):
            yield Static(id="status-banner")
            with VerticalScroll(id="timeline-scroll"):
                yield Static(id="timeline-view")
            yield Input(
                placeholder="输入一个任务，agent 会自行调用工具完成。",
                id="chat-input",
            )
        yield Footer()

    def on_mount(self) -> None:
        """挂载后刷新界面并开始计时。"""

        self._refresh_view()
        self.set_interval(0.1, self._refresh_running_timeline)
        self.call_after_refresh(self._focus_chat_input)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """把输入框内容提交给会话 loop。"""

        prompt = event.value.strip()
        event.input.value = ""
        if not prompt:
            return
        self._timeline.append_user_message(prompt)
        self._render_timeline()
        self._run_turn_worker(prompt)

    def action_new_session(self) -> None:
        """清空界面并重建当前内存会话。"""

        self._session_loop.reset()
        self._timeline.reset()
        self._status_message = "已创建新会话。"
        self._refresh_view()

    @work(thread=True, exclusive=True, group="agent", exit_on_error=False)
    def _run_turn_worker(self, prompt: str) -> None:
        """在后台线程中执行一轮会话。"""

        try:
            self._session_loop.run(prompt)
        except Exception as error:  # pragma: no cover
            self.call_from_thread(self._show_error, f"处理失败: {error}")

    def _dispatch_runtime_event(self, event: LoopEvent) -> None:
        """把后台线程事件桥接回 Textual 主线程。"""

        self.call_from_thread(self._apply_loop_event, event)

    def _apply_loop_event(self, event: LoopEvent) -> None:
        """把一条运行时事件应用到时间线。"""

        self._timeline.apply_event(event)
        channel = event.channel
        event_type = event.event_type
        payload = event.payload
        if channel == "assistant" and event_type == "assistant_stream_started":
            self._status_message = payload.get("message", "正在生成回复。")
            self._refresh_view()
            return
        if channel == "assistant" and event_type == "assistant_stream_delta":
            self._render_timeline()
            return
        if channel == "assistant" and event_type == "assistant_stream_completed":
            self._status_message = "回复完成。"
            self._refresh_view()
            return
        if channel == "assistant" and event_type == "assistant_stream_failed":
            self._show_error(str(payload.get("message", "回复失败。")))
            return
        if channel == "progress" and event_type == "thinking_started":
            self._status_message = "thinking"
            self._refresh_view()
            return
        if channel == "progress" and event_type == "thinking_completed":
            self._render_timeline()
            return
        if channel == "progress" and event_type == "thinking_failed":
            self._status_message = str(payload.get("message", "思考失败。"))
            self._refresh_view()
            return
        if channel == "progress" and event_type in {"tool_started", "tool_completed", "tool_failed"}:
            self._status_message = str(payload.get("message", self._status_message))
            self._refresh_view()

    def _show_error(self, message: str) -> None:
        """在时间线中展示错误。"""

        self._timeline.append_system_message("处理失败", message, status="error")
        self._status_message = message
        self._refresh_view()

    def _render_timeline(self) -> None:
        """刷新主时间线区域。"""

        try:
            timeline_widget = self.query_one("#timeline-view", Static)
            scroll_widget = self.query_one("#timeline-scroll", VerticalScroll)
        except NoMatches:
            return
        should_follow = self._should_follow_scroll(scroll_widget)
        timeline_widget.update(Text(self._render_timeline_text()))
        if should_follow:
            scroll_widget.scroll_end(animate=False)

    def _refresh_running_timeline(self) -> None:
        """刷新仍在运行中的计时项目。"""

        if self._timeline.refresh_running_durations():
            self._render_timeline()

    def _refresh_view(self) -> None:
        """刷新顶部状态和时间线。"""

        try:
            self.query_one("#status-banner", Static).update(Text(self._render_status_banner()))
        except NoMatches:
            return
        self._render_timeline()

    def _render_status_banner(self) -> str:
        """渲染顶部状态摘要。"""

        turn_count = len(getattr(self._session_loop, "history", ())) // 2
        return (
            "[SmartIPO Agent Workbench]\n"
            f"turns: {turn_count}\n"
            f"status: {self._status_message}"
        )

    def _render_timeline_text(self) -> str:
        """把时间线项目渲染为文本。"""

        entries = self._timeline.entries
        if not entries:
            return "还没有消息。"
        return "\n\n".join(self._format_timeline_item(item) for item in entries)

    def _format_timeline_item(self, item: TimelineEntry) -> str:
        """把一条时间线项目格式化为可读文本。"""

        if item.kind in {"user", "assistant", "system"}:
            return f"{item.title}: {item.body}"
        if item.kind == "thinking":
            return f"{item.title}: [{self._thinking_label(item)} {self._format_duration(item.duration_ms)}]"
        header = f"[{item.title} | {self._format_status_label(item.status)} | {self._format_duration(item.duration_ms)}]"
        lines = [header]
        if item.body:
            lines.append(item.body)
        if item.preview:
            lines.append(f"概要: {item.preview}")
        if item.detail:
            if item.collapsible and item.collapsed:
                lines.append("结果: [详细结果已收起]")
            elif item.detail != item.preview or not item.preview:
                lines.append(f"结果: {item.detail}")
        return "\n".join(lines)

    def _focus_chat_input(self) -> None:
        """让输入框在启动后获得焦点。"""

        self.query_one("#chat-input", Input).focus()

    @staticmethod
    def _format_status_label(status: str) -> str:
        """把内部状态映射为用户可读文案。"""

        if status == "running":
            return "进行中"
        if status == "error":
            return "失败"
        return "完成"

    @staticmethod
    def _format_duration(duration_ms: int) -> str:
        """把毫秒时长格式化为秒。"""

        return f"{duration_ms / 1000:.2f}s"

    @staticmethod
    def _thinking_label(item: TimelineEntry) -> str:
        """把 thinking 基础文本渲染为本地动画。"""

        if item.status != "running":
            return item.body
        cycle = (item.duration_ms // 350) % 3
        suffix = (".", "..", "...")[cycle]
        return f"{item.body} {suffix}"

    @staticmethod
    def _should_follow_scroll(scroll_widget: VerticalScroll) -> bool:
        """仅当用户靠近底部时才自动跟随。"""

        return (scroll_widget.max_scroll_y - scroll_widget.scroll_y) <= 2
