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

from src.agent import build_default_agent

_TIMELINE_REFRESH_INTERVAL_SECONDS = 0.05
_CHAT_PREFIX_STYLE = "bold #d8ffe0"
_THINKING_HISTORY_PREFIX_STYLE = "bold #91ab97"
_THINKING_HISTORY_BODY_STYLE = "#b2bbb3"
_TIMING_STYLE = "#7e9b84"
_THINKING_STYLE = "bold #88ad8f"
_LOW_EMPHASIS_STYLE = _THINKING_STYLE
_TOOL_BLOCK_STYLE = "bold #d8ffe0"
_SUPPORTED_COMMANDS = ("/stop", "/new", "/help")
_COMMAND_HELP_TEXT = (
    "Available commands: /stop interrupts the active reply, /new starts a new session, /help shows this help."
)
_INPUT_PLACEHOLDER = "Send a message. /stop interrupts, /new resets, /help shows commands."
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
    user_item_key: str


class AgentWorkbenchApp(App[None]):
    """运行 SmartIPO EasyHarness agent 的单列本地工作台。"""

    TITLE = "SmartIPO"
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
        self._status_message = "Workbench ready."
        self._active_by_kind: dict[str, str] = {}
        self._active_tools: dict[str, str] = {}
        self._pending_turns: deque[_PendingTurn] = deque()
        self._active_turn: _PendingTurn | None = None
        self._active_worker: Worker[None] | None = None
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
        self._pending_turns.clear()
        self._active_turn = None
        self._active_worker = None
        self._stopping_turn_id = None
        self._cancelled_turn_id = None
        self._status_message = "Started a new session."
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
                self.call_from_thread(self._apply_agent_event_for_turn, turn_id, event)
            if worker.is_cancelled:
                return
            self.call_from_thread(self._complete_turn, turn_id)
        except Exception as error:  # pragma: no cover
            self.call_from_thread(self._show_error, turn_id, f"Request failed: {error}")

    def _apply_agent_event_for_turn(self, turn_id: str, event: AgentEvent) -> None:
        """仅当事件属于当前活跃轮次时，才把它应用到本地展示态。"""

        if not self._is_active_turn(turn_id):
            return
        self._apply_agent_event(event)

    def _apply_agent_event(self, event: AgentEvent) -> None:
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
        self._status_message = self._format_event_status(event)
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
                    metadata={"ephemeral": True, "history": False},
                )
                return
            item.status = "started"
            item.metadata["provisional"] = False
            item.metadata["ephemeral"] = True
            item.metadata["history"] = False
            return
        item = self._get_active_thinking_item()
        if item is None:
            key = self._append_item(
                kind="thinking",
                title="thinking",
                body="",
                status="started",
                started_at=self._parse_started_at(event.started_at),
                metadata={"provisional": False, "ephemeral": True, "history": False},
            )
            self._active_by_kind["thinking"] = key
            item = self._get_item(key)
        if item is None:
            return
        thinking_text = (event.text or "").strip()
        if event.status == "delta":
            item.status = "delta"
            item.metadata["provisional"] = False
            if thinking_text:
                self._promote_thinking_item_to_history(
                    item,
                    thinking_text,
                    append=True,
                )
            else:
                item.metadata["ephemeral"] = True
                item.metadata["history"] = False
            return
        if event.status in {"completed", "failed", "cancelled"}:
            self._sync_running_item_duration(item)
            if thinking_text:
                self._promote_thinking_item_to_history(
                    item,
                    thinking_text,
                    append=False,
                )
            item.status = event.status
            item.duration_ms = max(item.duration_ms, event.duration_ms or 0)
            item.started_at = None
            item.metadata["provisional"] = False
            self._active_by_kind.pop("thinking", None)

    def _apply_tool_event(self, event: AgentEvent) -> None:
        self._remove_waiting_thinking_items()
        tool_key = self._tool_event_key(event)
        if event.status == "started":
            self._active_tools[tool_key] = self._append_item(
                kind="tool",
                title="",
                body="",
                name=event.name or "tool",
                status="started",
                started_at=self._parse_started_at(event.started_at),
                metadata=self._event_data_dict(event),
            )
            return
        item_key = self._resolve_active_tool_item_key(tool_key, event.name or "")
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
        output = self._extract_tool_output(event)
        item.preview = output.get("preview") or event.text or item.preview
        item.detail = output.get("detail") or output.get("model_text") or item.detail
        if event.text and not item.preview:
            item.preview = event.text
        if event.status in {"completed", "failed", "cancelled"}:
            self._active_tools.pop(tool_key, None)

    def _resolve_active_tool_item_key(self, tool_key: str, tool_name: str) -> str:
        """尽量把 tool 终态重新挂回已有运行项，避免同一次调用被渲染成两条。"""

        item_key = self._active_tools.get(tool_key, "")
        if item_key:
            return item_key
        if not tool_name:
            return ""
        named_item_key = self._active_tools.get(tool_name, "")
        if named_item_key:
            if tool_key != tool_name:
                self._active_tools[tool_key] = named_item_key
                self._active_tools.pop(tool_name, None)
            return named_item_key
        return ""

    def _apply_assistant_event(self, event: AgentEvent) -> None:
        if event.status in {"started", "delta", "completed", "cancelled"}:
            self._remove_waiting_thinking_items()
        if event.status == "started":
            self._active_by_kind["assistant"] = self._append_item(
                kind="assistant",
                title="Assistant > ",
                status="started",
                started_at=self._parse_started_at(event.started_at),
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
        if item is None:
            return
        if event.status == "delta" and event.text:
            item.body += event.text
            return
        if event.status in {"completed", "failed", "cancelled"}:
            if event.text and (event.status != "cancelled" or not item.body):
                item.body = event.text
            item.status = event.status
            item.duration_ms = event.duration_ms or item.duration_ms
            item.started_at = None
            self._active_by_kind.pop("assistant", None)

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
            title="SmartIPO",
            body=body,
            status=event.status,
            started_at=self._parse_started_at(event.started_at),
            duration_ms=event.duration_ms or 0,
            metadata=metadata,
        )

    def _apply_compress_event(self, event: AgentEvent) -> None:
        self._append_item(
            kind="compress",
            title="SmartIPO",
            body=event.text or "",
            status=event.status,
            started_at=self._parse_started_at(event.started_at),
            duration_ms=event.duration_ms or 0,
            metadata=self._event_data_dict(event),
        )

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
        self._settle_running_turn_items("failed", message=message)
        self._remove_waiting_thinking_items()
        self._append_item(
            kind="system",
            title="SmartIPO",
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

    def _start_local_thinking(self) -> None:
        """在收到真实事件前先启动本地 thinking 占位与计时。"""

        if self._get_active_thinking_item() is not None:
            return
        self._active_by_kind["thinking"] = self._append_item(
            kind="thinking",
            title="thinking",
            status="started",
            started_at=datetime.now(timezone.utc),
            metadata={"provisional": True, "ephemeral": True},
        )

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
        user_item_key = self._append_user_message(
            prompt,
            metadata={
                "turn_id": turn_id,
                "queue_state": "queued",
                "queue_position": 0,
            },
        )
        self._pending_turns.append(
            _PendingTurn(
                turn_id=turn_id,
                prompt=prompt,
                user_item_key=user_item_key,
            )
        )
        self._refresh_turn_queue_metadata()

    def _start_next_turn_if_idle(self) -> None:
        """若当前没有活跃轮次，则启动队首消息。"""

        if self._active_turn is not None or not self._pending_turns:
            return
        turn = self._pending_turns.popleft()
        self._active_turn = turn
        self._stopping_turn_id = None
        self._cancelled_turn_id = None
        self._refresh_turn_queue_metadata()
        self._start_local_thinking()
        self._status_message = "Processing queued message."
        self._refresh_view(force_follow=True)
        self._active_worker = self._run_turn_worker(turn.turn_id, turn.prompt)

    def _finish_active_turn(self, *, queue_state: str, status_message: str) -> None:
        """收尾当前活跃轮次，并在可能时启动下一条。"""

        if self._active_turn is None:
            return
        self._active_worker = None
        item = self._get_item(self._active_turn.user_item_key)
        if item is not None:
            item.metadata["queue_state"] = queue_state
            item.metadata["queue_position"] = None
            item.status = "failed" if queue_state == "failed" else "completed"
        self._active_turn = None
        self._stopping_turn_id = None
        self._cancelled_turn_id = None
        self._refresh_turn_queue_metadata()
        self._status_message = status_message
        self._refresh_view(force_follow=True)
        self._start_next_turn_if_idle()

    def _refresh_turn_queue_metadata(self) -> None:
        """同步当前活跃条目与待处理条目的队列状态。"""

        if self._active_turn is not None:
            active_item = self._get_item(self._active_turn.user_item_key)
            if active_item is not None:
                active_item.metadata["queue_state"] = "running"
                active_item.metadata["queue_position"] = 0
        for index, turn in enumerate(self._pending_turns, start=1):
            item = self._get_item(turn.user_item_key)
            if item is None:
                continue
            item.metadata["queue_state"] = "queued"
            item.metadata["queue_position"] = index
            item.status = "completed"

    def _settle_running_turn_items(self, status: str, *, message: str = "") -> None:
        """收口当前仍处于 started 的展示项，避免失败后残留运行态。"""

        for key in list(self._active_by_kind.values()):
            item = self._get_item(key)
            if item is None or item.started_at is None:
                continue
            self._sync_running_item_duration(item)
            item.status = status
            item.started_at = None
        self._active_by_kind.clear()
        for key in list(self._active_tools.values()):
            item = self._get_item(key)
            if item is None:
                continue
            self._sync_running_item_duration(item)
            item.status = status
            item.started_at = None
            if message and "error" not in item.metadata:
                item.metadata["error"] = message
        self._active_tools.clear()

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
        duration_ms = int(
            (datetime.now(timezone.utc) - item.started_at).total_seconds() * 1000
        )
        item.duration_ms = max(0, duration_ms)

    def _refresh_running_items(self) -> None:
        """刷新仍处于 started 状态的本地展示时长。"""

        changed = False
        now = datetime.now(timezone.utc)
        for item in self._items:
            if item.started_at is None:
                continue
            duration_ms = int((now - item.started_at).total_seconds() * 1000)
            duration_ms = max(0, duration_ms)
            if duration_ms != item.duration_ms:
                item.duration_ms = duration_ms
                changed = True
        if changed:
            self._render_timeline()

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
        self._active_by_kind.clear()
        for key in list(self._active_tools.values()):
            item = self._get_item(key)
            if item is None:
                continue
            self._sync_running_item_duration(item)
            item.status = "failed"
            item.started_at = None
            item.metadata.setdefault("error", "Interrupted")
        self._active_tools.clear()

    def _append_system_message(self, content: str, *, status: str = "completed") -> str:
        """追加一条 SmartIPO 系统消息。"""

        return self._append_item(
            kind="system",
            title="SmartIPO",
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
            "SmartIPO\n"
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
            item
            for item in self._items
            if not (
                (
                    item.kind == "user"
                    and str(item.metadata.get("queue_state", "")).strip() == "queued"
                )
                or self._should_hide_timeline_item(item)
            )
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
        if item.kind in {"system", "compress"}:
            return self._render_system_message_renderable(item)
        if item.kind == "thinking":
            if self._is_thinking_history_item(item):
                return self._render_thinking_history_renderable(item)
            return self._render_thinking_item_renderable(item)
        if item.kind == "tool":
            return self._render_tool_item_renderable(item)
        return Text(self._format_timeline_item(item), style="white")

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
        """渲染 SmartIPO 系统类消息。"""

        message = Text()
        if item.status == "cancelled":
            message.append(f"{item.title} · ", style=_LOW_EMPHASIS_STYLE)
            message.append(item.body, style=_LOW_EMPHASIS_STYLE)
            return message
        message.append(f"{item.title} · ", style=_CHAT_PREFIX_STYLE)
        message.append(item.body, style="white")
        return message

    @staticmethod
    def _render_thinking_item_renderable(item: _TimelineItem) -> Text:
        """渲染临时 thinking 活动行。"""

        message = Text()
        message.append(AgentWorkbenchApp._format_duration(item.duration_ms), style=_TIMING_STYLE)
        message.append(" · ", style=_TIMING_STYLE)
        message.append("Thinking ...", style=_THINKING_STYLE)
        return message

    @staticmethod
    def _render_tool_item_renderable(item: _TimelineItem) -> Text:
        """渲染只面向用户的一行工具活动摘要。"""

        main_line = Text()
        main_line.append(AgentWorkbenchApp._format_duration(item.duration_ms), style=_TIMING_STYLE)
        main_line.append(" · ", style=_TIMING_STYLE)
        main_line.append("{ ", style=_TOOL_BLOCK_STYLE)
        main_line.append("Tool", style=_TOOL_BLOCK_STYLE)
        main_line.append(f" {item.name or 'tool'}", style="white")
        main_line.append(" · ", style=_TOOL_BLOCK_STYLE)
        main_line.append(AgentWorkbenchApp._format_status_label(item.status), style=_TOOL_BLOCK_STYLE)
        main_line.append(" }", style=_TOOL_BLOCK_STYLE)
        summary = AgentWorkbenchApp._tool_user_summary(item)
        if summary:
            main_line.append(" · ", style=_TIMING_STYLE)
            main_line.append(summary, style="white")
        return main_line

    def _format_timeline_item(self, item: _TimelineItem) -> str:
        if item.kind in {"user", "assistant", "system", "compress"}:
            return self._format_message_item(item)
        if item.kind == "thinking":
            if not self._is_waiting_thinking_item(item):
                return self._format_assistant_item(item)
            return f"{self._format_duration(item.duration_ms)} · Thinking ..."
        return self._format_tool_item(item)

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

    def _format_tool_item(self, item: _TimelineItem) -> str:
        line = (
            f"{self._format_duration(item.duration_ms)} · "
            f"{{ Tool {item.name or 'tool'} · {self._format_status_label(item.status)} }}"
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
        tool_use_id = str(data.get("tool_use_id", "")).strip()
        return tool_use_id or event.name or "tool"

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
    def _is_waiting_thinking_item(item: _TimelineItem) -> bool:
        """判断 thinking 条目是否仍是可删除的 waiting-only 占位。"""

        return item.kind == "thinking" and item.metadata.get("ephemeral", False)

    @staticmethod
    def _is_thinking_history_item(item: _TimelineItem) -> bool:
        """判断 thinking 条目是否已经升级为真实历史消息。"""

        return item.kind == "thinking" and item.metadata.get("history", False)

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
                return "SmartIPO is thinking."
            if event.status == "cancelled":
                return "Interrupted."
            if event.status == "failed":
                return event.text or "Thinking did not complete."
            return "Thinking complete."
        if event.kind == "assistant":
            if event.status == "started":
                return "SmartIPO is drafting a reply."
            if event.status == "delta":
                return "SmartIPO is drafting a reply."
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
            return "Context compressed."
        if event.status == "cancelled":
            return "Interrupted."
        return event.text or "System message."

    @staticmethod
    def _should_follow_scroll(scroll_widget: VerticalScroll) -> bool:
        """仅当用户靠近底部时才自动跟随。"""

        return (scroll_widget.max_scroll_y - scroll_widget.scroll_y) <= 2
