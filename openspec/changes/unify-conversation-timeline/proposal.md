## Why

当前 SmartIPO 的会话时间线逻辑主要内嵌在 Textual UI 里：思考占位、工具计时、工具结果摘要和流式输出都是由 TUI 直接消费 `LoopEvent` 后临时拼出来的。这已经开始限制功能演进，因为你现在要的“工具结果卡片 + 长结果折叠 + thinking 动画”不仅服务 TUI，未来 WebUI 也必须复用同一套语义。

## What Changes

- 在 `src/core` 引入跨 UI 复用的会话时间线表示层，把运行时事件归约为稳定的 timeline entries。
- 把工具调用展示升级为一等时间线项目，包含运行状态、耗时、结果概要、长结果详情和默认折叠建议。
- 把 thinking 状态从“写死在 TUI 文案里”改为通用活动状态，由 UI 本地渲染 `thinking . .. ...` 动画，不向运行时事件流注入动画噪音。
- 让 Textual workbench 改为消费通用 timeline state，而不是自己直接解释底层 `LoopEvent`。
- 为未来 WebUI 预留同一份 timeline reducer / state / formatting 语义，不要求第二套解释逻辑。

## Capabilities

### New Capabilities
- `conversation-timeline-state`: 定义跨 UI 复用的会话时间线状态模型和事件归约规则。
- `activity-presence-rendering`: 定义 thinking / tool-running 这类活动状态如何以 UI 本地动画和展示规则呈现。

### Modified Capabilities
- None.

## Impact

- 受影响代码主要位于 `src/core/events.py`、新的 `src/core/timeline*.py`、`src/core/strands_runtime.py`、`src/tui/app.py` 与相关测试。
- 不新增第三方依赖，不改变 Agent/ToolRegistry 的对外调用方式。
- 这是一次表示层收敛，不是 strands runtime 或具体 UI 框架的架构重写。
