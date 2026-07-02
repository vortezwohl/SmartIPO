"""本地 agent workbench 运行时测试。

该文件聚焦验证本次改动的最小闭环：集中模型配置、统一 `Agent` 会话 API、
多工具事件顺序，以及 fileglide 在本地会话中的真实文件 I/O 能力。
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.core.agent import Agent
from src.core.events import LoopEvent, build_loop_event
from src.core.strands_runtime import StrandsRunResult
from src.model_config import AGENT_SESSION_ROUND, BRAIN_MODEL_CONFIGS, CHANNEL_CONFIGS
from src.service.model_hub import create_default_brain_model, validate_model_config
from src.tool.contracts import ToolContext, ToolResult, ToolSpec
from src.tool.registry import ToolRegistry, build_default_tool_registry


class _FakeSessionRuntime:
    """用于验证会话 runner 复用与多工具连续调用。"""

    requires_model = False

    def __init__(self) -> None:
        self.created_runner_count = 0
        self.prompts: list[str] = []

    def create_session_runner(
        self,
        *,
        model,
        tools,
        system_prompt: str,
        event_sink=None,
    ):
        _ = (model, system_prompt)
        self.created_runner_count += 1
        tool_map = {item.tool_name: item for item in tools}
        runtime = self

        class _Runner:
            def run(self, prompt: str) -> StrandsRunResult:
                runtime.prompts.append(prompt)
                if event_sink is not None:
                    event_sink(
                        build_loop_event(
                            "progress",
                            "thinking_started",
                            message="正在思考下一步。",
                        )
                    )
                tool_map["first_tool"]()
                tool_map["second_tool"]()
                if event_sink is not None:
                    event_sink(
                        build_loop_event(
                            "assistant",
                            "assistant_stream_started",
                            message="正在生成回复。",
                        )
                    )
                    event_sink(
                        build_loop_event(
                            "assistant",
                            "assistant_stream_delta",
                            text="done",
                        )
                    )
                    event_sink(
                        build_loop_event(
                            "assistant",
                            "assistant_stream_completed",
                            text="done",
                            fallback=False,
                        )
                    )
                return StrandsRunResult(text="done")

        return _Runner()


class _FakeFileIoRuntime:
    """用于验证 fileglide 可在主脑会话中执行真实文件 I/O。"""

    requires_model = False

    def create_session_runner(
        self,
        *,
        model,
        tools,
        system_prompt: str,
        event_sink=None,
    ):
        _ = (model, system_prompt, event_sink)
        tool_map = {item.tool_name: item for item in tools}

        class _Runner:
            def run(self, prompt: str) -> StrandsRunResult:
                tool_map["text.write"](target="note.txt", content=prompt)
                tool_map["text.read"](target="note.txt")
                return StrandsRunResult(text="file done")

        return _Runner()


class _FakeFailureRuntime:
    """用于验证工具失败事件不会被伪装成成功。"""

    requires_model = False

    def create_session_runner(
        self,
        *,
        model,
        tools,
        system_prompt: str,
        event_sink=None,
    ):
        _ = (model, system_prompt, event_sink)
        tool_map = {item.tool_name: item for item in tools}

        class _Runner:
            def run(self, prompt: str) -> StrandsRunResult:
                _ = prompt
                tool_map["broken_tool"]()
                return StrandsRunResult(text="should not reach")

        return _Runner()


class ModelConfigTests(unittest.TestCase):
    """验证集中模型配置装配与覆写保护。"""

    def test_default_brain_model_comes_from_model_config(self) -> None:
        """主脑模型必须从 `src/model_config.py` 读取集中配置。"""

        self.assertIn("deepseek", CHANNEL_CONFIGS)
        self.assertEqual(BRAIN_MODEL_CONFIGS[AGENT_SESSION_ROUND].channel, "deepseek")

        with patch.dict(
            os.environ,
            {
                "API_KEY": "test-key",
                "API_BASE": "https://example.com/v1",
            },
            clear=False,
        ):
            validate_model_config()
            model = create_default_brain_model()

        self.assertEqual(model.config["model_id"], "openai/deepseek-v4-flash")
        self.assertEqual(model.client_args["api_key"], "test-key")
        self.assertEqual(model.client_args["api_base"], "https://example.com/v1")
        self.assertEqual(model.config["params"]["temperature"], 0.2)
        self.assertEqual(model.config["params"]["top_p"], 0.9)
        self.assertEqual(model.config["params"]["seed"], 42)

    def test_sampling_overrides_are_rejected(self) -> None:
        """调用点不得直接覆写集中采样参数。"""

        with patch.dict(os.environ, {"API_KEY": "test-key"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "主脑采样参数必须来自 src/model_config.py"):
                create_default_brain_model(temperature=0.01)


class SessionRuntimeTests(unittest.TestCase):
    """验证会话型运行时、多工具事件与 fileglide 能力。"""

    def test_session_loop_reuses_one_runner_and_records_history(self) -> None:
        """同一内存会话应复用一个 runner，并允许一轮内连续调用多个工具。"""

        events: list[LoopEvent] = []
        calls: list[str] = []

        def _make_tool(name: str) -> ToolSpec:
            def _handler(_context: ToolContext) -> ToolResult:
                calls.append(name)
                return ToolResult(content=name, summary=f"{name} ok")

            return ToolSpec(
                name=name,
                description=f"{name} description",
                display_name=name,
                input_schema={"type": "object", "properties": {}},
                handler=_handler,
            )

        registry = ToolRegistry()
        registry.register(_make_tool("first_tool"))
        registry.register(_make_tool("second_tool"))
        runtime = _FakeSessionRuntime()
        agent = Agent(
            model=None,
            tool_registry=registry,
            system_prompt="You are a test agent.",
            runtime=runtime,
            event_sink=events.append,
        )

        first = agent.run("first job")
        second = agent.run("second job")

        self.assertEqual(first.text, "done")
        self.assertEqual(second.text, "done")
        self.assertEqual(runtime.created_runner_count, 1)
        self.assertEqual(runtime.prompts, ["first job", "second job"])
        self.assertEqual(calls, ["first_tool", "second_tool", "first_tool", "second_tool"])
        self.assertEqual(
            [event.event_type for event in events[:6]],
            [
                "thinking_started",
                "tool_started",
                "tool_completed",
                "tool_started",
                "tool_completed",
                "assistant_stream_started",
            ],
        )
        self.assertEqual(len(agent.history), 4)
        self.assertEqual(agent.history[0].content, "first job")
        self.assertEqual(agent.history[1].content, "done")

    def test_tool_failure_stays_visible_and_bubbles_up(self) -> None:
        """工具失败时应产生失败事件并继续向上抛异常。"""

        events: list[LoopEvent] = []

        def _broken_handler(_context: ToolContext) -> ToolResult:
            raise RuntimeError("broken")

        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                name="broken_tool",
                description="broken tool",
                display_name="Broken Tool",
                input_schema={"type": "object", "properties": {}},
                handler=_broken_handler,
            )
        )
        agent = Agent(
            model=None,
            tool_registry=registry,
            system_prompt="test",
            runtime=_FakeFailureRuntime(),
            event_sink=events.append,
        )

        with self.assertRaisesRegex(RuntimeError, "broken"):
            agent.run("boom")

        self.assertIn("tool_failed", [event.event_type for event in events])

    def test_fileglide_tools_support_real_file_io_without_shell(self) -> None:
        """本地 agent 会话应能直接通过 fileglide 完成常见文件 I/O。"""

        with tempfile.TemporaryDirectory() as temp_dir:
            agent = Agent(
                model=None,
                tool_registry=build_default_tool_registry(),
                system_prompt="Use tools.",
                runtime=_FakeFileIoRuntime(),
                tool_names=["text.write", "text.read"],
                workspace_root=temp_dir,
            )

            result = agent.run("hello from fileglide")

            self.assertEqual(result.text, "file done")
            note_path = Path(temp_dir) / "note.txt"
            self.assertTrue(note_path.exists())
            self.assertEqual(note_path.read_text(encoding="utf-8"), "hello from fileglide")


if __name__ == "__main__":
    unittest.main()
