## Why

当前 SmartIPO TUI 的 `/stop` 只能中断本地 Textual worker，不能把取消意图真正传递给 `easyharness.Agent.cancel()`，所以界面看起来停了，底层 agent 实际上可能仍在继续生成或执行工具。这会让 turn 生命周期、排队续跑和用户心智出现分叉，也让“中断回复”停留在视觉假象而不是真实运行时行为。

同时，工具或运行时失败时，timeline 现在可能直接把 traceback 级别的诊断文本展示给最终用户。模型和调试链路确实需要完整异常，但普通用户只需要稳定、简短、可理解的失败摘要；继续把原始堆栈暴露到主对话区，只会把工作台重新拉回调试面板。

## What Changes

- 让 `/stop` 从“仅取消 UI worker”升级为“向 EasyHarness runtime 发出真实取消请求，并以 `cancelled` 事件完成 turn 收口”的完整链路。
- 为 cancelled turn 建立明确的本地生命周期语义：保留已生成的 assistant 半截文本，安全结束 running/tool/thinking 展示项，并在 timeline 中留下一个低存在感的英文停止事件。
- 统一 TUI 对 `AgentEvent.status == "cancelled"` 的处理，避免把取消误渲染成完成、失败或普通系统消息。
- 调整工具失败和系统失败的用户展示策略：主 timeline 只显示概要错误，不再直接展示 traceback 等原始堆栈。
- 保留完整异常与调试诊断给 agent/runtime/测试链路使用，但把这些信息从默认用户可见面移出。

## Capabilities

### New Capabilities
- `tui-runtime-cancellation`: 定义 `/stop` 如何真实驱动 runtime 取消、如何基于 `cancelled` 事件收口当前 turn，以及取消后 timeline/队列/旧事件隔离的行为。
- `user-safe-runtime-failures`: 定义主 timeline 在工具失败或运行时失败时只展示用户级摘要，同时保留完整诊断供 agent 与内部调试使用的展示边界。

### Modified Capabilities
- None.

## Impact

- 受影响代码主要位于 `src/tui/app.py` 的 slash 命令处理、worker 生命周期、turn 收口状态机和 timeline/tool 渲染逻辑。
- 需要调整 `test/test_tui_app.py`，补充真实取消链路、cancelled 事件收口、停止事件留痕和 traceback 不再进入主 timeline 的断言。
- 不新增第三方依赖；优先复用 `easyharness.Agent.cancel()`、现有 `AgentEvent` 的 `cancelled` 状态，以及当前 turn_id 隔离机制。
- 不引入新的跨 UI runtime/timeline 协议；完整异常仍留在 runtime/tool metadata 或内部诊断通道中，默认用户界面只消费摘要。
