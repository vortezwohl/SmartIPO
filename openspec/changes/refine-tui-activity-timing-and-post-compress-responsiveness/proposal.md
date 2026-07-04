## Why

当前 TUI 在多条 tool call 并发或重叠运行时，会把运行中的计时显示成近似同步增长，但在工具结束后又冻结为彼此不同的最终耗时；同时，在 `Conversation compressed` 之后到下一批真实 `thinking`/`assistant` 事件到来之前，界面会出现一段没有任何活动反馈的空窗。两种现象都会让用户误判为 TUI 卡住或状态不可信，因此需要用统一、可验证的本地活动反馈模型修正。

## What Changes

- 统一 tool 活动项在“运行中显示”和“终态冻结”两种阶段的计时口径，确保每条运行中的工具活动都表现为独立计时。
- 为 compression 终态后的活跃 turn 恢复本地 `Thinking ...` 占位反馈，避免在真实后续事件到来前出现长时间空白。
- 明确区分“活动关联修复”和“活动显示修复”的责任边界，避免继续把可见反馈问题混入 tool 生命周期收口逻辑。
- 增加针对并发 tool 运行态显示、compression 后反馈恢复、后续真实事件接管占位的回归验证。

## Capabilities

### New Capabilities
- `tui-activity-feedback-continuity`: 规范 TUI 对工具活动计时显示与 compression 后过渡反馈的可见行为，确保用户始终看到可信、连续的活动状态。

### Modified Capabilities
- 无

## Impact

- 受影响模块：`src/tui/app.py` 的 timeline 活动状态机与本地计时刷新逻辑、相关 TUI 测试。
- 受影响系统：tool 运行态耗时显示、compression 终态后的本地占位反馈、turn 活跃期的时间线可见性。
- 非目标模块：工具执行器、业务工具实现、模型配置、压缩预算配置。
