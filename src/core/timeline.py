"""跨 UI 复用的会话时间线状态模型。

该文件负责把运行时 `LoopEvent` 归约为稳定的 timeline entries。它只定义
会话时间线语义与状态流转，不直接依赖 Textual、WebUI 或其他具体展示层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.core.events import LoopEvent, TOOL_ACTIVITY_EVENT_TYPES


@dataclass(slots=True)
class TimelineEntry:
    """描述一条跨 UI 复用的时间线条目。"""

    key: str
    kind: str
    title: str
    body: str
    preview: str = ""
    detail: str = ""
    status: str = "done"
    duration_ms: int = 0
    started_at: datetime | None = None
    collapsible: bool = False
    collapsed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationTimeline:
    """维护一组可被不同 UI 渲染的会话时间线条目。"""

    def __init__(self) -> None:
        self.reset()

    @property
    def entries(self) -> tuple[TimelineEntry, ...]:
        """返回当前时间线条目。"""

        return tuple(self._entries)

    def reset(self) -> None:
        """清空状态并回到初始会话。"""

        self._entries: list[TimelineEntry] = []
        self._item_counter = 0
        self._thinking_key: str | None = None
        self._stream_key: str | None = None
        self._running_tool_keys: dict[str, str] = {}

    def append_user_message(self, content: str) -> str:
        """把用户输入追加为一条标准时间线项目。"""

        return self._append_entry(
            kind="user",
            title="你",
            body=content,
        )

    def append_system_message(self, title: str, content: str, *, status: str = "error") -> str:
        """把系统消息追加为一条标准时间线项目。"""

        return self._append_entry(
            kind="system",
            title=title,
            body=content,
            status=status,
        )

    def apply_event(self, event: LoopEvent) -> None:
        """把一条运行时事件归约进当前时间线状态。"""

        channel = event.channel
        event_type = event.event_type
        payload = event.payload
        if channel == "assistant":
            self._apply_assistant_event(event_type, payload)
            return
        if channel != "progress":
            return
        if event_type == "thinking_started":
            self._start_thinking(event.created_at)
            return
        if event_type == "thinking_completed":
            self._remove_thinking()
            return
        if event_type == "thinking_failed":
            self._fail_thinking(str(payload.get("message", "thinking failed")))
            return
        if event_type in TOOL_ACTIVITY_EVENT_TYPES:
            self._apply_tool_event(event_type, payload, event.created_at)

    def refresh_running_durations(self, now: datetime | None = None) -> bool:
        """刷新仍在运行中的条目时长。"""

        current_time = now or datetime.now()
        changed = False
        for item in self._entries:
            if item.started_at is None:
                continue
            new_duration = max(
                0,
                int((current_time - item.started_at).total_seconds() * 1000),
            )
            if new_duration != item.duration_ms:
                item.duration_ms = new_duration
                changed = True
        return changed

    def _apply_assistant_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "assistant_stream_started":
            return
        if event_type == "assistant_stream_delta":
            self._remove_thinking()
            delta = str(payload.get("text", ""))
            if not delta:
                return
            item = self._get_entry(self._stream_key or "")
            if item is None:
                self._stream_key = self._append_entry(
                    kind="assistant",
                    title="AI",
                    body=delta,
                    status="running",
                )
                return
            item.body += delta
            return
        if event_type == "assistant_stream_completed":
            item = self._get_entry(self._stream_key or "")
            if item is not None:
                item.status = "done"
            self._stream_key = None

    def _start_thinking(self, created_at: datetime) -> None:
        if self._thinking_key is not None:
            return
        self._thinking_key = self._append_entry(
            kind="thinking",
            title="AI",
            body="thinking",
            status="running",
            started_at=created_at,
        )

    def _remove_thinking(self) -> None:
        if self._thinking_key is None:
            return
        self._entries = [
            item
            for item in self._entries
            if item.key != self._thinking_key
        ]
        self._thinking_key = None

    def _fail_thinking(self, message: str) -> None:
        item = self._get_entry(self._thinking_key or "")
        if item is None:
            return
        item.body = message
        item.status = "error"
        item.started_at = None
        self._thinking_key = None

    def _apply_tool_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        created_at: datetime,
    ) -> None:
        tool_name = str(payload.get("tool_name", "tool"))
        tool_kind = str(payload.get("tool_kind", "")).strip()
        tool_use_id = str(payload.get("tool_use_id", tool_name)).strip() or tool_name
        item = self._get_entry(self._running_tool_keys.get(tool_use_id, ""))
        if event_type == "tool_attempt_started":
            self._remove_thinking()
            key = self._append_entry(
                kind="tool",
                title="",
                body="",
                status="running",
                started_at=created_at,
                metadata={
                    "tool_name": tool_name,
                    "tool_kind": tool_kind,
                    "tool_use_id": tool_use_id,
                    "phase": "attempt",
                },
            )
            self._running_tool_keys[tool_use_id] = key
            return
        if event_type == "tool_started":
            if item is None:
                key = self._append_entry(
                    kind="tool",
                    title="",
                    body="",
                    status="running",
                    started_at=created_at,
                    metadata={
                        "tool_name": tool_name,
                        "tool_kind": tool_kind,
                        "tool_use_id": tool_use_id,
                        "phase": "execution",
                    },
                )
                self._running_tool_keys[tool_use_id] = key
                return
            item.started_at = created_at
            item.duration_ms = 0
            item.status = "running"
            item.metadata.update(
                {
                    "tool_name": tool_name,
                    "tool_kind": tool_kind,
                    "tool_use_id": tool_use_id,
                    "phase": "execution",
                }
            )
            return
        preview = str(payload.get("result_preview", "")).strip()
        detail = str(payload.get("result_detail", "")).strip()
        collapsible = bool(payload.get("collapsible", False))
        collapsed = bool(payload.get("collapsed_by_default", False))
        error = str(payload.get("error", "")).strip()
        failure_stage = str(payload.get("failure_stage", "")).strip()
        metadata = {
            "tool_name": tool_name,
            "tool_kind": tool_kind,
            "tool_use_id": tool_use_id,
        }
        if event_type == "tool_attempt_failed":
            metadata["phase"] = "attempt"
        elif event_type in {"tool_completed", "tool_failed"}:
            metadata["phase"] = "execution"
        if error:
            metadata["error"] = error
        if failure_stage:
            metadata["failure_stage"] = failure_stage
        if item is None:
            self._append_entry(
                kind="tool",
                title="",
                body="",
                preview=preview,
                detail=detail,
                collapsible=collapsible,
                collapsed=collapsed,
                status="done" if event_type == "tool_completed" else "error",
                duration_ms=int(payload.get("duration_ms", 0) or 0),
                metadata=metadata,
            )
            self._running_tool_keys.pop(tool_use_id, None)
            return
        item.preview = preview or item.preview
        item.detail = detail or item.detail
        item.collapsible = collapsible
        item.collapsed = collapsed if collapsible else False
        item.status = "done" if event_type == "tool_completed" else "error"
        item.duration_ms = int(
            payload.get("duration_ms", 0)
            or item.duration_ms
        )
        item.started_at = None
        item.metadata.update(metadata)
        self._running_tool_keys.pop(tool_use_id, None)

    def _append_entry(
        self,
        *,
        kind: str,
        title: str,
        body: str,
        preview: str = "",
        detail: str = "",
        status: str = "done",
        duration_ms: int = 0,
        started_at: datetime | None = None,
        collapsible: bool = False,
        collapsed: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        key = self._next_key(kind)
        self._entries.append(
            TimelineEntry(
                key=key,
                kind=kind,
                title=title,
                body=body,
                preview=preview,
                detail=detail,
                status=status,
                duration_ms=duration_ms,
                started_at=started_at,
                collapsible=collapsible,
                collapsed=collapsed,
                metadata=metadata or {},
            )
        )
        return key

    def _get_entry(self, key: str) -> TimelineEntry | None:
        for item in self._entries:
            if item.key == key:
                return item
        return None

    def _next_key(self, prefix: str) -> str:
        self._item_counter += 1
        return f"{prefix}-{self._item_counter}"
