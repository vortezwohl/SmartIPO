## ADDED Requirements

### Requirement: 并发工具活动必须显示彼此独立的运行中计时
系统 MUST 让每条处于运行中的工具活动依据自身独立的本地运行时钟显示实时耗时，而不是表现为多条工具活动近似同步增长的共享计时效果。

#### Scenario: 多条工具活动同时运行时分别显示独立耗时
- **WHEN** 同一 turn 中存在两条或以上同时处于运行中的工具活动
- **THEN** 系统 MUST 为每条工具活动独立刷新其运行中耗时显示
- **AND** 系统 MUST NOT 把这些工具活动显示成共享同一计时节奏的近似同步增长

### Requirement: 工具终态必须冻结为权威最终耗时
系统 MUST 在工具活动进入 `completed`、`failed` 或 `cancelled` 后停止本地实时刷新，并把该活动项固定为终态事件给出的最终耗时。

#### Scenario: 工具完成后冻结为终态耗时
- **WHEN** 某条工具活动收到终态事件且事件中包含最终 `duration`
- **THEN** 系统 MUST 停止继续刷新该活动项的本地运行中耗时
- **AND** 系统 MUST 使用终态事件给出的最终耗时作为该活动项的冻结显示值

### Requirement: compression 终态后必须恢复连续的活跃反馈
如果当前 turn 在 compression 结束后仍然活跃且下一批真实 `thinking`、`assistant`、`tool` 或 `compress` 事件尚未到来，系统 MUST 立即恢复本地 `Thinking ...` 占位，避免时间线出现长时间无反馈空窗。

#### Scenario: compression 完成后回补本地 thinking 占位
- **WHEN** compression 活动进入终态且当前 turn 仍然活跃
- **THEN** 系统 MUST 在没有其它真实运行态活动项时恢复本地 `Thinking ...` 占位
- **AND** 用户 MUST 能持续看到 agent 仍在继续处理的可见反馈

#### Scenario: 真实后续事件到来后占位立即让位
- **WHEN** compression 终态后恢复的本地 `Thinking ...` 占位之后收到了真实 `thinking`、`assistant`、`tool` 或新的 `compress` 事件
- **THEN** 系统 MUST 立即移除 waiting-only 占位或将其升级为真实历史
- **AND** 系统 MUST NOT 同时保留与真实后续事件重复冲突的假占位反馈
