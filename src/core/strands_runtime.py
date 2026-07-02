"""Strands 运行时桥接层。

该文件负责两件事：
1. 把项目内 `ToolSpec` 包成 strands 可调用工具；
2. 把 strands 的流式回调桥接成统一 `LoopEvent`，并提供持久会话 runner。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import time
from typing import Any

from strands import Agent as StrandsAgent, tool

from src.core.events import LoopEventSink, build_loop_event
from src.tool.contracts import ToolContext, ToolResult, ToolSpec


_INVALID_PROVIDER_TOOL_NAME = re.compile(r"[^a-zA-Z0-9_-]+")
_TOOL_DETAIL_COLLAPSE_THRESHOLD = 240
_TOOL_PREVIEW_LIMIT = 120


@dataclass(slots=True)
class StrandsToolSummary:
    """描述一条已执行工具的最小摘要。"""

    name: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


@dataclass(slots=True)
class StrandsRunResult:
    """描述一次主脑回合的最小结果。"""

    text: str = ""
    tools: list[StrandsToolSummary] = field(default_factory=list)
    error: str = ""


class _StrandsCallbackBridge:
    """把 strands callback 事件桥接成统一事件流。"""

    def __init__(self, event_sink: LoopEventSink | None) -> None:
        self._event_sink = event_sink
        self.reset()

    def reset(self) -> None:
        """在每轮调用开始前重置状态。"""

        self._thinking_open = False
        self._assistant_started = False
        self._assistant_completed = False
        self._assistant_text = ""

    def open_thinking(self) -> None:
        """发出思考开始事件。"""

        if self._event_sink is None or self._thinking_open:
            return
        self._thinking_open = True
        self._event_sink(
            build_loop_event(
                "progress",
                "thinking_started",
                message="正在思考下一步。",
            )
        )

    def complete_thinking(self, message: str = "思考完成。") -> None:
        """发出思考完成事件。"""

        if self._event_sink is None or not self._thinking_open:
            return
        self._thinking_open = False
        self._event_sink(
            build_loop_event(
                "progress",
                "thinking_completed",
                message=message,
            )
        )

    def fail_thinking(self, message: str) -> None:
        """发出思考失败事件。"""

        if self._event_sink is None or not self._thinking_open:
            return
        self._thinking_open = False
        self._event_sink(
            build_loop_event(
                "progress",
                "thinking_failed",
                message=message,
            )
        )

    def fail_assistant(self, message: str) -> None:
        """在已有流式输出时发出 assistant 失败事件。"""

        if (
            self._event_sink is None
            or not self._assistant_started
            or self._assistant_completed
        ):
            return
        self._event_sink(
            build_loop_event(
                "assistant",
                "assistant_stream_failed",
                message=message,
            )
        )

    def flush_result(self, text: str) -> None:
        """在回调没有完整流出文本时，用最终结果补齐事件。"""

        normalized = text.strip()
        if self._event_sink is None or not normalized:
            return
        is_fallback = not self._assistant_started
        self.complete_thinking("准备开始回复。")
        if not self._assistant_started:
            self._assistant_started = True
            self._assistant_text = normalized
            self._event_sink(
                build_loop_event(
                    "assistant",
                    "assistant_stream_started",
                    message="正在生成回复。",
                )
            )
            self._event_sink(
                build_loop_event(
                    "assistant",
                    "assistant_stream_delta",
                    text=normalized,
                )
            )
        if not self._assistant_completed:
            self._assistant_completed = True
            self._assistant_text = normalized
            self._event_sink(
                build_loop_event(
                    "assistant",
                    "assistant_stream_completed",
                    text=self._assistant_text,
                    fallback=is_fallback,
                )
            )

    def __call__(self, **kwargs: Any) -> None:
        """接收 strands callback_handler 事件。"""

        if self._event_sink is None:
            return
        event = kwargs.get("event", {})
        tool_use = event.get("contentBlockStart", {}).get("start", {}).get("toolUse")
        if tool_use:
            self.complete_thinking("已决定调用工具。")
        data = str(kwargs.get("data", "") or "")
        if data:
            self.complete_thinking("准备开始回复。")
            if not self._assistant_started:
                self._assistant_started = True
                self._event_sink(
                    build_loop_event(
                        "assistant",
                        "assistant_stream_started",
                        message="正在生成回复。",
                    )
                )
            self._assistant_text += data
            self._event_sink(
                build_loop_event(
                    "assistant",
                    "assistant_stream_delta",
                    text=data,
                )
            )
            if kwargs.get("complete", False) and not self._assistant_completed:
                self._assistant_completed = True
                self._event_sink(
                    build_loop_event(
                        "assistant",
                        "assistant_stream_completed",
                        text=self._assistant_text,
                        fallback=False,
                    )
                )
        result = kwargs.get("result")
        if result is not None and not self._assistant_completed:
            self.flush_result(str(result))


class StrandsSessionRunner:
    """复用同一个 strands Agent 实例执行多轮会话。"""

    def __init__(
        self,
        *,
        agent_factory: Any,
        model: Any,
        tools: list[Any],
        system_prompt: str,
        event_sink: LoopEventSink | None,
    ) -> None:
        self._event_sink = event_sink
        self._bridge = _StrandsCallbackBridge(event_sink)
        self._agent = agent_factory(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            callback_handler=self._bridge if event_sink is not None else None,
        )

    def run(self, prompt: str) -> StrandsRunResult:
        """执行一轮会话输入。"""

        return _invoke_agent(
            self._agent,
            prompt,
            bridge=self._bridge,
        )


class StrandsRuntime:
    """创建 strands 会话 runner。"""

    requires_model = True

    def __init__(self, *, agent_factory: Any = StrandsAgent) -> None:
        """初始化运行时。"""

        self._agent_factory = agent_factory

    def create_session_runner(
        self,
        *,
        model: Any,
        tools: list[Any],
        system_prompt: str,
        event_sink: LoopEventSink | None = None,
    ) -> StrandsSessionRunner:
        """创建一个持久会话 runner。"""

        return StrandsSessionRunner(
            agent_factory=self._agent_factory,
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            event_sink=event_sink,
        )


def build_tool_context(
    *,
    services: dict[str, Any] | None = None,
    llm: Any | None = None,
    workspace_root: str = ".",
    event_sink: LoopEventSink | None = None,
) -> ToolContext:
    """构造一份共享给工具调用的最小上下文。"""

    return ToolContext(
        services=services or {},
        llm=llm,
        workspace_root=workspace_root,
        event_sink=event_sink,
    )


def sanitize_provider_tool_name(name: str) -> str:
    """把内部工具名转换为 provider 可接受的名字。"""

    sanitized = _INVALID_PROVIDER_TOOL_NAME.sub("_", name)
    if not sanitized:
        raise RuntimeError(f"工具名 '{name}' 无法转换为合法的 provider 工具名。")
    return sanitized


def build_strands_tools(
    *,
    tool_specs: list[ToolSpec],
    services: dict[str, Any] | None = None,
    llm: Any | None = None,
    executed_tools: list[StrandsToolSummary] | None = None,
    event_sink: LoopEventSink | None = None,
    workspace_root: str = ".",
) -> list[Any]:
    """把一组项目内工具包装为 strands tools，并校验 provider 名冲突。"""

    provider_names: dict[str, str] = {}
    for tool_spec in tool_specs:
        provider_name = sanitize_provider_tool_name(tool_spec.name)
        existing = provider_names.get(provider_name)
        if existing is not None and existing != tool_spec.name:
            raise RuntimeError(
                "不同内部工具名映射到了同一个 provider 工具名: "
                f"'{existing}' 与 '{tool_spec.name}' -> '{provider_name}'。"
            )
        provider_names[provider_name] = tool_spec.name
    return [
        build_strands_tool(
            tool_spec=tool_spec,
            services=services,
            llm=llm,
            executed_tools=executed_tools,
            event_sink=event_sink,
            workspace_root=workspace_root,
        )
        for tool_spec in tool_specs
    ]


def build_strands_tool(
    *,
    tool_spec: ToolSpec,
    services: dict[str, Any] | None = None,
    llm: Any | None = None,
    executed_tools: list[StrandsToolSummary] | None = None,
    event_sink: LoopEventSink | None = None,
    workspace_root: str = ".",
):
    """把一个项目内 `ToolSpec` 包装为 strands tool。"""
    provider_tool_name = sanitize_provider_tool_name(tool_spec.name)

    def _call(**kwargs):
        start_time = time.perf_counter()
        if event_sink is not None:
            event_sink(
                build_loop_event(
                    "progress",
                    "tool_started",
                    tool_name=tool_spec.name,
                    display_name=tool_spec.display_name,
                    tool_kind=tool_spec.tool_kind,
                    message=f"开始调用 {tool_spec.display_name}。",
                )
            )
        context = build_tool_context(
            services=services,
            llm=llm,
            workspace_root=workspace_root,
            event_sink=event_sink,
        )
        try:
            result = tool_spec.handler(context, **kwargs)
        except Exception as error:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            if event_sink is not None:
                event_sink(
                    build_loop_event(
                        "progress",
                        "tool_failed",
                        tool_name=tool_spec.name,
                        display_name=tool_spec.display_name,
                        tool_kind=tool_spec.tool_kind,
                        duration_ms=duration_ms,
                        message=f"{tool_spec.display_name} 调用失败: {error}",
                    )
                )
            raise
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        if executed_tools is not None:
            executed_tools.append(
                StrandsToolSummary(
                    name=tool_spec.name,
                    summary=result.summary,
                    metadata=result.metadata,
                    duration_ms=duration_ms,
                )
            )
        if event_sink is not None:
            result_payload = _build_tool_result_payload(result)
            event_sink(
                build_loop_event(
                    "progress",
                    "tool_completed",
                    tool_name=tool_spec.name,
                    display_name=tool_spec.display_name,
                    tool_kind=tool_spec.tool_kind,
                    duration_ms=duration_ms,
                    result_summary=result.summary,
                    result_preview=result_payload["result_preview"],
                    result_detail=result_payload["result_detail"],
                    collapsible=result_payload["collapsible"],
                    collapsed_by_default=result_payload["collapsed_by_default"],
                    message=f"{tool_spec.display_name} 调用完成。",
                )
            )
        return _serialize_tool_result(result)

    return tool(
        _call,
        name=provider_tool_name,
        description=tool_spec.description,
        inputSchema=tool_spec.input_schema,
    )


def _invoke_agent(
    agent: Any,
    prompt: str,
    *,
    bridge: _StrandsCallbackBridge,
) -> StrandsRunResult:
    """执行一次 Agent 调用并补齐事件状态。"""

    bridge.reset()
    bridge.open_thinking()
    try:
        result = agent(prompt)
    except Exception as error:
        message = str(error).strip() or error.__class__.__name__
        bridge.fail_thinking(message)
        bridge.fail_assistant(message)
        raise
    text = str(result).strip()
    bridge.flush_result(text)
    bridge.complete_thinking()
    return StrandsRunResult(text=text)


def _serialize_tool_result(result: ToolResult) -> str:
    """把工具结果整理为主脑可读文本。"""

    if result.summary:
        return result.summary
    if isinstance(result.content, str):
        return result.content
    return json.dumps(result.content, ensure_ascii=False, default=str)


def _build_tool_result_payload(result: ToolResult) -> dict[str, Any]:
    """把工具结果整理为时间线可消费的概要与详情。"""

    detail = _serialize_tool_result(result).strip()
    preview = result.summary.strip() or _truncate_text(detail, _TOOL_PREVIEW_LIMIT)
    collapsible = (
        len(detail) > _TOOL_DETAIL_COLLAPSE_THRESHOLD
        or "\n" in detail
        or detail != preview
    )
    return {
        "result_preview": preview,
        "result_detail": detail,
        "collapsible": collapsible,
        "collapsed_by_default": collapsible,
    }


def _truncate_text(text: str, limit: int) -> str:
    """把长文本裁剪为稳定预览。"""

    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."
