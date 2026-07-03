## Why

当前 SmartIPO 的 TUI 已经直接消费 `easyharness.AgentEvent`，但对 `thinking` 事件的处理仍停留在“本地等待占位”层：runtime 已经发出的 reasoning 文本会在界面层被清空、折叠或直接移除，导致用户既看不到真实的 thinking 内容，也无法在 tool timeline 中看到“先思考、再调工具、再回复”的完整过程。这已经不是文案或配色问题，而是运行时事实在 UI 中被错误降级的问题。

现在修正这件事是合适的，因为当前问题已经具备明确根因和局部修复边界：EasyHarness runtime 会稳定发出 `thinking started/delta/completed` 事件，而现有丢失发生在 `src/tui/app.py` 的本地展示态。此时把 thinking 从“临时占位”收敛为“可见事实”，可以在不引入新 runtime 协议的前提下，让 TUI 行为重新符合直觉、符合事件流事实，也符合后续实现和测试收敛。

## What Changes

- 将 TUI 对 `thinking` 的语义从“仅用于等待 assistant 的临时占位”升级为“当 runtime 提供真实 reasoning 内容时，必须可见的会话事实”。
- 区分两类 thinking：本地 provisional waiting 占位仍可保留，但它只在真实 `thinking` 事件到来前临时存在；一旦 runtime 发出 `thinking delta/completed`，界面必须保留并展示真实内容，而不是继续把它当作可删除占位。
- 建立稳定的阶段衔接规则：同一轮中的 `thinking -> tool -> assistant` 必须按实际发生顺序进入 timeline，可见历史不得因为 assistant started 或 tool started 而抹掉先前真实 thinking 内容。
- 明确 tool timeline 的覆盖边界：tool 活动既要继续保持简洁的一行主摘要，也必须在时间线上承接前置 thinking 历史，形成完整的推理与执行链路，而不是只剩工具结果和 assistant 结论。
- 允许 TUI 将真实 thinking 内容以最符合聊天直觉的方式展示，但不得重新引入跨层共享 timeline 协议，也不得要求 EasyHarness runtime 调整公共 `AgentEvent` 合同。
- **BREAKING** 调整当前 “thinking 在 assistant 首次输出后必须消失” 的界面行为与对应测试断言；依赖该旧行为的 TUI 文本快照和 spec 预期将需要同步更新。

## Capabilities

### New Capabilities
- `tui-runtime-thinking-visibility`: 定义 TUI 如何区分本地 waiting 占位与真实 runtime thinking 事件，并保证真实 thinking 文本在会话中可见、可保留。
- `tui-phase-chronology-visibility`: 定义同一轮中的 thinking、tool 和 assistant 事件如何按实际阶段顺序进入 timeline，避免后置阶段抹掉前置真实历史。

### Modified Capabilities
- None.

## Impact

- 主要影响代码位于 `src/tui/app.py` 的 thinking 生命周期处理、assistant/tool 事件收口逻辑、timeline 可见项筛选和渲染路径。
- 需要同步更新 `test/test_tui_app.py` 中与 `Thinking ...` 临时态、assistant 开始后移除 thinking、tool 前后历史可见性相关的断言，并新增针对真实 `thinking delta/completed` 文本展示的覆盖。
- 不需要修改 `easyharness.AgentEvent`、`src/agent.py`、业务工具实现或默认工具装配；runtime 事件来源保持不变。
- 可能需要同步修正相关 OpenSpec 中把 thinking 定义为“必须消失的临时态”的行为描述，确保规范与实现目标一致。
