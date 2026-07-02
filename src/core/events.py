"""会话型 agent loop 事件定义。

该文件为运行时、工具包装层和 Textual 工作台提供统一事件结构，避免在各层
之间直接传递框架对象或临时字典约定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


TOOL_ACTIVITY_EVENT_TYPES = (
    "tool_attempt_started",
    "tool_attempt_failed",
    "tool_started",
    "tool_completed",
    "tool_failed",
)

TOOL_TERMINAL_EVENT_TYPES = (
    "tool_attempt_failed",
    "tool_completed",
    "tool_failed",
)


@dataclass(slots=True)
class LoopEvent:
    """描述一条可被 UI 消费的运行时事件。"""

    channel: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


LoopEventSink = Callable[[LoopEvent], None]


def build_loop_event(channel: str, event_type: str, **payload: Any) -> LoopEvent:
    """构造一条标准运行时事件。"""

    return LoopEvent(
        channel=channel,
        event_type=event_type,
        payload=dict(payload),
    )
