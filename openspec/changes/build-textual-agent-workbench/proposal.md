## Why

`SmartIPO` 已经有了最小 strands runtime 骨架，但还没有一个真正可用的本地 agent workbench。当前运行时只能做单轮调用，既不能像 Claude Code / OpenClaw 那样在一个会话里连续规划并调用多个工具，也不能把思考、工具调用和流式输出以可追踪的方式展示给用户。

现在推进这项变更是合适的，因为 `strands`、`textual` 和 `fileglide` 已经都具备了。此时补齐会话型 agent loop、过程事件流和本地 TUI，可以在项目还不复杂时把主脑、工具和 UI 的职责边界一次定稳。

## What Changes

- 新增一个基于 Textual 的本地 agent workbench，提供类似 Claude Code / OpenClaw 的单会话交互体验。
- 把当前单轮 `AgentLoop` 升级为会话型 agent loop，使主脑能够在一轮任务内连续调用多个工具直到任务自然结束，而不是只调用一次工具就提前停止。
- 接入完整 fileglide 工具集合，让本地 agent 具备全文件系统 I/O 能力。
- 为主脑思考、工具调用和 assistant 输出建立统一事件流，并把这些事件流式渲染到 TUI 时间线中，同时展示耗时。
- 新增 `src/model_config.py` 作为主脑模型配置总入口，集中管理模型、temperature、top_p、seed 和环境变量映射。

## Capabilities

### New Capabilities
- `textual-agent-workbench`: 定义 SmartIPO 的 Textual 本地 agent workbench、会话型 agent loop、过程事件流和本地交互体验。
- `agent-model-configuration`: 定义 SmartIPO 主脑模型配置总表及其运行时装配约束。
- `session-agent-runtime`: 定义 SmartIPO 会话型主脑运行时、多工具连续调用和过程事件桥接能力。

### Modified Capabilities
- None.

## Impact

- 受影响代码主要位于 `src/core/`、`src/tool/`、`src/tui/`、`src/base/`、`src/service/`、`src/model_config.py` 与 `test/`。
- 运行时将真实使用 `fileglide` Python 包和 `textual`，但不新增新的 UI 框架或 orchestration 框架。
- 本次会引入一个本地默认入口，模型配置将从散落调用参数收敛到 `src/model_config.py`。
