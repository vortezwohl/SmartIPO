## Context

当前 `src/tui/app.py` 对 `thinking` 只区分两类含义：可删除的 waiting-only 占位，以及升级为历史消息的真实 thinking 文本。这个设计在最初足够简单，但现在同时承担了三种不同职责：
- turn 空窗期的前置占位符
- runtime 真实 thinking 活动
- 已完成的 thinking 历史消息

由于这三类状态被压在同一套隐式标记里，结果是：
- `tool`、`assistant`、`compress` 开始时会删除 placeholder
- 但动作结束后是否需要回补 placeholder，依赖零散的后置逻辑
- `Thinking ...` 目前还是静态文本，不是动画化指示器

这类问题继续靠分支补丁会越来越脆弱，因此需要把 thinking placeholder 的生命周期收口成清晰规则。

## Goals / Non-Goals

**Goals:**
- 把 `Thinking ...` 建模为 turn 内“下一个真实动作开始前”的统一前置占位符。
- 明确真实动作开始时可以覆盖占位符，动作结束后若 turn 仍活跃则必须重新回补。
- 为所有运行中的 thinking 指示器增加统一 `...` 动画。
- 在不改动 runtime 事件结构的前提下，补齐 TUI 状态机和回归测试。

**Non-Goals:**
- 不改变 EasyHarness / Strands 的事件生产顺序。
- 不重做整体时间线 UI 结构，也不引入新的全局面板。
- 不改变 tool、assistant、compress 的权威终态耗时来源。
- 不把已完成的 thinking 历史消息做成持续动画。

## Decisions

### 决策 1：把 thinking 占位改为显式的 turn 空窗状态，而不是隐式附着在 thinking 项上

实现上应把“waiting placeholder”作为独立可判定的展示状态，而不是继续把它与真实 thinking 活动共用同一套含义模糊的 `ephemeral/history/provisional` 组合。

原因：
- 你当前要求的语义是“空窗占位 -> 真实动作覆盖 -> 动作结束后回补 -> 下一个动作再覆盖”，这是阶段切换，不是单条消息属性切换。
- 继续在同一 thinking 项上打补丁，会让历史 thinking 与 waiting placeholder 之间的边界越来越脆。

备选方案：
- 继续沿用现有 metadata 标记，只追加更多分支特判。
  放弃原因：短期能工作，但长期会继续出现“某一类动作后没回补”的遗漏。

### 决策 2：定义统一的“前置占位生命周期”

统一规则如下：
- turn 开始后，如果当前没有真实运行中的阶段，就显示 `Thinking ...`
- 真实 `thinking/tool/assistant/compress` 阶段开始时，移除或复用当前占位
- 真实阶段结束后，如果 turn 未结束且下一个真实阶段尚未开始，立刻回补 `Thinking ...`
- turn 完全结束后，移除最后的占位

原因：
- 这与用户心智一致，也最容易写成稳定测试。
- 它允许时间线在视觉上保持“始终有下一阶段将要发生”的反馈，而不会与真实阶段并存冲突。

备选方案：
- 让 placeholder 与真实动作并存。
  放弃原因：时间线会冗余，而且与你刚刚澄清的语义不一致。

### 决策 3：动画只作用于运行中的 thinking 指示器

动画化的范围应当仅限于运行中的 `Thinking` 指示器，包括：
- turn 空窗占位符
- runtime 真实 thinking 运行态

已升级为历史消息的 `Assistant (Thinking) > ...` 不参与动画。

原因：
- 历史消息是结果，不是活动。
- 如果历史消息持续变化，会破坏时间线稳定性和可读性。

备选方案：
- 所有包含 thinking 字样的行都做动画。
  放弃原因：历史消息会闪烁，且没有信息增益。

### 决策 4：动画帧应从计时刷新时钟派生，不新增独立定时器

当前 TUI 已有固定间隔的运行态刷新。动画帧应复用这套节拍，根据当前时间或运行毫秒数派生 `.` / `..` / `...`，避免新增独立 animation timer。

原因：
- 最小改动。
- 不会再引入新的同步问题。

## Risks / Trade-offs

- [placeholder 与真实阶段切换边界仍然有遗漏] → 用状态机驱动测试，覆盖 submit 后、tool 后、assistant 后、compress 后、thinking 后的回补。
- [历史 thinking 被误当成运行态动画] → 明确把动画判定限制在 waiting / running thinking 项，不影响 history thinking。
- [显式生命周期改动触碰现有测试假设] → 保留历史 thinking chronology 测试，并新增空窗覆盖测试，避免回归。

## Migration Plan

- 仅修改本地 TUI 状态机与渲染逻辑，无外部迁移步骤。
- 若回归测试暴露现有 `thinking` 元数据语义过于混乱，可在实现阶段再考虑引入更明确的本地阶段标记。

## Open Questions

- 无。当前用户语义已经足够明确：placeholder 允许被真实动作覆盖，但动作结束后只要 turn 未结束就必须回来。
