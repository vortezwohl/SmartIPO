## ADDED Requirements

### Requirement: turn 内空窗必须显示 Thinking 前置占位符
系统 MUST 在 turn 已开始但当前没有真实运行中的 `thinking`、`tool`、`assistant` 或 `compress` 阶段时，显示 `Thinking ...` 作为下一个真实动作开始前的前置占位符。

#### Scenario: 提交后首个真实事件到来前显示 Thinking 占位符
- **WHEN** 用户提交了一条新 turn，且 runtime 尚未开始任何真实 `thinking`、`tool`、`assistant` 或 `compress` 阶段
- **THEN** 系统 MUST 立即显示 `Thinking ...` 占位符

#### Scenario: 真实动作结束后在下一动作开始前回补 Thinking 占位符
- **WHEN** turn 内某个真实 `thinking`、`tool`、`assistant` 或 `compress` 阶段进入终态，且 turn 尚未结束且当前没有其他真实运行中的阶段
- **THEN** 系统 MUST 立即重新显示 `Thinking ...` 占位符

### Requirement: 真实动作开始时必须覆盖当前 Thinking 前置占位符
系统 MUST 在真实 `thinking`、`tool`、`assistant` 或 `compress` 阶段开始时，移除、复用或替换当前 `Thinking ...` 前置占位符，避免占位符与真实动作并存冲突。

#### Scenario: tool 开始时覆盖 Thinking 占位符
- **WHEN** turn 当前显示 `Thinking ...` 前置占位符，随后收到真实 `tool started` 事件
- **THEN** 系统 MUST 移除或替换该占位符，并显示对应的 tool 活动行

#### Scenario: assistant 开始时覆盖 Thinking 占位符
- **WHEN** turn 当前显示 `Thinking ...` 前置占位符，随后收到真实 `assistant started` 事件
- **THEN** 系统 MUST 移除或替换该占位符，并显示对应的 assistant 活动行

### Requirement: turn 结束后必须移除最后的 Thinking 占位符
系统 MUST 在 turn 已经自然完成、失败收口或取消收口后移除最后的 `Thinking ...` 前置占位符，避免在已结束 turn 上残留活动态指示。

#### Scenario: turn 完成后不再保留 Thinking 占位符
- **WHEN** 当前 turn 已进入完成、失败或取消后的收尾状态
- **THEN** 系统 MUST 不再显示该 turn 的 `Thinking ...` 前置占位符
