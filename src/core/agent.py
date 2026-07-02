"""主脑会话控制器入口。

该文件只保留一个公开主脑控制器 `Agent`。它代表 SmartIPO 当前真实使用的
会话语义：维护内存历史、复用持久 session runner，并在一次任务中连续调用
多个工具直到自然结束。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.events import LoopEventSink
from src.core.strands_runtime import StrandsRunResult, StrandsRuntime, build_strands_tool
from src.tool.registry import ToolRegistry


@dataclass(slots=True)
class SessionTurn:
    """描述一轮已经进入会话历史的对话内容。"""

    role: str
    content: str


class Agent:
    """执行单会话主脑调用的公开控制器。"""

    def __init__(
        self,
        *,
        model: Any,
        tool_registry: ToolRegistry,
        system_prompt: str,
        runtime: Any | None = None,
        tool_names: list[str] | tuple[str, ...] | None = None,
        services: dict[str, Any] | None = None,
        llm: Any | None = None,
        event_sink: LoopEventSink | None = None,
        workspace_root: str = ".",
    ) -> None:
        self._model = model
        self._tool_registry = tool_registry
        self._runtime = runtime or StrandsRuntime()
        self._system_prompt = system_prompt
        self._tool_names = tuple(tool_names or ())
        self._services = services or {}
        self._llm = llm
        self._event_sink = event_sink
        self._workspace_root = workspace_root
        self._history: list[SessionTurn] = []
        self._session_runner = self._build_session_runner()

    @property
    def history(self) -> tuple[SessionTurn, ...]:
        """返回当前内存会话历史。"""

        return tuple(self._history)

    def reset(self) -> None:
        """清空当前会话历史并重建会话 runner。"""

        self._history = []
        self._session_runner = self._build_session_runner()

    def run(self, prompt: str) -> StrandsRunResult:
        """执行一轮会话输入。"""

        result = self._session_runner.run(prompt)
        self._history.append(SessionTurn(role="user", content=prompt))
        self._history.append(SessionTurn(role="assistant", content=result.text))
        return result

    def _build_session_runner(self):
        """构造底层持久会话 runner。"""

        if getattr(self._runtime, "requires_model", True) and self._model is None:
            raise RuntimeError(
                "Agent requires a model when runtime.requires_model is true."
            )
        return self._runtime.create_session_runner(
            model=self._model,
            tools=[
                build_strands_tool(
                    tool_spec=tool_spec,
                    services=self._services,
                    llm=self._llm,
                    event_sink=self._event_sink,
                    workspace_root=self._workspace_root,
                )
                for tool_spec in self._tool_registry.list_tools(*self._tool_names)
            ],
            system_prompt=self._system_prompt,
            event_sink=self._event_sink,
        )
