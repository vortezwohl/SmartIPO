## Context

当前仓库已经把 tool 生命周期收口问题和 compression 单条活动收口问题分别修到“事件归属正确”的层面，但 TUI 仍存在两个纯展示层缺陷：

- 多条 tool 活动同时处于运行态时，界面上的实时计时表现近似同步增长，用户无法感知每条工具是否真的独立运行；等终态事件到来后，又突然冻结成彼此不同的最终耗时。
- compression 结束到下一批真实 `thinking` / `assistant` 事件到来之间，当前活跃 turn 没有任何本地反馈，占位 `Thinking ...` 已被移除，用户会误以为程序卡死。

这两个问题有共同点：都不是业务工具、模型配置或 runtime 事件协议本身错误，而是 TUI 本地活动状态机在“运行中显示”与“终态接管”之间缺少一致的过渡策略。

约束条件：

- 不能再把展示问题误修成 runtime 或 provider 适配问题；否则会扩大影响面并增加维护成本。
- 终态耗时仍应以上游 `event.duration_ms` 为准，因为那是工具真实完成时的权威结果。
- 本地 `Thinking ...` 只应作为活跃 turn 的过渡占位，真实 `thinking`、`assistant`、`tool` 或 `compress` 事件一旦到来，必须立刻让位。

## Goals / Non-Goals

**Goals:**

- 让每条运行中的 tool 活动都基于自身独立的本地单调时钟显示实时耗时，而不是共享 wall-clock 视觉效果。
- 保持 tool 终态冻结值继续以上游 `duration_ms` 为准，确保最终结果权威且稳定。
- 在 compression 终态后，如果当前 turn 仍活跃且暂时没有新的真实运行态事件，立即恢复本地 `Thinking ...` 占位。
- 用测试覆盖“并发 tool 运行中显示独立计时”和“compression 后占位反馈及时恢复”两类关键体验。

**Non-Goals:**

- 不修改 EasyHarness runtime 的事件协议、tool 执行器或 conversation manager。
- 不改变 tool / compress / thinking 的文案、配色、终态摘要规则。
- 不重构整个 turn 队列或聊天生命周期，只修补当前展示层缺失的状态过渡。

## Decisions

### 1. 为运行中的 timeline 活动引入本地单调计时源，独立于终态权威耗时

决策：在 TUI 本地为需要实时刷新的活动项记录单调时钟起点，例如存入 `_TimelineItem.metadata["local_started_monotonic"]`；运行中刷新时优先用该值计算实时耗时，终态到来后再切回上游 `duration_ms` 作为最终冻结值。

原因：

- `datetime.now()` 与 `started_at` 的 wall-clock 差值适合表达“从某个时间点起已经过了多久”，但不适合在多条活动并列显示时表达“每条调用自己的独立计时体验”。
- `time.perf_counter()` 单调、稳定、无系统时钟跳变问题，更适合作为本地实时 UI 计时源。
- 继续保留上游 `duration_ms` 作为终态权威值，既能保证展示连续性，也不会篡改真实完成耗时。

备选方案：

- 继续使用 `started_at` 刷新运行态，再接受终态冻结跳变。
  不采用，因为这正是当前体验问题的来源。
- 运行态和终态都完全使用本地单调时钟。
  不采用，因为会让最终显示偏离 runtime 的权威结果。

### 2. 把 compression 结束后的空窗恢复为通用“活跃 turn 反馈回补”机制

决策：新增一个小的 TUI 本地帮助函数，用来判断“当前 turn 仍活跃，但暂时没有任何可见运行态事件”；在这种情况下自动恢复 provisional `Thinking ...` 占位。该逻辑优先挂在 compression 终态后触发，并可复用到其它造成空窗的终态路径。

原因：

- 当前 `_start_local_thinking()` 机制已经存在，只是 tool/compress 等真实事件到来时会把 waiting-only 占位移除；缺的是“真实事件结束但下一阶段尚未开始”时的回补。
- 复用现有 provisional thinking 比伪造 runtime `thinking started` 更干净，不会污染事件语义。
- 把它设计成通用判断函数，比在 `compress completed` 分支里硬编码更稳，后续 tool 批次结束后的空窗也能复用。

备选方案：

- 在 runtime 层强行补发一条 `thinking started`。
  不采用，因为这会把本地过渡反馈混成公共事件协议，责任边界错误。
- 只在 compression 完成时直接插入一条 system 提示。
  不采用，因为它无法表达“agent 仍在继续思考/处理”的状态。

### 3. 影响范围严格限制在 TUI 状态机与对应测试

决策：实现只触及 `src/tui/app.py` 及其测试，不扩散到业务工具、agent composition、EasyHarness runtime 或 OpenSpec 之外的其它层。

原因：

- 从定位结果看，两个问题都发生在 TUI 本地状态过渡和刷新机制。
- 最优雅的解法是让修复边界与缺陷边界一致，避免继续把展示责任推给上游。

## Risks / Trade-offs

- [Risk] 引入本地单调计时字段后，若清理时机不完整，终态后仍可能被刷新逻辑继续更新。
  → Mitigation：所有终态路径统一清除本地运行计时元数据，并在测试中断言终态后时长不再增长。
- [Risk] compression 后的占位回补若触发过度，可能在真实 `thinking` 历史或 assistant 输出前短暂闪烁。
  → Mitigation：只在当前 turn 活跃且无其它运行态 item 时回补，并让真实事件一到就立即移除 provisional thinking。
- [Risk] 同时存在 tool、compress、assistant 终态收口时，通用回补条件可能误判。
  → Mitigation：把“有无运行态”的判断写成显式函数，并通过多场景测试固定行为。

## Migration Plan

1. 在 TUI timeline item 的本地状态中引入单调计时起点，并调整运行中刷新逻辑。
2. 在 tool / thinking / compress 等活动项的 started 与 terminal 路径中统一维护本地计时元数据。
3. 新增“活跃 turn 反馈回补”函数，并在 compression 终态后触发。
4. 补充 TUI 回归测试，验证独立计时显示与 compression 后占位恢复。

回滚策略：

- 若本地计时或回补逻辑引入新的闪烁或错误占位，可整体回滚到现有 `src/tui/app.py` 逻辑。
- 因为本次变更只影响 UI 本地状态，没有数据迁移和协议变更，回滚成本低。

## Open Questions

- 是否需要把“活跃 turn 反馈回补”触发点仅限定在 compression 终态，还是顺带覆盖“最后一条 tool 结束后到 assistant/thinking 真正恢复前”的空窗；当前更推荐做成通用逻辑。
- 若运行中的 tool 已经自带高精度 `started_at`，是否仍需要保留 `started_at` 参与本地实时显示；当前建议只把它保留为事件关联和调试信息，不再作为实时显示主时钟。
