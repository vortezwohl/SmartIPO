"""会话时间线 reducer 测试。

该文件聚焦验证 core timeline 层的最小闭环：thinking 状态归约、工具条目
归约，以及 assistant 流式输出归约结果。
"""

from __future__ import annotations

from datetime import datetime, timedelta
import unittest

from src.core.events import build_loop_event
from src.core.timeline import ConversationTimeline


class ConversationTimelineTests(unittest.TestCase):
    """验证跨 UI 复用的会话时间线状态。"""

    def test_thinking_tool_and_assistant_events_reduce_to_entries(self) -> None:
        """thinking、tool 和 assistant 事件应归约为稳定时间线条目。"""

        timeline = ConversationTimeline()
        timeline.append_user_message("整理 README")

        timeline.apply_event(build_loop_event("progress", "thinking_started", message="正在思考下一步。"))
        timeline.apply_event(
            build_loop_event(
                "progress",
                "tool_attempt_started",
                tool_name="text.read",
                tool_kind="fileglide",
                tool_use_id="tool-1",
            )
        )
        timeline.apply_event(
            build_loop_event(
                "progress",
                "tool_started",
                tool_name="text.read",
                tool_kind="fileglide",
                tool_use_id="tool-1",
            )
        )
        timeline.apply_event(
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
        timeline.apply_event(build_loop_event("assistant", "assistant_stream_delta", text="已完成"))
        timeline.apply_event(
            build_loop_event(
                "assistant",
                "assistant_stream_completed",
                text="已完成",
                fallback=False,
            )
        )

        entries = timeline.entries
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0].kind, "user")
        self.assertEqual(entries[1].kind, "tool")
        self.assertEqual(entries[1].metadata["tool_name"], "text.read")
        self.assertEqual(entries[1].metadata["tool_kind"], "fileglide")
        self.assertEqual(entries[1].metadata["tool_use_id"], "tool-1")
        self.assertEqual(entries[1].metadata["phase"], "execution")
        self.assertEqual(entries[1].title, "")
        self.assertEqual(entries[1].body, "")
        self.assertEqual(entries[1].preview, "README.md")
        self.assertEqual(entries[1].detail, "README.md\nline 2\nline 3")
        self.assertTrue(entries[1].collapsible)
        self.assertTrue(entries[1].collapsed)
        self.assertEqual(entries[2].kind, "assistant")
        self.assertEqual(entries[2].body, "已完成")

    def test_tool_failure_keeps_raw_error_in_metadata(self) -> None:
        """工具失败时应把原始错误信息保留在 metadata。"""

        timeline = ConversationTimeline()
        timeline.apply_event(
            build_loop_event(
                "progress",
                "tool_started",
                tool_name="text.write",
                tool_kind="fileglide",
                tool_use_id="tool-2",
            )
        )
        timeline.apply_event(
            build_loop_event(
                "progress",
                "tool_failed",
                tool_name="text.write",
                tool_kind="fileglide",
                tool_use_id="tool-2",
                duration_ms=34,
                error="disk full",
                failure_stage="execution",
            )
        )

        entry = timeline.entries[0]
        self.assertEqual(entry.status, "error")
        self.assertEqual(entry.metadata["tool_name"], "text.write")
        self.assertEqual(entry.metadata["tool_kind"], "fileglide")
        self.assertEqual(entry.metadata["error"], "disk full")
        self.assertEqual(entry.metadata["failure_stage"], "execution")
        self.assertEqual(entry.body, "")

    def test_tool_attempt_failure_stays_distinct_from_local_execution_failure(self) -> None:
        """provider-side attempt failure 应以独立阶段进入时间线。"""

        timeline = ConversationTimeline()
        timeline.apply_event(
            build_loop_event(
                "progress",
                "tool_attempt_started",
                tool_name="path.list",
                tool_kind="fileglide",
                tool_use_id="tool-3",
            )
        )
        timeline.apply_event(
            build_loop_event(
                "progress",
                "tool_attempt_failed",
                tool_name="path.list",
                tool_kind="fileglide",
                tool_use_id="tool-3",
                error="provider-side tool call did not reach local execution",
                failure_stage="attempt",
            )
        )

        entry = timeline.entries[0]
        self.assertEqual(entry.status, "error")
        self.assertEqual(entry.metadata["phase"], "attempt")
        self.assertEqual(entry.metadata["failure_stage"], "attempt")
        self.assertEqual(
            entry.metadata["error"],
            "provider-side tool call did not reach local execution",
        )

    def test_refresh_running_durations_updates_active_entries(self) -> None:
        """运行中条目应能按当前时间刷新时长。"""

        timeline = ConversationTimeline()
        timeline.apply_event(build_loop_event("progress", "thinking_started", message="正在思考下一步。"))
        thinking_entry = timeline.entries[0]
        thinking_entry.started_at = datetime.now() - timedelta(milliseconds=900)

        changed = timeline.refresh_running_durations(datetime.now())

        self.assertTrue(changed)
        self.assertGreaterEqual(timeline.entries[0].duration_ms, 900)


if __name__ == "__main__":
    unittest.main()
