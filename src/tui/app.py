"""基于 Textual 的 EasyHarness 本地 agent 工作台。

该文件只负责界面层：接收用户输入、消费 `easyharness.AgentEvent` 流、
维护本地展示态并渲染单列会话记录。运行时、工具合同和事件事实来源均由
EasyHarness 提供，本文件不得重新定义跨 UI 共享的 runtime 或 timeline 协议。
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import time
from typing import Any

from easyharness import AgentEvent
from rich.align import Align
from rich.console import Group
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult, ScreenStackError, SystemCommand
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual import events
from textual.screen import Screen
from textual.worker import Worker, get_current_worker
from textual.widgets import Footer, Header, Input, Static
from vortezwohl.nlp import LevenshteinDistance

from src.agent import (
    DEFAULT_AGENT_BRAND,
    DEFAULT_OPENING_MESSAGE,
    build_default_agent,
)

_TIMELINE_REFRESH_INTERVAL_SECONDS = 0.003
_CHAT_PREFIX_STYLE = "bold #d8ffe0"
_THINKING_HISTORY_PREFIX_STYLE = "bold #91ab97"
_THINKING_HISTORY_BODY_STYLE = "#b2bbb3"
_TIMING_STYLE = "#7e9b84"
_THINKING_STYLE = "bold #88ad8f"
_LOW_EMPHASIS_STYLE = _THINKING_STYLE
_TOOL_LABEL_STYLE = "bold #a8c1ae"
_TOOL_TEXT_STYLE = "#d3ded5"
_THINKING_STATE_KEY = "thinking_state"
_THINKING_PLACEHOLDER_STATE = "placeholder"
_THINKING_HISTORY_STATE = "history"
_THINKING_ANIMATION_FRAME_DURATION_MS = 128
_THINKING_ANIMATION_FRAMES = ("...", ".", "..")
_PLACEHOLDER_MIN_VISIBLE_DURATION_MS = 128
_PLACEHOLDER_MIN_VISIBLE_UNTIL_KEY = "placeholder_min_visible_until"
_TEXT_REVEAL_TARGET_KEY = "text_reveal_target"
_PENDING_TEXT_TERMINAL_STATUS_KEY = "pending_text_terminal_status"
_PENDING_TEXT_TERMINAL_DURATION_KEY = "pending_text_terminal_duration_ms"
_LOCAL_STARTED_MONOTONIC_KEY = "local_started_monotonic"
_PENDING_TERMINAL_DURATION_KEY = "pending_terminal_duration_ms"
_SUPPORTED_COMMANDS = ("/stop", "/new", "/help")
_COMMAND_HELP_TEXT = (
    "Available commands: /stop interrupts the active reply, /new starts a new session, /help shows this help."
)
_INPUT_PLACEHOLDER = (
    f"Ask {DEFAULT_AGENT_BRAND} for valuation, IPO, or market-data research. "
    "/stop interrupts, /new resets, /help shows commands."
)
_LOCKED_THEME_NAME = "ansi-dark"


@dataclass(slots=True)
class _TimelineItem:
    """TUI 本地展示项，不作为跨层运行时合同导出。"""

    key: str
    kind: str
    title: str
    body: str = ""
    status: str = "completed"
    name: str = ""
    preview: str = ""
    detail: str = ""
    started_at: datetime | None = None
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class _PendingTurn:
    """描述一条待执行或正在执行的用户提交。"""

    turn_id: str
    prompt: str
    user_item_key: str = ""


@dataclass(slots=True)
class _QueuedTurnEvent:
    """描述尚未进入可见时间线的原始 agent 事件。"""

    turn_id: str
    event: AgentEvent


@dataclass(slots=True)
class _TextRevealChunk:
    """描述等待按节拍逐字符吐出的文本片段。"""

    turn_id: str | None
    item_key: str
    text: str


class AgentWorkbenchApp(App[None]):
    """运行 OpenBuffett EasyHarness agent 的单列本地工作台。"""

    TITLE = DEFAULT_AGENT_BRAND
    SUB_TITLE = ""

    CSS = """
    Screen {
        layout: vertical;
        color: white;
        background: #1f1f1f;
    }

    Header {
        background: #123225;
        color: white;
        width: 1fr;
    }

    #body {
        height: 1fr;
        width: 1fr;
        min-width: 0;
        padding: 0 1;
        background: #1f1f1f;
    }

    #status-banner {
        height: auto;
        width: 1fr;
        min-width: 0;
        padding: 0 1;
        color: white;
        background: #1f1f1f;
        border: round #d8ffe0;
    }

    #timeline-scroll {
        height: 1fr;
        width: 1fr;
        min-width: 0;
        border: round #d8ffe0;
        color: white;
        padding: 0 1;
        background: #1f1f1f;
    }

    #timeline-view {
        width: 1fr;
        min-width: 0;
        height: auto;
    }

    #queue-tray {
        height: auto;
        width: 1fr;
        min-width: 0;
        margin-top: 1;
        padding: 0 1;
        color: white;
        background: #1f1f1f;
        border: round #effff1;
    }

    #chat-input {
        width: 1fr;
        min-width: 0;
        margin-top: 1;
        color: white;
        background: #1f1f1f;
        border: round #effff1;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_session", "New session"),
        Binding("tab,ctrl+i", "autocomplete_command", show=False, priority=True),
    ]

    def __init__(self, *, agent: Any | None = None) -> None:
        """初始化工作台。

        Args:
            agent: 可选 EasyHarness agent 兼容对象；测试可注入假对象。
        """

        super().__init__()
        self.theme = _LOCKED_THEME_NAME
        self._agent = agent or build_default_agent()
        self._items: list[_TimelineItem] = []
        self._item_counter = 0
        self._turn_count = 0
        self._turn_serial = 0
        self._status_message = f"{DEFAULT_AGENT_BRAND} ready."
        self._active_by_kind: dict[str, str] = {}
        self._active_tools: dict[str, str] = {}
        self._active_compress_key = ""
        self._pending_tool_terminal_durations: dict[str, int] = {}
        self._pending_tool_terminal_lock = threading.Lock()
        self._pending_turns: deque[_PendingTurn] = deque()
        self._pending_display_events: deque[_QueuedTurnEvent] = deque()
        self._pending_text_reveal_queue: deque[_TextRevealChunk] = deque()
        self._active_turn: _PendingTurn | None = None
        self._active_worker: Worker[None] | None = None
        self._raw_stream_done_turn_id: str | None = None
        self._stopping_turn_id: str | None = None
        self._cancelled_turn_id: str | None = None
        self._full_repaint_scheduled = False
        self._pending_repaint_force_follow = False
        self._command_matcher = LevenshteinDistance(ignore_case=True)

    def compose(self) -> ComposeResult:
        """构建 TUI 布局。"""

        yield Header()
        with Vertical(id="body"):
            yield Static(id="status-banner")
            with VerticalScroll(id="timeline-scroll"):
                yield Static(id="timeline-view")
            yield Static(id="queue-tray")
            yield Input(
                placeholder=_INPUT_PLACEHOLDER,
                id="chat-input",
            )
        yield Footer()

    def on_mount(self) -> None:
        """挂载后刷新界面并启动本地运行态计时。"""

        self._enforce_locked_theme()
        self._append_opening_message()
        self._run_full_repaint(force_follow=True)
        self.set_interval(
            _TIMELINE_REFRESH_INTERVAL_SECONDS,
            self._refresh_running_items,
        )
        self.call_after_refresh(self._focus_chat_input)

    def on_resize(self, event: events.Resize) -> None:
        """在终端尺寸变化后强制按新布局重绘本地视图。"""

        self._enforce_locked_theme()
        self._schedule_full_repaint()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """把输入框内容提交给 EasyHarness agent。"""

        prompt = event.value.strip()
        event.input.value = ""
        if not prompt:
            return
        if self._handle_slash_command(prompt):
            self._refresh_view(force_follow=True)
            return
        self._enqueue_turn(prompt)
        self._start_next_turn_if_idle()
        self._refresh_view(force_follow=True)

    def on_key(self, event: events.Key) -> None:
        """在输入框聚焦时拦截 Tab，用于 slash 命令补全。"""

        if event.key != "tab":
            return
        try:
            input_widget = self.query_one("#chat-input", Input)
        except (NoMatches, ScreenStackError):
            return
        if not input_widget.has_focus:
            return
        if self._autocomplete_command_input(input_widget):
            event.prevent_default()
            event.stop()

    def action_autocomplete_command(self) -> None:
        """通过高优先级 binding 触发 slash 命令补全。"""

        try:
            input_widget = self.query_one("#chat-input", Input)
        except (NoMatches, ScreenStackError):
            return
        if not input_widget.has_focus:
            return
        self._autocomplete_command_input(input_widget)

    def action_new_session(self) -> None:
        """清空界面并重置当前 EasyHarness 会话。"""

        self._request_runtime_cancel()
        self._cancel_active_worker()
        reset = getattr(self._agent, "reset", None)
        if callable(reset):
            reset()
        self._items = []
        self._item_counter = 0
        self._turn_count = 0
        self._active_by_kind.clear()
        self._active_tools.clear()
        self._active_compress_key = ""
        self._pending_turns.clear()
        self._pending_display_events.clear()
        self._pending_text_reveal_queue.clear()
        self._active_turn = None
        self._active_worker = None
        self._raw_stream_done_turn_id = None
        self._stopping_turn_id = None
        self._cancelled_turn_id = None
        self._status_message = f"Started a new {DEFAULT_AGENT_BRAND} session."
        self._append_opening_message()
        self._refresh_view()

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        """移除内建主题切换命令，避免向用户暴露换肤入口。"""

        for command in super().get_system_commands(screen):
            if command.title == "Theme":
                continue
            yield command

    def action_change_theme(self) -> None:
        """锁定主题后忽略内建主题搜索入口。"""

        self._enforce_locked_theme()

    def search_themes(self) -> None:
        """锁定主题后禁止打开主题切换面板。"""

        self._enforce_locked_theme()

    def action_toggle_dark(self) -> None:
        """锁定主题后忽略明暗主题切换动作。"""

        self._enforce_locked_theme()

    @work(thread=True, group="agent", exit_on_error=False)
    def _run_turn_worker(self, turn_id: str, prompt: str) -> None:
        """在后台线程中执行一轮流式会话。"""

        try:
            worker = get_current_worker()
            for event in self._agent.stream(prompt):
                if worker.is_cancelled:
                    return
                self._record_pending_tool_terminal_event(event)
                self.call_from_thread(self._enqueue_agent_event_for_turn, turn_id, event)
            if worker.is_cancelled:
                return
            self.call_from_thread(self._mark_turn_stream_complete, turn_id)
        except Exception as error:  # pragma: no cover
            self.call_from_thread(self._show_error, turn_id, f"Request failed: {error}")

    def _enqueue_agent_event_for_turn(self, turn_id: str, event: AgentEvent) -> None:
        """把当前活跃 turn 的原始事件排入显示层队列。"""

        if not self._is_active_turn(turn_id):
            return
        self._pending_display_events.append(
            _QueuedTurnEvent(
                turn_id=turn_id,
                event=event,
            )
        )
        self._process_display_pipeline(allow_reveal=False)

    def _mark_turn_stream_complete(self, turn_id: str) -> None:
        """标记当前 turn 的原始事件流已经结束，等待显示层排空后再收尾。"""

        if not self._is_active_turn(turn_id):
            return
        self._raw_stream_done_turn_id = turn_id
        self._try_complete_active_turn()

    def _apply_agent_event_for_turn(self, turn_id: str, event: AgentEvent) -> None:
        """兼容旧测试入口：仅在事件属于当前活跃轮次时应用显示层逻辑。"""

        if not self._is_active_turn(turn_id):
            return
        self._enqueue_agent_event_for_turn(turn_id, event)

    def _apply_agent_event(self, event: AgentEvent, *, refresh_view: bool = True) -> None:
        """把 EasyHarness 事件应用到 TUI 本地展示态。"""

        if event.status == "cancelled":
            self._mark_active_turn_cancelled()
        if event.kind == "thinking":
            self._apply_thinking_event(event)
        elif event.kind == "tool":
            self._apply_tool_event(event)
        elif event.kind == "assistant":
            self._apply_assistant_event(event)
        elif event.kind == "system":
            self._apply_system_event(event)
        elif event.kind == "compress":
            self._apply_compress_event(event)
        self._commit_ready_text_terminal_states()
        self._reconcile_waiting_feedback_after_event()
        self._status_message = self._format_event_status(event)
        if refresh_view:
            self._refresh_view()

    def _apply_thinking_event(self, event: AgentEvent) -> None:
        if event.status == "started":
            item = self._get_active_thinking_item()
            if item is None:
                self._active_by_kind["thinking"] = self._append_item(
                    kind="thinking",
                    title="thinking",
                    body="",
                    status="started",
                    started_at=self._parse_started_at(event.started_at),
                    metadata={
                        "ephemeral": True,
                        "history": False,
                        _THINKING_STATE_KEY: _THINKING_PLACEHOLDER_STATE,
                    },
                )
                item = self._get_active_thinking_item()
                if item is not None:
                    self._restart_local_running_timer(item)
                return
            item.status = "started"
            self._mark_thinking_as_placeholder(item, provisional=False)
            self._ensure_local_running_timer(item)
            return
        item = self._get_active_thinking_item()
        if item is None:
            key = self._append_item(
                kind="thinking",
                title="thinking",
                body="",
                status="started",
                started_at=self._parse_started_at(event.started_at),
                metadata={
                    "provisional": False,
                    "ephemeral": True,
                    "history": False,
                    _THINKING_STATE_KEY: _THINKING_PLACEHOLDER_STATE,
                },
            )
            self._active_by_kind["thinking"] = key
            item = self._get_item(key)
            if item is not None:
                self._restart_local_running_timer(item)
        if item is None:
            return
        thinking_text = self._normalize_thinking_text(event.text or "")
        if event.status == "delta":
            item.status = "delta"
            if thinking_text:
                self._queue_thinking_text_reveal(item, thinking_text, append=True)
            else:
                self._mark_thinking_as_placeholder(item, provisional=False)
            return
        if event.status in {"completed", "failed", "cancelled"}:
            self._sync_running_item_duration(item)
            if thinking_text:
                self._queue_thinking_text_reveal(item, thinking_text, append=False)
            self._set_pending_text_terminal(
                item,
                status=event.status,
                duration_ms=max(item.duration_ms, event.duration_ms or 0),
            )

    def _apply_tool_event(self, event: AgentEvent) -> None:
        self._remove_waiting_thinking_items()
        tool_key = self._tool_event_key(event)
        if event.status == "started":
            metadata = self._event_data_dict(event)
            item_key = self._append_item(
                kind="tool",
                title="",
                body="",
                name=event.name or "tool",
                status="started",
                started_at=self._parse_started_at(event.started_at),
                metadata=metadata,
            )
            if tool_key:
                self._active_tools[tool_key] = item_key
            item = self._get_item(item_key)
            if item is not None:
                self._restart_local_running_timer(item)
                self._sync_pending_tool_terminal_snapshot(item)
            return
        item_key = self._active_tools.get(tool_key, "") if tool_key else ""
        item = self._get_item(item_key)
        if item is None:
            key = self._append_item(
                kind="tool",
                title="",
                body="",
                name=event.name or "tool",
                status=event.status,
                metadata=self._event_data_dict(event),
            )
            item = self._get_item(key)
        if item is None:
            return
        item.status = event.status
        item.duration_ms = event.duration_ms or item.duration_ms
        item.started_at = None
        item.metadata.update(self._event_data_dict(event))
        self._clear_local_running_timer(item)
        output = self._extract_tool_output(event)
        item.preview = output.get("preview") or event.text or item.preview
        item.detail = output.get("detail") or output.get("model_text") or item.detail
        item.metadata.pop(_PENDING_TERMINAL_DURATION_KEY, None)
        self._clear_pending_tool_terminal_snapshot(event, item)
        if event.text and not item.preview:
            item.preview = event.text
        if event.status in {"completed", "failed", "cancelled"}:
            self._discard_active_tool_item_aliases(item.key)

    def _discard_active_tool_item_aliases(self, item_key: str) -> None:
        """移除一个工具项在活跃映射中的全部别名。"""

        for active_key, active_item_key in list(self._active_tools.items()):
            if active_item_key == item_key:
                self._active_tools.pop(active_key, None)

    def _apply_assistant_event(self, event: AgentEvent) -> None:
        if event.status in {"started", "delta", "completed", "cancelled"}:
            self._remove_waiting_thinking_items()
        if event.status == "started":
            self._active_by_kind["assistant"] = self._append_item(
                kind="assistant",
                title="Assistant > ",
                status="started",
                started_at=self._parse_started_at(event.started_at),
                metadata={_TEXT_REVEAL_TARGET_KEY: ""},
            )
            return
        item = self._get_item(self._active_by_kind.get("assistant", ""))
        if item is None and event.text:
            key = self._append_item(
                kind="assistant",
                title="Assistant > ",
                body="",
                status=event.status,
                started_at=self._parse_started_at(event.started_at),
            )
            item = self._get_item(key)
            self._active_by_kind["assistant"] = key
            if item is not None:
                self._set_text_reveal_target(item, "")
        if item is None:
            return
        if event.status == "delta" and event.text:
            self._queue_assistant_text_reveal(
                item,
                event.text,
                append=True,
            )
            return
        if event.status in {"completed", "failed", "cancelled"}:
            if event.text and (
                event.status != "cancelled"
                or not self._current_text_reveal_target(item)
            ):
                self._queue_assistant_text_reveal(
                    item,
                    event.text,
                    append=False,
                )
            self._set_pending_text_terminal(
                item,
                status=event.status,
                duration_ms=event.duration_ms or item.duration_ms,
            )

    def _apply_system_event(self, event: AgentEvent) -> None:
        body = event.text or ""
        metadata = self._event_data_dict(event)
        if event.status == "cancelled":
            body = "Interrupted."
            metadata["raw_text"] = event.text or ""
        elif event.status == "failed":
            metadata["raw_text"] = body
            body = self._summarize_error_text(body)
        self._append_item(
            kind="system",
            title=DEFAULT_AGENT_BRAND,
            body=body,
            status=event.status,
            started_at=self._parse_started_at(event.started_at),
            duration_ms=event.duration_ms or 0,
            metadata=metadata,
        )

    def _apply_compress_event(self, event: AgentEvent) -> None:
        self._remove_waiting_thinking_items()
        body = self._compress_activity_text(event.status, event.text or "")
        metadata = self._event_data_dict(event)
        if event.status == "failed":
            metadata["raw_text"] = event.text or ""
        if event.status == "started":
            item = self._get_item(self._active_compress_key)
            if item is None:
                self._active_compress_key = self._append_item(
                    kind="compress",
                    title="",
                    body=body,
                    status="started",
                    started_at=self._parse_started_at(event.started_at),
                    duration_ms=event.duration_ms or 0,
                    metadata=metadata,
                )
                item = self._get_item(self._active_compress_key)
                if item is not None:
                    self._restart_local_running_timer(item)
                return
            item.body = body
            item.status = "started"
            item.started_at = self._parse_started_at(event.started_at)
            item.duration_ms = event.duration_ms or item.duration_ms
            item.metadata.update(metadata)
            self._restart_local_running_timer(item)
            return

        item = self._get_item(self._active_compress_key)
        if item is None:
            self._active_compress_key = self._append_item(
                kind="compress",
                title="",
                body=body,
                status=event.status,
                started_at=None,
                duration_ms=event.duration_ms or 0,
                metadata=metadata,
            )
            item = self._get_item(self._active_compress_key)
        if item is None:
            return
        item.body = body
        item.status = event.status
        item.started_at = None
        item.duration_ms = event.duration_ms or item.duration_ms
        item.metadata.update(metadata)
        self._clear_local_running_timer(item)
        if event.status in {"completed", "failed", "cancelled"}:
            self._active_compress_key = ""

    def _complete_turn(self, turn_id: str) -> None:
        """标记一轮流式会话自然完成。"""

        if not self._is_active_turn(turn_id):
            return
        if self._is_cancelled_turn(turn_id):
            self._settle_running_turn_items("cancelled")
            self._remove_waiting_thinking_items()
            self._turn_count += 1
            self._finish_active_turn(
                queue_state="interrupted",
                status_message="Interrupted.",
            )
            return
        self._settle_running_turn_items("completed")
        self._remove_waiting_thinking_items()
        self._turn_count += 1
        self._finish_active_turn(queue_state="completed", status_message="Reply complete.")

    def _show_error(self, turn_id: str, message: str) -> None:
        """在本地展示态中追加错误消息。"""

        if not self._is_active_turn(turn_id):
            return
        self._clear_active_turn_display_pipeline()
        self._raw_stream_done_turn_id = None
        self._settle_running_turn_items("failed", message=message)
        self._remove_waiting_thinking_items()
        self._append_item(
            kind="system",
            title=DEFAULT_AGENT_BRAND,
            body=self._summarize_error_text(message),
            status="failed",
            metadata={"raw_text": message},
        )
        self._turn_count += 1
        self._finish_active_turn(
            queue_state="failed",
            status_message=self._summarize_error_text(message),
        )

    def _append_user_message(
        self,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """追加用户消息条目，可附带队列状态元数据。"""

        return self._append_item(
            kind="user",
            title="User > ",
            body=content,
            metadata=metadata,
        )

    def _append_assistant_message(
        self,
        content: str,
        *,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """追加助手消息条目，供欢迎语和静态历史消息复用。"""

        return self._append_item(
            kind="assistant",
            title="Assistant > ",
            body=content,
            status=status,
            metadata=metadata,
        )

    def _append_opening_message(self) -> None:
        """在空白会话中注入默认开场自介，避免等待用户先发第一句。"""

        if self._items:
            return
        self._append_streamed_static_assistant_message(
            DEFAULT_OPENING_MESSAGE,
            metadata={"opening_message": True},
        )

    def _append_streamed_static_assistant_message(
        self,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """追加一条静态 assistant 消息，并复用正常消息的逐字 reveal 管线。"""

        item_key = self._append_item(
            kind="assistant",
            title="Assistant > ",
            body="",
            status="completed",
            metadata=metadata,
        )
        item = self._get_item(item_key)
        if item is None:
            return item_key
        self._set_text_reveal_target(item, "")
        self._enqueue_text_reveal_suffix(
            item,
            previous_target="",
            next_target=content,
            stream_without_turn=True,
        )
        return item_key

    def _enforce_locked_theme(self) -> None:
        """把应用主题收口到唯一允许的 ansi-dark。"""

        if self.theme != _LOCKED_THEME_NAME:
            self.theme = _LOCKED_THEME_NAME

    def _schedule_full_repaint(self, *, force_follow: bool = False) -> None:
        """在当前 refresh 周期稳定后统一执行完整 repaint。"""

        self._pending_repaint_force_follow = (
            self._pending_repaint_force_follow or force_follow
        )
        if self._full_repaint_scheduled:
            return
        self._full_repaint_scheduled = True
        self.call_after_refresh(self._run_full_repaint)

    def _run_full_repaint(self, *, force_follow: bool | None = None) -> None:
        """执行 mount 与 resize 共用的完整布局和视图刷新。"""

        if force_follow is None:
            force_follow = self._pending_repaint_force_follow
        self._pending_repaint_force_follow = False
        self._full_repaint_scheduled = False
        self._refresh_view(schedule_follow=False)
        try:
            self.query_one("#body", Vertical).refresh(layout=True, repaint=True)
        except (NoMatches, ScreenStackError):
            self.refresh(layout=True, repaint=True)
        self._schedule_timeline_follow(force_follow=force_follow)

    def _start_local_thinking(self, *, enforce_min_visibility: bool = False) -> None:
        """在收到真实事件前先启动本地 thinking 占位与计时。"""

        if self._get_active_thinking_item() is not None:
            return
        metadata = {
            "provisional": True,
            "ephemeral": True,
            "history": False,
            _THINKING_STATE_KEY: _THINKING_PLACEHOLDER_STATE,
        }
        if enforce_min_visibility:
            metadata[_PLACEHOLDER_MIN_VISIBLE_UNTIL_KEY] = (
                time.perf_counter() + (_PLACEHOLDER_MIN_VISIBLE_DURATION_MS / 1000)
            )
        self._active_by_kind["thinking"] = self._append_item(
            kind="thinking",
            title="thinking",
            status="started",
            started_at=datetime.now(timezone.utc),
            metadata=metadata,
        )
        item = self._get_active_thinking_item()
        if item is not None:
            self._restart_local_running_timer(item)

    @staticmethod
    def _mark_thinking_as_placeholder(
        item: _TimelineItem,
        *,
        provisional: bool,
    ) -> None:
        """把 thinking 条目标记为 turn 空窗前置占位符。"""

        item.metadata[_THINKING_STATE_KEY] = _THINKING_PLACEHOLDER_STATE
        item.metadata["provisional"] = provisional
        item.metadata["ephemeral"] = True
        item.metadata["history"] = False
        item.metadata.pop(_TEXT_REVEAL_TARGET_KEY, None)
        item.metadata.pop(_PENDING_TEXT_TERMINAL_STATUS_KEY, None)
        item.metadata.pop(_PENDING_TEXT_TERMINAL_DURATION_KEY, None)

    def _promote_thinking_item_to_history(
        self,
        item: _TimelineItem,
        text: str,
        *,
        append: bool,
    ) -> None:
        """把收到真实文本的 thinking 条目升级为可保留历史。"""

        item.title = "Assistant (Thinking) > "
        item.body = self._merge_thinking_text(
            item.body,
            text,
            append=append,
        )
        item.metadata["ephemeral"] = False
        item.metadata["history"] = True
        item.metadata["provisional"] = False
        item.metadata[_THINKING_STATE_KEY] = _THINKING_HISTORY_STATE
        self._set_text_reveal_target(item, item.body)

    def _remove_waiting_thinking_items(self) -> None:
        """只移除仍然停留在 waiting-only 状态的 thinking 占位。"""

        active_item = self._get_active_thinking_item()
        if active_item is not None and self._is_waiting_thinking_item(active_item):
            self._active_by_kind.pop("thinking", None)
        self._items = [
            item
            for item in self._items
            if not self._is_waiting_thinking_item(item)
        ]

    def _enqueue_turn(self, prompt: str) -> None:
        """把一条用户提交加入本地执行队列。"""

        turn_id = self._next_turn_id()
        self._pending_turns.append(
            _PendingTurn(
                turn_id=turn_id,
                prompt=prompt,
            )
        )

    def _start_next_turn_if_idle(self) -> None:
        """若当前没有活跃轮次，则启动队首消息。"""

        if self._active_turn is not None or not self._pending_turns:
            return
        self._clear_all_pending_tool_terminal_snapshots()
        turn = self._pending_turns.popleft()
        self._active_turn = turn
        self._raw_stream_done_turn_id = None
        self._stopping_turn_id = None
        self._cancelled_turn_id = None
        turn.user_item_key = self._append_user_message(
            turn.prompt,
            metadata={
                "turn_id": turn.turn_id,
                "queue_state": "running",
                "queue_position": 0,
            },
        )
        self._refresh_turn_queue_metadata()
        self._start_local_thinking(enforce_min_visibility=True)
        self._status_message = "Processing queued message."
        self._refresh_view(force_follow=True)
        self._active_worker = self._run_turn_worker(turn.turn_id, turn.prompt)

    def _finish_active_turn(self, *, queue_state: str, status_message: str) -> None:
        """收尾当前活跃轮次，并在可能时启动下一条。"""

        if self._active_turn is None:
            return
        self._active_worker = None
        self._clear_all_pending_tool_terminal_snapshots()
        self._clear_active_turn_display_pipeline()
        item = self._get_item(self._active_turn.user_item_key)
        if item is not None:
            item.metadata["queue_state"] = queue_state
            item.metadata["queue_position"] = None
            item.status = "failed" if queue_state == "failed" else "completed"
        self._active_turn = None
        self._raw_stream_done_turn_id = None
        self._stopping_turn_id = None
        self._cancelled_turn_id = None
        self._refresh_turn_queue_metadata()
        self._status_message = status_message
        self._refresh_view(force_follow=True)
        self._start_next_turn_if_idle()

    def _clear_active_turn_display_pipeline(self) -> None:
        """清理当前活跃 turn 的显示层缓冲状态。"""

        if self._active_turn is None:
            self._pending_display_events.clear()
            self._pending_text_reveal_queue.clear()
            return
        turn_id = self._active_turn.turn_id
        self._pending_display_events = deque(
            event
            for event in self._pending_display_events
            if event.turn_id != turn_id
        )
        self._pending_text_reveal_queue = deque(
            chunk
            for chunk in self._pending_text_reveal_queue
            if chunk.turn_id != turn_id
        )

    def _try_complete_active_turn(self) -> bool:
        """仅在原始流和显示层都已排空时，才真正结束当前 turn。"""

        if self._active_turn is None:
            return False
        turn_id = self._active_turn.turn_id
        if self._raw_stream_done_turn_id != turn_id:
            return False
        if self._pending_display_events or self._pending_text_reveal_queue:
            return False
        if self._has_pending_text_terminal_states():
            return False
        self._complete_turn(turn_id)
        return True

    def _has_pending_text_terminal_states(self) -> bool:
        """判断当前活跃文本条目是否还有等待 reveal 排空后提交的终态。"""

        for kind in ("thinking", "assistant"):
            item = self._get_item(self._active_by_kind.get(kind, ""))
            if item is None:
                continue
            pending_status = str(
                item.metadata.get(_PENDING_TEXT_TERMINAL_STATUS_KEY, "")
            ).strip()
            if pending_status:
                return True
        return False

    def _refresh_turn_queue_metadata(self) -> None:
        """同步当前活跃条目与待处理条目的队列状态。"""

        if self._active_turn is not None:
            active_item = self._get_item(self._active_turn.user_item_key)
            if active_item is not None:
                active_item.metadata["queue_state"] = "running"
                active_item.metadata["queue_position"] = 0

    def _settle_running_turn_items(self, status: str, *, message: str = "") -> None:
        """收口当前仍处于 started 的展示项，避免失败后残留运行态。"""

        for key in list(self._active_by_kind.values()):
            item = self._get_item(key)
            if item is None or item.started_at is None:
                continue
            self._sync_running_item_duration(item)
            item.status = status
            item.started_at = None
            self._clear_local_running_timer(item)
        self._active_by_kind.clear()
        for key in list(self._active_tools.values()):
            item = self._get_item(key)
            if item is None:
                continue
            self._sync_running_item_duration(item)
            item.status = status
            item.started_at = None
            self._clear_local_running_timer(item)
            if message and "error" not in item.metadata:
                item.metadata["error"] = message
        self._active_tools.clear()
        if self._active_compress_key:
            item = self._get_item(self._active_compress_key)
            if item is not None and item.started_at is not None:
                self._sync_running_item_duration(item)
                item.status = status
                item.started_at = None
                self._clear_local_running_timer(item)
            if status in {"completed", "failed", "cancelled"}:
                self._active_compress_key = ""

    def _is_active_turn(self, turn_id: str) -> bool:
        """判断某个 turn_id 是否仍对应当前活跃轮次。"""

        return self._active_turn is not None and self._active_turn.turn_id == turn_id

    def _is_cancelled_turn(self, turn_id: str) -> bool:
        """判断当前 turn 是否已经收到 runtime cancelled 终态。"""

        return self._cancelled_turn_id == turn_id

    def _mark_active_turn_cancelled(self) -> None:
        """记录当前活跃 turn 已进入 cancelled 终态。"""

        if self._active_turn is None:
            return
        self._cancelled_turn_id = self._active_turn.turn_id

    def _next_turn_id(self) -> str:
        """生成当前会话内唯一的轮次编号。"""

        self._turn_serial += 1
        return f"turn-{self._turn_serial}"

    def _append_item(
        self,
        *,
        kind: str,
        title: str,
        body: str = "",
        status: str = "completed",
        name: str = "",
        preview: str = "",
        detail: str = "",
        started_at: datetime | None = None,
        duration_ms: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        self._item_counter += 1
        key = f"{kind}-{self._item_counter}"
        self._items.append(
            _TimelineItem(
                key=key,
                kind=kind,
                title=title,
                body=body,
                status=status,
                name=name,
                preview=preview,
                detail=detail,
                started_at=started_at,
                duration_ms=duration_ms,
                metadata=metadata or {},
            )
        )
        return key

    def _get_item(self, key: str) -> _TimelineItem | None:
        for item in self._items:
            if item.key == key:
                return item
        return None

    def _get_active_thinking_item(self) -> _TimelineItem | None:
        """返回当前仍处于活动中的 thinking 条目。"""

        key = self._active_by_kind.get("thinking", "")
        if not key:
            return None
        return self._get_item(key)

    @staticmethod
    def _sync_running_item_duration(item: _TimelineItem) -> None:
        """用当前 UTC 时间刷新单个运行中条目的本地耗时。"""

        if item.started_at is None:
            return
        duration_ms = AgentWorkbenchApp._running_item_duration_ms(item)
        item.duration_ms = max(0, duration_ms)

    def _refresh_running_items(self) -> None:
        """刷新仍处于 started 状态的本地展示时长。"""

        changed = False
        for item in self._items:
            if item.started_at is None:
                continue
            if item.kind == "tool":
                self._sync_pending_tool_terminal_snapshot(item)
            duration_ms = self._running_item_duration_ms(item)
            duration_ms = max(0, duration_ms)
            if duration_ms != item.duration_ms:
                item.duration_ms = duration_ms
                changed = True
        if self._process_display_pipeline():
            changed = True
        if self._try_complete_active_turn():
            changed = True
        if changed:
            self._render_timeline()

    def _process_display_pipeline(self, *, allow_reveal: bool = True) -> bool:
        """推进显示层事件回放、逐字符 reveal 与文本终态收口。"""

        changed = False
        if allow_reveal and self._advance_text_reveal():
            changed = True
        if self._drain_pending_display_events():
            changed = True
        if self._commit_ready_text_terminal_states():
            self._restore_waiting_thinking_if_turn_still_active()
            changed = True
        return changed

    def _drain_pending_display_events(self) -> bool:
        """按可见顺序回放等待中的原始 agent 事件。"""

        changed = False
        while self._pending_display_events:
            queued_event = self._pending_display_events[0]
            if not self._is_active_turn(queued_event.turn_id):
                self._pending_display_events.popleft()
                changed = True
                continue
            if self._pending_text_reveal_queue:
                break
            if self._should_delay_event_for_placeholder(queued_event.event):
                break
            self._pending_display_events.popleft()
            self._apply_agent_event(queued_event.event, refresh_view=False)
            changed = True
            if self._pending_text_reveal_queue:
                break
        return changed

    def _advance_text_reveal(self) -> bool:
        """每个刷新节拍最多吐出一个可见字符。"""

        if not self._pending_text_reveal_queue:
            return False
        chunk = self._pending_text_reveal_queue[0]
        if chunk.turn_id is not None and not self._is_active_turn(chunk.turn_id):
            self._pending_text_reveal_queue.popleft()
            return True
        item = self._get_item(chunk.item_key)
        if item is None or not chunk.text:
            self._pending_text_reveal_queue.popleft()
            return True
        item.body += chunk.text[0]
        remainder = chunk.text[1:]
        if remainder:
            chunk.text = remainder
        else:
            self._pending_text_reveal_queue.popleft()
        return True

    def _should_delay_event_for_placeholder(self, event: AgentEvent) -> bool:
        """判断当前事件是否需要等待 placeholder 最短可见时长结束后再显示。"""

        item = self._get_active_thinking_item()
        if item is None or not self._is_waiting_thinking_item(item):
            return False
        min_visible_until = item.metadata.get(_PLACEHOLDER_MIN_VISIBLE_UNTIL_KEY)
        if not isinstance(min_visible_until, (int, float)):
            return False
        if time.perf_counter() >= float(min_visible_until):
            item.metadata.pop(_PLACEHOLDER_MIN_VISIBLE_UNTIL_KEY, None)
            return False
        return event.kind in {"thinking", "assistant", "tool", "compress"}

    @staticmethod
    def _running_item_duration_ms(item: _TimelineItem) -> int:
        """优先使用本地单调时钟刷新运行中条目的耗时。"""

        pending_terminal_duration = item.metadata.get(_PENDING_TERMINAL_DURATION_KEY)
        if isinstance(pending_terminal_duration, int):
            return pending_terminal_duration
        local_started = item.metadata.get(_LOCAL_STARTED_MONOTONIC_KEY)
        if isinstance(local_started, (int, float)):
            return int((time.perf_counter() - float(local_started)) * 1000)
        if item.started_at is None:
            return item.duration_ms
        return int((datetime.now(timezone.utc) - item.started_at).total_seconds() * 1000)

    @staticmethod
    def _restart_local_running_timer(item: _TimelineItem) -> None:
        """为运行中的本地活动项重置单调计时起点。"""

        item.metadata[_LOCAL_STARTED_MONOTONIC_KEY] = time.perf_counter()

    @staticmethod
    def _ensure_local_running_timer(item: _TimelineItem) -> None:
        """为运行中的本地活动项补齐单调计时起点。"""

        item.metadata.setdefault(_LOCAL_STARTED_MONOTONIC_KEY, time.perf_counter())

    @staticmethod
    def _clear_local_running_timer(item: _TimelineItem) -> None:
        """清理运行态结束后的本地单调计时元数据。"""

        item.metadata.pop(_LOCAL_STARTED_MONOTONIC_KEY, None)

    def _reconcile_waiting_feedback_after_event(self) -> None:
        """在每次事件应用后统一协调 waiting `Thinking ...` 反馈。"""

        self._restore_waiting_thinking_if_turn_still_active()

    def _restore_waiting_thinking_if_turn_still_active(self) -> None:
        """在活跃 turn 出现无可见运行态空窗时回补本地 thinking 占位。"""

        if self._active_turn is None:
            return
        if self._stopping_turn_id == self._active_turn.turn_id:
            return
        if self._cancelled_turn_id == self._active_turn.turn_id:
            return
        if self._get_active_thinking_item() is not None:
            return
        if self._has_visible_running_activity():
            return
        self._start_local_thinking()

    @staticmethod
    def _is_visible_running_item(item: _TimelineItem | None) -> bool:
        """判断某个时间线项是否仍表示真实运行中活动。"""

        if item is None:
            return False
        if item.status in {"completed", "failed", "cancelled"}:
            return False
        if item.started_at is not None:
            return True
        if isinstance(item.metadata.get(_LOCAL_STARTED_MONOTONIC_KEY), (int, float)):
            return True
        return item.status in {"started", "delta"}

    def _record_pending_tool_terminal_event(self, event: AgentEvent) -> None:
        """在后台线程先登记 tool 终态耗时，避免主线程延迟时继续跑表。"""

        if event.kind != "tool":
            return
        if event.status not in {"completed", "failed", "cancelled"}:
            return
        if event.duration_ms is None:
            return
        aliases = self._tool_event_aliases(event)
        if not aliases:
            return
        with self._pending_tool_terminal_lock:
            for alias in aliases:
                self._pending_tool_terminal_durations[alias] = event.duration_ms

    def _sync_pending_tool_terminal_snapshot(self, item: _TimelineItem) -> None:
        """把后台已收到的 tool 终态耗时提前同步到本地 running 条目。"""

        if item.kind != "tool":
            return
        pending_duration = self._pending_tool_terminal_duration_for_item(item)
        if pending_duration is None:
            item.metadata.pop(_PENDING_TERMINAL_DURATION_KEY, None)
            return
        item.metadata[_PENDING_TERMINAL_DURATION_KEY] = pending_duration

    def _pending_tool_terminal_duration_for_item(
        self,
        item: _TimelineItem,
    ) -> int | None:
        """查找某个 tool 条目是否已有待应用的终态耗时。"""

        aliases = self._tool_item_aliases(item)
        if not aliases:
            return None
        with self._pending_tool_terminal_lock:
            for alias in aliases:
                pending_duration = self._pending_tool_terminal_durations.get(alias)
                if pending_duration is not None:
                    return pending_duration
        return None

    def _clear_pending_tool_terminal_snapshot(
        self,
        event: AgentEvent,
        item: _TimelineItem | None = None,
    ) -> None:
        """在 tool 终态正式应用后清理后台暂存的提前停表快照。"""

        aliases = set(self._tool_event_aliases(event))
        if item is not None:
            aliases.update(self._tool_item_aliases(item))
        if not aliases:
            return
        with self._pending_tool_terminal_lock:
            for alias in aliases:
                self._pending_tool_terminal_durations.pop(alias, None)

    def _clear_all_pending_tool_terminal_snapshots(self) -> None:
        """清空当前 turn 残留的 tool 终态提前停表快照。"""

        with self._pending_tool_terminal_lock:
            self._pending_tool_terminal_durations.clear()

    @staticmethod
    def _tool_event_aliases(event: AgentEvent) -> tuple[str, ...]:
        """为一个 tool 事件生成稳定别名集合。"""

        tool_key = AgentWorkbenchApp._tool_event_key(event)
        if not tool_key:
            return ()
        return (tool_key,)

    @staticmethod
    def _tool_item_aliases(item: _TimelineItem) -> tuple[str, ...]:
        """为本地 tool 条目生成可用于终态匹配的别名集合。"""

        tool_use_id = AgentWorkbenchApp._tool_use_id_from_metadata(item.metadata)
        if not tool_use_id:
            return ()
        return (tool_use_id,)

    def _has_visible_running_activity(self) -> bool:
        """判断当前是否仍有真实运行态活动项可见。"""

        for key in set(self._active_by_kind.values()):
            item = self._get_item(key)
            if self._is_visible_running_item(item):
                return True
        for key in set(self._active_tools.values()):
            item = self._get_item(key)
            if self._is_visible_running_item(item):
                return True
        if self._active_compress_key:
            item = self._get_item(self._active_compress_key)
            if self._is_visible_running_item(item):
                return True
        return False

    def _handle_slash_command(self, prompt: str) -> bool:
        """在 TUI 内部处理 slash 命令，不把它们送入 agent 队列。"""

        if not prompt.startswith("/"):
            return False
        command = prompt.split(maxsplit=1)[0].strip().casefold()
        if command == "/stop":
            self._interrupt_active_turn()
            return True
        if command == "/new":
            self.action_new_session()
            return True
        if command == "/help":
            self._append_system_message(_COMMAND_HELP_TEXT)
            self._status_message = "Displayed the command help."
            return True
        suggestion = self._match_command(command)
        if suggestion:
            self._append_system_message(
                f"Unknown command {command}. Press Tab to complete commands like {suggestion}."
            )
        else:
            self._append_system_message(
                f"Unknown command {command}. Run /help to see available commands."
            )
        self._status_message = "Command not recognized."
        return True

    def _interrupt_active_turn(self) -> None:
        """中断当前活跃回复，并保留已生成的历史内容。"""

        if self._active_turn is None:
            self._append_system_message("There is no active reply to interrupt.")
            self._status_message = "There is no active reply to interrupt."
            return
        if self._stopping_turn_id == self._active_turn.turn_id:
            self._status_message = "Stopping active reply."
            return
        if self._request_runtime_cancel():
            self._stopping_turn_id = self._active_turn.turn_id
            self._status_message = "Stopping active reply."
            return
        self._cancel_active_worker()
        self._clear_active_turn_display_pipeline()
        self._raw_stream_done_turn_id = None
        self._interrupt_running_turn_items()
        self._remove_waiting_thinking_items()
        self._append_system_message("Interrupted the active reply.")
        self._turn_count += 1
        self._finish_active_turn(
            queue_state="interrupted",
            status_message="Interrupted the active reply.",
        )

    def _cancel_active_worker(self) -> None:
        """取消当前后台 worker，并清理本地引用。"""

        worker = self._active_worker
        self._active_worker = None
        if worker is None or worker.is_finished:
            return
        worker.cancel()

    def _request_runtime_cancel(self) -> bool:
        """尝试请求底层 EasyHarness runtime 取消当前活跃调用。"""

        cancel = getattr(self._agent, "cancel", None)
        if not callable(cancel):
            return False
        cancel()
        return True

    def _interrupt_running_turn_items(self) -> None:
        """把当前仍处于运行态的展示项收口为中断后的可见历史。"""

        for key in list(self._active_by_kind.values()):
            item = self._get_item(key)
            if item is None:
                continue
            self._sync_running_item_duration(item)
            item.status = "completed"
            item.started_at = None
            self._clear_local_running_timer(item)
        self._active_by_kind.clear()
        for key in list(self._active_tools.values()):
            item = self._get_item(key)
            if item is None:
                continue
            self._sync_running_item_duration(item)
            item.status = "failed"
            item.started_at = None
            self._clear_local_running_timer(item)
            item.metadata.setdefault("error", "Interrupted")
        self._active_tools.clear()

    def _append_system_message(self, content: str, *, status: str = "completed") -> str:
        """追加一条 OpenBuffett 系统消息。"""

        return self._append_item(
            kind="system",
            title=DEFAULT_AGENT_BRAND,
            body=content,
            status=status,
        )

    def _autocomplete_command_input(self, input_widget: Input) -> bool:
        """对以 `/` 开头的当前输入执行闭集命令补全。"""

        current_value = input_widget.value.strip()
        if not current_value.startswith("/") or " " in current_value:
            return False
        matched_command = self._match_command(current_value)
        if matched_command is None or matched_command == current_value.casefold():
            return False
        input_widget.value = matched_command
        input_widget.cursor_position = len(matched_command)
        self._status_message = f"Completed command {matched_command}."
        return True

    def _match_command(self, raw_command: str) -> str | None:
        """匹配闭集 slash 命令，优先前缀命中，再回退到莱温斯坦距离。"""

        command = raw_command.strip().casefold()
        if not command.startswith("/"):
            return None
        if command in _SUPPORTED_COMMANDS:
            return command
        prefix_matches = [
            candidate for candidate in _SUPPORTED_COMMANDS if candidate.startswith(command)
        ]
        if prefix_matches:
            return prefix_matches[0]
        ranked_commands = self._command_matcher.rank(command, list(_SUPPORTED_COMMANDS))
        if not ranked_commands:
            return None
        best_match = ranked_commands[0]
        max_distance = max(1, min(2, len(best_match) // 3))
        if self._command_matcher(command, best_match) > max_distance:
            return None
        return best_match

    def _refresh_view(
        self,
        *,
        force_follow: bool = False,
        schedule_follow: bool = True,
    ) -> None:
        """刷新顶部状态和会话记录。"""

        try:
            self.query_one("#status-banner", Static).update(
                Text(self._render_status_banner())
            )
        except (NoMatches, ScreenStackError):
            return
        self._render_timeline(
            force_follow=force_follow,
            schedule_follow=schedule_follow,
        )
        self._render_queue_tray()

    def _render_timeline(
        self,
        *,
        force_follow: bool = False,
        schedule_follow: bool = True,
    ) -> None:
        """刷新主会话记录区域。"""

        try:
            timeline_widget = self.query_one("#timeline-view", Static)
        except (NoMatches, ScreenStackError):
            return
        timeline_widget.update(self._render_timeline_renderable())
        if schedule_follow:
            self._schedule_timeline_follow(force_follow=force_follow)

    def _schedule_timeline_follow(self, *, force_follow: bool = False) -> None:
        """在最终布局稳定后再决定是否跟随到底部。"""

        try:
            scroll_widget = self.query_one("#timeline-scroll", VerticalScroll)
        except (NoMatches, ScreenStackError):
            return
        if not (force_follow or self._should_follow_scroll(scroll_widget)):
            return
        self.call_after_refresh(
            scroll_widget.scroll_end,
            animate=False,
            force=True,
            immediate=True,
        )

    def _render_queue_tray(self) -> None:
        """刷新待处理消息托盘。"""

        try:
            queue_widget = self.query_one("#queue-tray", Static)
        except (NoMatches, ScreenStackError):
            return
        queue_widget.display = bool(self._pending_turns)
        queue_widget.update(self._render_queue_tray_renderable())

    def _render_status_banner(self) -> str:
        """渲染顶部状态摘要。"""

        return (
            f"{DEFAULT_AGENT_BRAND}\n"
            f"Completed {self._turn_count} turns\n"
            f"{self._status_message}"
        )

    def _render_timeline_text(self) -> str:
        """把本地展示项渲染为文本。"""

        visible_items = self._visible_timeline_items()
        if not visible_items:
            return "No messages yet."
        return "\n\n".join(self._format_timeline_item(item) for item in visible_items)

    def _render_timeline_renderable(self) -> object:
        """把主消息区渲染为 Rich renderable，便于局部着色。"""

        visible_items = self._visible_timeline_items()
        if not visible_items:
            return Text("No messages yet.", style="white")
        renderables: list[object] = []
        for index, item in enumerate(visible_items):
            renderables.append(self._render_timeline_item_renderable(item))
            if index < len(visible_items) - 1:
                renderables.append(Text(""))
        return Group(*renderables)

    def _visible_timeline_items(self) -> list[_TimelineItem]:
        """返回当前应在 timeline 中可见的展示项。"""

        return [
            item for item in self._items if not self._should_hide_timeline_item(item)
        ]

    def _render_queue_tray_text(self) -> str:
        """把待处理队列渲染为纯文本，便于测试验证。"""

        if not self._pending_turns:
            return ""
        return "\n".join(turn.prompt for turn in self._pending_turns)

    def _render_queue_tray_renderable(self) -> object:
        """把待处理队列渲染为扁平、居中的轻量列表。"""

        if not self._pending_turns:
            return Text("")
        queue_lines = [Align.center(Text("Queued", style=_CHAT_PREFIX_STYLE))]
        queue_lines.extend(
            Align.center(Text(turn.prompt, style="white")) for turn in self._pending_turns
        )
        return Group(*queue_lines)

    def _render_timeline_item_renderable(self, item: _TimelineItem) -> object:
        """把单条 timeline 项渲染为带局部样式的 Rich 对象。"""

        if item.kind == "user":
            return self._render_chat_message_renderable(item)
        if item.kind == "assistant":
            return self._render_chat_message_renderable(item)
        if item.kind == "system":
            return self._render_system_message_renderable(item)
        if item.kind == "compress":
            return self._render_compress_item_renderable(item)
        if item.kind == "thinking":
            if self._is_thinking_history_item(item):
                return self._render_thinking_history_renderable(item)
            return self._render_thinking_item_renderable(item)
        if item.kind == "tool":
            return self._render_tool_item_renderable(item)
        return Text(self._format_timeline_item(item), style=_LOW_EMPHASIS_STYLE)

    @staticmethod
    def _render_chat_message_renderable(item: _TimelineItem) -> Text:
        """渲染带主题色前缀的用户或助手消息。"""

        message = Text()
        message.append(item.title, style=_CHAT_PREFIX_STYLE)
        message.append(item.body, style="white")
        return message

    @staticmethod
    def _render_thinking_history_renderable(item: _TimelineItem) -> Text:
        """渲染已经升级为真实历史的 thinking 消息。"""

        message = Text()
        message.append(item.title, style=_THINKING_HISTORY_PREFIX_STYLE)
        message.append(item.body, style=_THINKING_HISTORY_BODY_STYLE)
        return message

    @staticmethod
    def _render_system_message_renderable(item: _TimelineItem) -> Text:
        """渲染 OpenBuffett 系统类消息。"""

        message = Text()
        if item.status == "cancelled":
            message.append(f"{item.title} · ", style=_LOW_EMPHASIS_STYLE)
            message.append(item.body, style=_LOW_EMPHASIS_STYLE)
            return message
        message.append(f"{item.title} · ", style=_LOW_EMPHASIS_STYLE)
        message.append(item.body, style=_LOW_EMPHASIS_STYLE)
        return message

    @staticmethod
    def _render_thinking_item_renderable(item: _TimelineItem) -> Text:
        """渲染临时 thinking 活动行。"""

        message = Text()
        message.append(AgentWorkbenchApp._format_duration(item.duration_ms), style=_TIMING_STYLE)
        message.append(" · ", style=_TIMING_STYLE)
        message.append(AgentWorkbenchApp._thinking_indicator_text(item), style=_THINKING_STYLE)
        return message

    @staticmethod
    def _render_compress_item_renderable(item: _TimelineItem) -> Text:
        """渲染上下文压缩活动行。"""

        message = Text()
        message.append(AgentWorkbenchApp._format_duration(item.duration_ms), style=_TIMING_STYLE)
        message.append(" · ", style=_TIMING_STYLE)
        message.append(item.body, style=_LOW_EMPHASIS_STYLE)
        return message

    @staticmethod
    def _render_tool_item_renderable(item: _TimelineItem) -> Text:
        """渲染只面向用户的一行工具活动摘要。"""

        main_line = Text()
        main_line.append(AgentWorkbenchApp._format_duration(item.duration_ms), style=_TIMING_STYLE)
        main_line.append(" · ", style=_TIMING_STYLE)
        main_line.append("Tool", style=_TOOL_LABEL_STYLE)
        main_line.append(f" {item.name or 'tool'}", style=_TOOL_TEXT_STYLE)
        main_line.append(" · ", style=_TIMING_STYLE)
        main_line.append(
            AgentWorkbenchApp._format_status_label(item.status),
            style=_TOOL_LABEL_STYLE,
        )
        summary = AgentWorkbenchApp._tool_user_summary(item)
        if summary:
            main_line.append(" · ", style=_TIMING_STYLE)
            main_line.append(summary, style=_TOOL_TEXT_STYLE)
        return main_line

    def _format_timeline_item(self, item: _TimelineItem) -> str:
        if item.kind in {"user", "assistant", "system"}:
            return self._format_message_item(item)
        if item.kind == "compress":
            return self._format_compress_item(item)
        if item.kind == "thinking":
            if not self._is_waiting_thinking_item(item):
                return self._format_assistant_item(item)
            return (
                f"{self._format_duration(item.duration_ms)} · "
                f"{self._thinking_indicator_text(item)}"
            )
        return self._format_tool_item(item)

    @staticmethod
    def _thinking_indicator_text(item: _TimelineItem) -> str:
        """返回运行中 thinking 指示器当前应显示的动画帧。"""

        frame_index = (
            max(item.duration_ms, 0) // _THINKING_ANIMATION_FRAME_DURATION_MS
        ) % len(_THINKING_ANIMATION_FRAMES)
        return f"Thinking {_THINKING_ANIMATION_FRAMES[int(frame_index)]}"

    def _format_message_item(self, item: _TimelineItem) -> str:
        if item.kind == "user":
            return self._format_user_item(item)
        if item.kind == "assistant":
            return self._format_assistant_item(item)
        if item.status == "failed":
            return f"{item.title} · {item.body}"
        return f"{item.title} · {item.body}"

    @staticmethod
    def _format_user_item(item: _TimelineItem) -> str:
        """按队列状态渲染用户消息。"""

        return f"{item.title}{item.body}"

    @staticmethod
    def _format_assistant_item(item: _TimelineItem) -> str:
        """按聊天风格渲染助手消息。"""

        return f"{item.title}{item.body}"

    def _format_compress_item(self, item: _TimelineItem) -> str:
        """按活动风格渲染上下文压缩消息。"""

        return f"{self._format_duration(item.duration_ms)} · {item.body}"

    def _format_tool_item(self, item: _TimelineItem) -> str:
        line = (
            f"{self._format_duration(item.duration_ms)} · "
            f"Tool {item.name or 'tool'} · {self._format_status_label(item.status)}"
        )
        summary = self._tool_user_summary(item)
        if summary:
            return f"{line} · {summary}"
        return line

    def _focus_chat_input(self) -> None:
        """让输入框在启动后获得焦点。"""

        self.query_one("#chat-input", Input).focus()

    @staticmethod
    def _format_status_label(status: str) -> str:
        if status == "started":
            return "Running"
        if status == "delta":
            return "Updating"
        if status == "cancelled":
            return "Stopped"
        if status == "failed":
            return "Failed"
        return "Done"

    @staticmethod
    def _format_duration(duration_ms: int) -> str:
        return f"{duration_ms / 1000:.2f}s"

    @staticmethod
    def _parse_started_at(value: str | None) -> datetime | None:
        if not value:
            return datetime.now(timezone.utc)
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except ValueError:
            return datetime.now(timezone.utc)

    @staticmethod
    def _event_data_dict(event: AgentEvent) -> dict[str, Any]:
        if isinstance(event.data, dict):
            return dict(event.data)
        if event.data is None:
            return {}
        return {"data": event.data}

    @staticmethod
    def _extract_tool_output(event: AgentEvent) -> dict[str, Any]:
        data = AgentWorkbenchApp._event_data_dict(event)
        output = data.get("output")
        if isinstance(output, dict):
            return {
                "preview": str(output.get("preview") or "").strip(),
                "detail": str(output.get("detail") or "").strip(),
                "model_text": str(output.get("model_text") or "").strip(),
            }
        return {}

    @staticmethod
    def _tool_event_key(event: AgentEvent) -> str:
        data = AgentWorkbenchApp._event_data_dict(event)
        return str(data.get("tool_use_id", "")).strip()

    @staticmethod
    def _tool_use_id_from_metadata(metadata: dict[str, Any]) -> str:
        return str(metadata.get("tool_use_id", "")).strip()

    @staticmethod
    def _tool_user_summary(item: _TimelineItem) -> str:
        """提取用户可见的一行工具概要，完整结果继续留在内部状态。"""

        if item.status == "failed":
            error = str(item.metadata.get("error", "")).strip()
            if not error:
                error = item.preview or item.body or item.detail
            summary = AgentWorkbenchApp._summarize_error_text(error)
            if summary:
                return f"Error: {summary}"
            return ""
        summary = item.preview or item.body or item.detail
        return AgentWorkbenchApp._single_line_text(summary)

    @staticmethod
    def _single_line_text(text: str) -> str:
        """把文本压缩为首个非空行，避免主 timeline 出现多行工具输出。"""

        lines = [line.strip() for line in str(text).splitlines() if line.strip()]
        if not lines:
            return str(text).strip()
        return lines[0]

    @staticmethod
    def _summarize_error_text(text: str) -> str:
        """把异常文本压缩为适合终端主 timeline 展示的摘要。"""

        cleaned = str(text).strip()
        if not cleaned:
            return ""
        if "Traceback (most recent call last):" not in cleaned:
            return AgentWorkbenchApp._single_line_text(cleaned)
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if not lines:
            return cleaned
        return lines[-1]

    @staticmethod
    def _merge_thinking_text(existing: str, incoming: str, *, append: bool) -> str:
        """合并流式 thinking 文本，兼容 delta 追加与 completed 全量回传。"""

        normalized_existing = str(existing)
        normalized_incoming = str(incoming)
        if not normalized_incoming:
            return normalized_existing
        if not normalized_existing:
            return normalized_incoming
        if append:
            return normalized_existing + normalized_incoming
        if normalized_incoming == normalized_existing:
            return normalized_existing
        if normalized_incoming.startswith(normalized_existing):
            return normalized_incoming
        if normalized_existing.endswith(normalized_incoming):
            return normalized_existing
        return normalized_existing + normalized_incoming

    @staticmethod
    def _normalize_thinking_text(text: str) -> str:
        """把 runtime thinking 中的换行控制字符压平为单行显示文本。"""

        return (
            str(text)
            .replace("\r\n", " ")
            .replace("\r", " ")
            .replace("\n", " ")
        )

    @staticmethod
    def _current_text_reveal_target(item: _TimelineItem) -> str:
        """返回某个文本条目当前已知的完整目标文本。"""

        return str(item.metadata.get(_TEXT_REVEAL_TARGET_KEY, item.body))

    @staticmethod
    def _set_text_reveal_target(item: _TimelineItem, text: str) -> None:
        """记录某个文本条目最终应被 reveal 出来的目标文本。"""

        item.metadata[_TEXT_REVEAL_TARGET_KEY] = str(text)

    def _queue_thinking_text_reveal(
        self,
        item: _TimelineItem,
        text: str,
        *,
        append: bool,
    ) -> None:
        """把 thinking 文本更新转成逐字符 reveal backlog。"""

        previous_target = self._current_text_reveal_target(item)
        merged_target = self._merge_thinking_text(previous_target, text, append=append)
        item.title = "Assistant (Thinking) > "
        item.metadata["ephemeral"] = False
        item.metadata["history"] = True
        item.metadata["provisional"] = False
        item.metadata[_THINKING_STATE_KEY] = _THINKING_HISTORY_STATE
        self._set_text_reveal_target(item, merged_target)
        self._enqueue_text_reveal_suffix(
            item,
            previous_target=previous_target,
            next_target=merged_target,
        )

    def _queue_assistant_text_reveal(
        self,
        item: _TimelineItem,
        text: str,
        *,
        append: bool,
    ) -> None:
        """把 assistant 文本更新转成逐字符 reveal backlog。"""

        previous_target = self._current_text_reveal_target(item)
        merged_target = self._merge_thinking_text(previous_target, text, append=append)
        self._set_text_reveal_target(item, merged_target)
        self._enqueue_text_reveal_suffix(
            item,
            previous_target=previous_target,
            next_target=merged_target,
        )

    def _enqueue_text_reveal_suffix(
        self,
        item: _TimelineItem,
        *,
        previous_target: str,
        next_target: str,
        stream_without_turn: bool = False,
    ) -> None:
        """把目标文本中新追加的后缀排入逐字符 reveal 队列。"""

        if not next_target.startswith(previous_target):
            return
        suffix = next_target[len(previous_target) :]
        if not suffix:
            return
        if stream_without_turn:
            self._pending_text_reveal_queue.append(
                _TextRevealChunk(
                    turn_id=None,
                    item_key=item.key,
                    text=suffix,
                )
            )
            return
        if self._active_turn is None or self._active_worker is None:
            item.body += suffix
            return
        self._pending_text_reveal_queue.append(
            _TextRevealChunk(
                turn_id=self._active_turn.turn_id,
                item_key=item.key,
                text=suffix,
            )
        )

    @staticmethod
    def _set_pending_text_terminal(
        item: _TimelineItem,
        *,
        status: str,
        duration_ms: int,
    ) -> None:
        """登记文本条目在 reveal 排空后需要提交的终态。"""

        item.metadata[_PENDING_TEXT_TERMINAL_STATUS_KEY] = status
        item.metadata[_PENDING_TEXT_TERMINAL_DURATION_KEY] = duration_ms

    def _commit_ready_text_terminal_states(self) -> bool:
        """把已经 reveal 完成的文本条目收口到终态。"""

        changed = False
        for kind in ("thinking", "assistant"):
            item = self._get_item(self._active_by_kind.get(kind, ""))
            if item is None:
                continue
            pending_status = str(
                item.metadata.get(_PENDING_TEXT_TERMINAL_STATUS_KEY, "")
            ).strip()
            if not pending_status or self._item_has_reveal_backlog(item.key):
                continue
            item.status = pending_status
            item.duration_ms = max(
                item.duration_ms,
                int(item.metadata.get(_PENDING_TEXT_TERMINAL_DURATION_KEY, 0)),
            )
            item.started_at = None
            item.metadata["provisional"] = False
            self._clear_local_running_timer(item)
            item.metadata.pop(_PENDING_TEXT_TERMINAL_STATUS_KEY, None)
            item.metadata.pop(_PENDING_TEXT_TERMINAL_DURATION_KEY, None)
            self._active_by_kind.pop(kind, None)
            if kind == "thinking" and self._is_waiting_thinking_item(item):
                self._items = [existing for existing in self._items if existing.key != item.key]
            changed = True
        return changed

    def _item_has_reveal_backlog(self, item_key: str) -> bool:
        """判断某个条目是否仍有待吐出的字符 backlog。"""

        return any(
            chunk.item_key == item_key for chunk in self._pending_text_reveal_queue
        )

    @staticmethod
    def _is_waiting_thinking_item(item: _TimelineItem) -> bool:
        """判断 thinking 条目是否仍是可删除的 waiting-only 占位。"""

        if item.kind != "thinking":
            return False
        state = str(item.metadata.get(_THINKING_STATE_KEY, "")).strip()
        if state:
            return state == _THINKING_PLACEHOLDER_STATE
        return item.metadata.get("ephemeral", False)

    @staticmethod
    def _is_thinking_history_item(item: _TimelineItem) -> bool:
        """判断 thinking 条目是否已经升级为真实历史消息。"""

        if item.kind != "thinking":
            return False
        state = str(item.metadata.get(_THINKING_STATE_KEY, "")).strip()
        if state:
            return state == _THINKING_HISTORY_STATE
        return item.metadata.get("history", False)

    @staticmethod
    def _should_hide_timeline_item(item: _TimelineItem) -> bool:
        """隐藏已经收口但仍未升级为真实历史的空 waiting 占位。"""

        return (
            AgentWorkbenchApp._is_waiting_thinking_item(item)
            and item.started_at is None
            and not item.body.strip()
        )

    @staticmethod
    def _format_event_status(event: AgentEvent) -> str:
        if event.kind == "thinking":
            if event.status == "started":
                return f"{DEFAULT_AGENT_BRAND} is thinking."
            if event.status == "cancelled":
                return "Interrupted."
            if event.status == "failed":
                return event.text or "Thinking did not complete."
            return "Thinking complete."
        if event.kind == "assistant":
            if event.status == "started":
                return f"{DEFAULT_AGENT_BRAND} is drafting a reply."
            if event.status == "delta":
                return f"{DEFAULT_AGENT_BRAND} is drafting a reply."
            if event.status == "cancelled":
                return "Interrupted."
            if event.status == "failed":
                return event.text or "Reply did not complete."
            return "Reply complete."
        if event.kind == "tool":
            name = event.name or "tool"
            if event.status == "started":
                return f"Calling {name}."
            if event.status == "cancelled":
                return f"{name} stopped."
            if event.status == "failed":
                return f"{name} failed."
            return f"{name} finished."
        if event.kind == "compress":
            return AgentWorkbenchApp._compress_activity_text(
                event.status,
                event.text or "",
            )
        if event.status == "cancelled":
            return "Interrupted."
        return event.text or "System message."

    @staticmethod
    def _compress_activity_text(status: str, text: str) -> str:
        """生成上下文压缩事件的英文活动文案。"""

        detail = AgentWorkbenchApp._summarize_error_text(text) if text else ""
        if status == "started":
            return "Compressing context..."
        if status == "completed":
            return "Conversation compressed"
        if status == "failed":
            if detail:
                return f"Context compression failed: {detail}"
            return "Context compression failed."
        if status == "cancelled":
            return "Context compression interrupted."
        return detail or "Conversation compressed"

    @staticmethod
    def _should_follow_scroll(scroll_widget: VerticalScroll) -> bool:
        """仅当用户靠近底部时才自动跟随。"""

        return (scroll_widget.max_scroll_y - scroll_widget.scroll_y) <= 2
