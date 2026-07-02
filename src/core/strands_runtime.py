"""Strands 运行时桥接层。

该文件负责两件事：
1. 把项目内 `ToolSpec` 包成 strands 可调用工具；
2. 把 strands 的流式回调桥接成统一 `LoopEvent`，并提供持久会话 runner。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

from strands import Agent as StrandsAgent
from strands.tools import PythonAgentTool

from src.core.events import LoopEventSink, build_loop_event
from src.tool.contracts import ToolContext, ToolResult, ToolSpec
from src.tool.framework.execution import (
    build_tool_result_payload,
    extract_tool_error,
    serialize_tool_result,
)
from src.tool.framework.validation import sanitize_provider_tool_name


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

    def __init__(
        self,
        event_sink: LoopEventSink | None,
        provider_tool_identities: dict[str, tuple[str, str]],
    ) -> None:
        self._event_sink = event_sink
        self._provider_tool_identities = provider_tool_identities
        self.reset()

    def reset(self) -> None:
        """在每轮调用开始前重置状态。"""

        self._thinking_open = False
        self._assistant_started = False
        self._assistant_completed = False
        self._assistant_text = ""
        self._pending_tool_attempts: dict[str, dict[str, str]] = {}

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

        self._fail_pending_tool_attempts(message)
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
        self._fail_pending_tool_attempts(
            "provider-side tool call did not reach local execution",
        )
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
            self.complete_thinking()
            self._record_tool_attempt(tool_use)
        data = str(kwargs.get("data", "") or "")
        if data:
            self._fail_pending_tool_attempts(
                "provider-side tool call did not reach local execution",
            )
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

    def mark_tool_execution(self, tool_use_id: str) -> None:
        """标记某次工具尝试已经进入本地执行。"""

        self._pending_tool_attempts.pop(tool_use_id, None)

    def _record_tool_attempt(self, tool_use: dict[str, Any]) -> None:
        if self._event_sink is None:
            return
        provider_tool_name = str(tool_use.get("name", "")).strip()
        tool_use_id = str(tool_use.get("toolUseId", provider_tool_name)).strip()
        tool_name, tool_kind = self._provider_tool_identities.get(
            provider_tool_name,
            (provider_tool_name or "tool", ""),
        )
        self._pending_tool_attempts[tool_use_id] = {
            "tool_name": tool_name,
            "tool_kind": tool_kind,
        }
        self._event_sink(
            build_loop_event(
                "progress",
                "tool_attempt_started",
                tool_name=tool_name,
                tool_kind=tool_kind,
                tool_use_id=tool_use_id,
            )
        )

    def _fail_pending_tool_attempts(self, message: str) -> None:
        if self._event_sink is None or not self._pending_tool_attempts:
            return
        for tool_use_id, identity in tuple(self._pending_tool_attempts.items()):
            self._event_sink(
                build_loop_event(
                    "progress",
                    "tool_attempt_failed",
                    tool_name=identity["tool_name"],
                    tool_kind=identity["tool_kind"],
                    tool_use_id=tool_use_id,
                    error=message,
                    failure_stage="attempt",
                )
            )
        self._pending_tool_attempts.clear()


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
        provider_tool_identities = _build_provider_tool_identities(tools)
        self._bridge = _StrandsCallbackBridge(
            event_sink,
            provider_tool_identities,
        )
        for item in tools:
            setter = getattr(item, "set_bridge", None)
            if callable(setter):
                setter(self._bridge)
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
    return _ProjectStrandsTool(
        tool_spec=tool_spec,
        services=services,
        llm=llm,
        executed_tools=executed_tools,
        event_sink=event_sink,
        workspace_root=workspace_root,
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


def _build_tool_event_error_payload(error: Exception) -> dict[str, str]:
    """提取应回给时间线的原始错误诊断。"""

    tool_error = extract_tool_error(error)
    payload = {"error": tool_error.raw_error or tool_error.model_message}
    if tool_error.raw_error:
        payload["raw_error"] = tool_error.raw_error
    if tool_error.code:
        payload["error_code"] = tool_error.code
    if tool_error.model_message != payload["error"]:
        payload["model_error"] = tool_error.model_message
    if tool_error.retry_hint:
        payload["retry_hint"] = tool_error.retry_hint
    return payload


class _ProjectStrandsTool(PythonAgentTool):
    """把项目内 `ToolSpec` 直接桥接为 Strands 可执行工具。"""

    def __init__(
        self,
        *,
        tool_spec: ToolSpec,
        services: dict[str, Any] | None,
        llm: Any | None,
        executed_tools: list[StrandsToolSummary] | None,
        event_sink: LoopEventSink | None,
        workspace_root: str,
    ) -> None:
        self._project_tool_spec = tool_spec
        self._services = services
        self._llm = llm
        self._executed_tools = executed_tools
        self._event_sink = event_sink
        self._workspace_root = workspace_root
        self._bridge: _StrandsCallbackBridge | None = None
        provider_tool_name = sanitize_provider_tool_name(tool_spec.name)
        super().__init__(
            provider_tool_name,
            {
                "name": provider_tool_name,
                "description": tool_spec.description,
                "inputSchema": tool_spec.input_schema,
            },
            self._run_tool_use,
        )

    @property
    def internal_tool_name(self) -> str:
        """返回项目内原始工具名。"""

        return self._project_tool_spec.name

    @property
    def provider_tool_name(self) -> str:
        """返回 provider 可见工具名。"""

        return self.tool_name

    @property
    def tool_kind(self) -> str:
        """返回工具类别。"""

        return self._project_tool_spec.tool_kind

    def set_bridge(self, bridge: _StrandsCallbackBridge) -> None:
        """绑定会话级 callback bridge。"""

        self._bridge = bridge

    def __call__(self, **kwargs: Any) -> str:
        """供测试与假 runtime 直接调用工具。"""

        result = self._invoke_project_tool(kwargs, tool_use_id="direct")
        return serialize_tool_result(result)

    def _run_tool_use(self, tool_use: dict[str, Any], **_invocation_state: Any) -> dict[str, Any]:
        tool_use_id = str(tool_use.get("toolUseId", "unknown")).strip() or "unknown"
        tool_input = tool_use.get("input", {})
        if not isinstance(tool_input, dict):
            error = f"tool input must be an object, got {type(tool_input).__name__}"
            self._emit_attempt_failure(tool_use_id, error)
            return _build_strands_error_result(tool_use_id, error)
        try:
            result = self._invoke_project_tool(tool_input, tool_use_id=tool_use_id)
        except Exception as error:
            tool_error = extract_tool_error(error)
            return _build_strands_error_result(
                tool_use_id,
                tool_error.model_message,
            )
        return _build_strands_success_result(
            tool_use_id,
            serialize_tool_result(result),
        )

    def _invoke_project_tool(self, tool_input: dict[str, Any], *, tool_use_id: str) -> ToolResult:
        if self._bridge is not None and tool_use_id != "direct":
            self._bridge.mark_tool_execution(tool_use_id)
        start_time = time.perf_counter()
        if self._event_sink is not None:
            self._event_sink(
                build_loop_event(
                    "progress",
                    "tool_started",
                    tool_name=self._project_tool_spec.name,
                    tool_kind=self._project_tool_spec.tool_kind,
                    tool_use_id=tool_use_id,
                )
            )
        context = build_tool_context(
            services=self._services,
            llm=self._llm,
            workspace_root=self._workspace_root,
            event_sink=self._event_sink,
        )
        try:
            result = self._project_tool_spec.handler(context, **tool_input)
        except Exception as error:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            if self._event_sink is not None:
                error_payload = _build_tool_event_error_payload(error)
                self._event_sink(
                    build_loop_event(
                        "progress",
                        "tool_failed",
                        tool_name=self._project_tool_spec.name,
                        tool_kind=self._project_tool_spec.tool_kind,
                        tool_use_id=tool_use_id,
                        duration_ms=duration_ms,
                        failure_stage="execution",
                        **error_payload,
                    )
                )
            raise
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        if self._executed_tools is not None:
            self._executed_tools.append(
                StrandsToolSummary(
                    name=self._project_tool_spec.name,
                    summary=result.preview_text or result.summary,
                    metadata=result.metadata,
                    duration_ms=duration_ms,
                )
            )
        if self._event_sink is not None:
            result_payload = build_tool_result_payload(
                result,
                detail_collapse_threshold=_TOOL_DETAIL_COLLAPSE_THRESHOLD,
                preview_limit=_TOOL_PREVIEW_LIMIT,
            )
            self._event_sink(
                build_loop_event(
                    "progress",
                    "tool_completed",
                    tool_name=self._project_tool_spec.name,
                    tool_kind=self._project_tool_spec.tool_kind,
                    tool_use_id=tool_use_id,
                    duration_ms=duration_ms,
                    result_preview=result_payload["result_preview"],
                    result_detail=result_payload["result_detail"],
                    collapsible=result_payload["collapsible"],
                    collapsed_by_default=result_payload["collapsed_by_default"],
                )
            )
        return result

    def _emit_attempt_failure(self, tool_use_id: str, error: str) -> None:
        if self._event_sink is None:
            return
        self._event_sink(
            build_loop_event(
                "progress",
                "tool_attempt_failed",
                tool_name=self._project_tool_spec.name,
                tool_kind=self._project_tool_spec.tool_kind,
                tool_use_id=tool_use_id,
                error=error,
                failure_stage="attempt",
            )
        )


def _build_provider_tool_identities(tools: list[Any]) -> dict[str, tuple[str, str]]:
    """收集 provider 工具名到内部工具身份的映射。"""

    identities: dict[str, tuple[str, str]] = {}
    for item in tools:
        provider_tool_name = getattr(item, "provider_tool_name", None)
        internal_tool_name = getattr(item, "internal_tool_name", None)
        tool_kind = getattr(item, "tool_kind", "")
        if not isinstance(provider_tool_name, str) or not isinstance(internal_tool_name, str):
            continue
        identities[provider_tool_name] = (internal_tool_name, str(tool_kind))
    return identities


def _build_strands_success_result(tool_use_id: str, text: str) -> dict[str, Any]:
    """构造一条 Strands 成功工具结果。"""

    return {
        "toolUseId": tool_use_id,
        "status": "success",
        "content": [{"text": text}],
    }


def _build_strands_error_result(tool_use_id: str, error: str) -> dict[str, Any]:
    """构造一条 Strands 失败工具结果。"""

    return {
        "toolUseId": tool_use_id,
        "status": "error",
        "content": [{"text": error}],
    }
