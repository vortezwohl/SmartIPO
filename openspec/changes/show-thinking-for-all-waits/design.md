## Context

当前 `src/tui/app.py` 已有本地 waiting `Thinking ...` 占位机制，但回补时机分散在少数事件分支里。现状可以覆盖 submit 后首帧等待、部分 `tool` 终态和 `compress` 终态，却无法保证 `thinking` 结束、`assistant` 结束、`system` 插入提示或其他中途空窗时继续给用户可见反馈。

本次变更只针对 TUI 本地时间线状态机，不调整 runtime 事件生产，也不重构已有活动项模型。目标是在最小代码面内把“活跃 turn 的等待反馈”收口成统一规则。

## Goals / Non-Goals

**Goals:**
- 为活跃 turn 建立统一的 waiting feedback 不变量。
- 用单一协调点覆盖所有事件后的等待空窗，而不是继续扩散分支特判。
- 保持现有真实 `thinking`、`tool`、`assistant`、`compress` 活动渲染与冻结逻辑不变。
- 用回归测试锁定 placeholder 回补与让位行为。

**Non-Goals:**
- 不修改 EasyHarness runtime 的事件顺序或事件结构。
- 不调整 compression 策略、token 阈值或消息保留数量。
- 不修改 tool 并发计时、颜色样式或其他已存在的时间线视觉规则。
- 不引入新的活动类型或通用状态机框架。

## Decisions

### 决策 1：在 `_apply_agent_event()` 末尾统一执行等待态协调

将 waiting `Thinking ...` 的回补条件收口到事件分发后的统一步骤中，而不是继续在 `tool`、`compress`、`assistant` 等分支末尾分别补逻辑。

原因：
- 等待空窗是“整个 turn 当前没有真实运行态活动”的全局状态，不属于某一种事件类型独占的责任。
- 统一协调可以天然覆盖未来新增的事件分支，减少遗漏。
- 这样改动面最小，只需要复用已有 `_restore_waiting_thinking_if_turn_still_active()` 和 `_has_visible_running_activity()`，不必重写时间线模型。

备选方案：
- 继续在各分支追加 `_restore_waiting_thinking_if_turn_still_active()` 调用。
  放弃原因：容易再次漏掉新的空窗路径，也会让等待态规则继续分散。

### 决策 2：保留“真实活动优先”规则，只让 waiting placeholder 作为空窗兜底

waiting `Thinking ...` 只在没有真实运行态活动时存在；一旦新的真实 `thinking`、`tool`、`assistant` 或 `compress` 活动开始，waiting placeholder 必须立即移除或被复用升级。

原因：
- 用户需要知道 agent 仍在工作，但不能看到与真实活动重复冲突的假状态。
- 项目内已经有等待态复用和移除逻辑，延续现有模式风险最低。

备选方案：
- 让 waiting placeholder 始终保留，直到 assistant 最终完成。
  放弃原因：会与真实活动并存，破坏时间线可读性。

### 决策 3：验证重点放在事件后空窗，而不是渲染样式

测试新增范围聚焦在事件终态或插入事件后的时间线状态：
- `thinking` 终态后回补
- `assistant` 终态后回补
- `system` 事件后回补
- 后续真实活动到来后占位立即让位

原因：
- 本次需求是反馈连续性，不是视觉风格调整。
- 这些场景正好覆盖当前最容易漏掉的等待窗口。

## Risks / Trade-offs

- [等待态误补到非活跃 turn] → 继续沿用 `_active_turn`、`_stopping_turn_id`、`_cancelled_turn_id` 守卫条件，并用测试覆盖。
- [waiting placeholder 与真实活动重复显示] → 保持所有真实活动开始时的占位移除逻辑，并补“回补后被真实事件接管”的回归测试。
- [统一协调影响既有 `tool`/`compress` 行为] → 复用现有帮助函数，不改变真实活动项的生命周期，只改变回补触发点。
