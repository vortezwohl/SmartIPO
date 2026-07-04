## Why

当前 TUI 把 `Thinking ...` 同时当成 waiting 占位、真实 thinking 活动和历史 thinking 表面，导致用户无法稳定预期它何时出现、何时被替换、何时应该回来。现在最明显的问题是：真实动作一旦结束而 turn 仍未结束，时间线经常出现没有任何 `Thinking ...` 的空窗，看起来像卡死。

## What Changes

- 明确定义 `Thinking ...` 为 turn 内“下一个真实动作开始前”的前置占位符，而不是与真实动作长期并存的全局横幅。
- 规定真实 `tool`、`assistant`、`compress`、`thinking` 活动开始时可以覆盖当前 `Thinking ...` 占位，但这些活动结束后只要 turn 尚未结束，就必须重新回补 `Thinking ...`。
- 为所有运行中的 thinking 指示器增加统一的 `...` 动画，避免当前静态文案看起来像死文本。
- 把 waiting placeholder、真实 thinking 活动、thinking 历史消息三类状态拆清楚，并补齐对应回归测试。

## Capabilities

### New Capabilities
- `tui-turn-thinking-placeholder-lifecycle`: 规范 turn 内 `Thinking ...` 占位符与真实动作之间的替换、回补和结束规则。
- `tui-thinking-indicator-animation`: 规范运行中 thinking 指示器的动画化展示。

### Modified Capabilities
- 无

## Impact

- 受影响模块：`src/tui/app.py` 的 thinking / tool / assistant / compress 时间线状态机与渲染逻辑，`test/test_tui_app.py` 的时间线回归测试。
- 非目标模块：EasyHarness runtime、工具实现、compression token 配置、tool 真实耗时统计。
- 风险边界：主要风险是 placeholder 与真实动作的切换时机和历史 thinking 可见性，需要通过状态机梳理与回归测试控制。
