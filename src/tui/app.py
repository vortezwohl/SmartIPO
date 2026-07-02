"""基于 Textual 的本地 agent workbench。

该文件只负责界面层：单会话输入、时间线展示、流式 assistant 输出，以及
思考/工具过程的可视化。业务逻辑仍然由公开 `Agent` 和工具层承担。
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
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
from src.service.model_hub import create_default_brain_model
from src.tool.registry import build_default_tool_registry


DEFAULT_SYSTEM_PROMPT = """
你是 SmartIPO 的本地 coding agent。
- 接到一个任务后要自己连续规划并调用工具，直到任务自然结束。
- 优先使用 fileglide 完成读取、搜索、写入、移动等本地文件系统操作。
- 先读再改，避免无根据猜测。
- 工具失败时要直接暴露失败，不要伪装成成功。
""".strip()


TOOL_KIND_LABELS = {
    "native": "工具",
    "fileglide": "文件工具",
}


@dataclass(slots=True)
class TimelineItem:
    """表示时间线中的一条可视项目。"""

    key: str
    kind: str
    title: str
    body: str
    detail: str = ""
    status: str = "done"
    duration_ms: int = 0
    started_at: float | None = None


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
        self._timeline_items: list[TimelineItem] = []
        self._thinking_item_key: str | None = None
        self._stream_item_key: str | None = None
        self._running_tool_keys: dict[str, str] = {}
        self._status_message = "工作台已就绪。"
        self._item_counter = 0
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
        self._append_timeline_item("user", "你", prompt)
        self._run_turn_worker(prompt)

    def action_new_session(self) -> None:
        """清空界面并重建当前内存会话。"""

        self._session_loop.reset()
        self._timeline_items = []
        self._thinking_item_key = None
        self._stream_item_key = None
        self._running_tool_keys = {}
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

        channel = event.channel
        event_type = event.event_type
        payload = event.payload
        if channel == "assistant" and event_type == "assistant_stream_started":
            self._status_message = payload.get("message", "正在生成回复。")
            self._refresh_view()
            return
        if channel == "assistant" and event_type == "assistant_stream_delta":
            self._remove_thinking_placeholder()
            self._append_stream_delta(str(payload.get("text", "")))
            return
        if channel == "assistant" and event_type == "assistant_stream_completed":
            self._complete_stream()
            self._status_message = "回复完成。"
            self._refresh_view()
            return
        if channel == "assistant" and event_type == "assistant_stream_failed":
            self._show_error(str(payload.get("message", "回复失败。")))
            return
        if channel == "progress" and event_type == "thinking_started":
            self._start_thinking_item(str(payload.get("message", "正在思考下一步。")))
            self._status_message = str(payload.get("message", "正在思考下一步。"))
            self._refresh_view()
            return
        if channel == "progress" and event_type == "thinking_completed":
            self._remove_thinking_placeholder()
            return
        if channel == "progress" and event_type == "thinking_failed":
            self._fail_thinking_item(str(payload.get("message", "思考失败。")))
            self._status_message = str(payload.get("message", "思考失败。"))
            self._refresh_view()
            return
        if channel == "progress" and event_type in {"tool_started", "tool_completed", "tool_failed"}:
            if event_type == "tool_started":
                self._remove_thinking_placeholder()
            self._apply_tool_event(event_type, payload)
            self._status_message = str(payload.get("message", self._status_message))
            self._refresh_view()

    def _append_stream_delta(self, delta: str) -> None:
        """把 assistant 增量文本追加到当前流式项目。"""

        if not delta:
            return
        item = self._get_timeline_item(self._stream_item_key or "")
        if item is None:
            self._stream_item_key = self._append_timeline_item(
                "assistant",
                "AI",
                delta,
            )
        else:
            item.body += delta
            self._render_timeline()

    def _complete_stream(self) -> None:
        """标记当前流式 assistant 项目完成。"""

        item = self._get_timeline_item(self._stream_item_key or "")
        if item is not None:
            item.status = "done"
        self._stream_item_key = None
        self._render_timeline()

    def _start_thinking_item(self, message: str) -> None:
        """显示一个运行中的思考占位。"""

        if self._thinking_item_key is not None:
            return
        self._thinking_item_key = self._append_timeline_item(
            "thinking",
            "思考中",
            message,
            status="running",
            started_at=time.perf_counter(),
        )

    def _remove_thinking_placeholder(self) -> None:
        """在输出或工具阶段到来后移除思考占位。"""

        if self._thinking_item_key is None:
            return
        self._timeline_items = [
            item
            for item in self._timeline_items
            if item.key != self._thinking_item_key
        ]
        self._thinking_item_key = None
        self._render_timeline()

    def _fail_thinking_item(self, message: str) -> None:
        """把当前思考占位标记为失败。"""

        item = self._get_timeline_item(self._thinking_item_key or "")
        if item is None:
            return
        item.body = message
        item.status = "error"
        item.duration_ms = self._current_duration_ms(item)
        item.started_at = None
        self._thinking_item_key = None
        self._render_timeline()

    def _apply_tool_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """把工具事件映射为时间线卡片。"""

        tool_name = str(payload.get("tool_name", "tool"))
        item = self._get_timeline_item(self._running_tool_keys.get(tool_name, ""))
        title = self._format_tool_title(payload)
        if event_type == "tool_started":
            key = self._append_timeline_item(
                "tool",
                title,
                str(payload.get("message", "")).strip(),
                status="running",
                started_at=time.perf_counter(),
            )
            self._running_tool_keys[tool_name] = key
            return
        if item is None:
            key = self._append_timeline_item(
                "tool",
                title,
                str(payload.get("message", "")).strip(),
                detail=str(payload.get("result_summary", "")).strip(),
                status="done" if event_type == "tool_completed" else "error",
                duration_ms=int(payload.get("duration_ms", 0) or 0),
            )
            self._running_tool_keys.pop(tool_name, None)
            if event_type == "tool_started":
                self._running_tool_keys[tool_name] = key
            return
        item.title = title
        item.body = str(payload.get("message", "")).strip() or item.body
        item.detail = str(payload.get("result_summary", "")).strip() or item.detail
        item.status = "done" if event_type == "tool_completed" else "error"
        item.duration_ms = int(payload.get("duration_ms", 0) or self._current_duration_ms(item))
        item.started_at = None
        self._running_tool_keys.pop(tool_name, None)
        self._render_timeline()

    def _show_error(self, message: str) -> None:
        """在时间线中展示错误。"""

        self._append_timeline_item(
            "system",
            "处理失败",
            message,
            status="error",
        )
        self._status_message = message
        self._refresh_view()

    def _append_timeline_item(
        self,
        kind: str,
        title: str,
        body: str,
        *,
        detail: str = "",
        status: str = "done",
        duration_ms: int = 0,
        started_at: float | None = None,
    ) -> str:
        """向时间线末尾追加一项。"""

        key = self._next_item_key(kind)
        self._timeline_items.append(
            TimelineItem(
                key=key,
                kind=kind,
                title=title,
                body=body,
                detail=detail,
                status=status,
                duration_ms=duration_ms,
                started_at=started_at,
            )
        )
        self._render_timeline()
        return key

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

        changed = False
        for item in self._timeline_items:
            if item.started_at is None:
                continue
            new_duration = self._current_duration_ms(item)
            if new_duration != item.duration_ms:
                item.duration_ms = new_duration
                changed = True
        if changed:
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

        if not self._timeline_items:
            return "还没有消息。"
        return "\n\n".join(self._format_timeline_item(item) for item in self._timeline_items)

    def _format_timeline_item(self, item: TimelineItem) -> str:
        """把一条时间线项目格式化为可读文本。"""

        if item.kind in {"user", "assistant"}:
            return f"{item.title}: {item.body}"
        if item.kind == "thinking":
            return f"AI: [思考中 {self._format_duration(item.duration_ms)}] {item.body}"
        header = f"[{item.title} | {self._format_status_label(item.status)} | {self._format_duration(item.duration_ms)}]"
        lines = [header]
        if item.body:
            lines.append(item.body)
        if item.detail:
            lines.append(f"概要: {item.detail}")
        return "\n".join(lines)

    def _get_timeline_item(self, key: str) -> TimelineItem | None:
        """按 key 查找一条时间线项目。"""

        for item in self._timeline_items:
            if item.key == key:
                return item
        return None

    def _next_item_key(self, prefix: str) -> str:
        """生成稳定递增的项目 key。"""

        self._item_counter += 1
        return f"{prefix}-{self._item_counter}"

    def _focus_chat_input(self) -> None:
        """让输入框在启动后获得焦点。"""

        self.query_one("#chat-input", Input).focus()

    @staticmethod
    def _format_tool_title(payload: dict[str, Any]) -> str:
        """把工具事件负载格式化为标题。"""

        kind = TOOL_KIND_LABELS.get(str(payload.get("tool_kind", "")), "工具")
        display_name = str(payload.get("display_name", "Tool"))
        return f"{kind} · {display_name}"

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
    def _should_follow_scroll(scroll_widget: VerticalScroll) -> bool:
        """仅当用户靠近底部时才自动跟随。"""

        return (scroll_widget.max_scroll_y - scroll_widget.scroll_y) <= 2

    @staticmethod
    def _current_duration_ms(item: TimelineItem) -> int:
        """计算运行中项目当前已消耗时长。"""

        if item.started_at is None:
            return item.duration_ms
        return int((time.perf_counter() - item.started_at) * 1000)
