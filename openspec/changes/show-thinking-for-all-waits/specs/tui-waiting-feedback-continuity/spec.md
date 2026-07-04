## ADDED Requirements

### Requirement: 活跃 turn 的等待空窗必须持续显示 Thinking 占位
系统 MUST 在当前 turn 仍活跃且时间线中不存在真实运行中的 `thinking`、`tool`、`assistant` 或 `compress` 活动时，显示 waiting-only `Thinking ...` 占位，避免中途等待阶段出现无反馈空窗。

#### Scenario: thinking 终态后回补 waiting placeholder
- **WHEN** 活跃 turn 收到 `thinking` 的 `completed`、`failed` 或 `cancelled` 终态事件，且当前没有其他真实运行中的可见活动
- **THEN** 系统 MUST 立即恢复一条 waiting-only `Thinking ...` 占位

#### Scenario: assistant 终态后回补 waiting placeholder
- **WHEN** 活跃 turn 收到 `assistant` 的 `completed`、`failed` 或 `cancelled` 终态事件，且当前没有其他真实运行中的可见活动
- **THEN** 系统 MUST 立即恢复一条 waiting-only `Thinking ...` 占位

#### Scenario: system 事件插入后回补 waiting placeholder
- **WHEN** 活跃 turn 收到一条 `system` 事件并将其追加到时间线，且当前没有其他真实运行中的可见活动
- **THEN** 系统 MUST 保持或恢复 waiting-only `Thinking ...` 占位

### Requirement: 真实活动到来时必须立即接管 waiting placeholder
系统 MUST 在新的真实 `thinking`、`tool`、`assistant` 或 `compress` 活动到来时，立即移除 waiting-only `Thinking ...` 占位，或将其复用为真实活动条目，避免假占位与真实活动并存。

#### Scenario: 后续真实 thinking 复用 waiting placeholder
- **WHEN** 活跃 turn 已存在 waiting-only `Thinking ...` 占位，随后收到真实 `thinking started` 事件
- **THEN** 系统 MUST 复用该占位或将其升级为真实 `thinking` 活动，而不是再新增一条重复占位

#### Scenario: 后续真实 tool 或 assistant 移除 waiting placeholder
- **WHEN** 活跃 turn 已存在 waiting-only `Thinking ...` 占位，随后收到真实 `tool`、`assistant` 或 `compress` 事件
- **THEN** 系统 MUST 立即移除 waiting-only 占位
- **AND** 系统 MUST NOT 同时保留与真实活动重复冲突的等待占位
