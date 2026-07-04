## Why

当前 TUI 只在少数活动终态后回补 `Thinking ...`，导致活跃 turn 在多种等待空窗里没有任何可见反馈。用户会误判界面卡死，因此需要把“等待时显示 `Thinking ...`”从零散特判收口为统一的时间线规则。

## What Changes

- 将活跃 turn 的等待反馈定义为统一不变量：只要 turn 仍活跃且当前没有真实运行中的可见活动，时间线就显示 waiting-only `Thinking ...`。
- 把等待反馈回补逻辑从 `tool`、`compress` 等局部分支提升到统一的事件后协调流程，覆盖 `thinking`、`assistant`、`system` 以及后续新增活动类型之间的等待空窗。
- 保持真实 `thinking`、`tool`、`assistant`、`compress` 事件的现有让位规则：一旦真实活动到来，waiting-only 占位立即移除或升级，不与真实活动重复并存。
- 补充针对不同等待空窗的 TUI 回归测试，确保最小改动下行为稳定。

## Capabilities

### New Capabilities
- `tui-waiting-feedback-continuity`: 规范活跃 turn 在任意中途等待阶段都持续显示 `Thinking ...` 的时间线行为。

### Modified Capabilities
- 无

## Impact

- 受影响模块：`src/tui/app.py` 的 agent 事件分发与 waiting placeholder 协调逻辑，`test/test_tui_app.py` 的时间线回归测试。
- 不受影响模块：runtime 事件生产、compression token 配置、tool 耗时冻结逻辑、消息视觉样式。
- 风险边界：主要风险是 waiting placeholder 与真实活动的切换时机，需要通过回归测试约束，避免重复显示或错误保留。
