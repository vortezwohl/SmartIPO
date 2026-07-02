## ADDED Requirements

### Requirement: Runtime SHALL emit observable tool attempt activity before local execution
当 provider 发出工具尝试意图时，runtime MUST 产生一条可被 UI 消费的工具活动事件，即使该工具最终没有进入本地 handler。

#### Scenario: Provider tool attempt becomes a timeline-visible activity
- **WHEN** callback bridge 观察到 provider 发出的 `toolUse` 意图
- **THEN** runtime MUST 记录一条工具尝试活动事件
- **THEN** 上层 timeline/UI MUST 能展示“工具正在尝试调用”的活动

### Requirement: Runtime SHALL surface provider-side validation failures as activity failures
如果工具调用在 provider 或 SDK 校验阶段失败，而没有进入本地 handler，runtime MUST 仍然发出一条失败活动事件，并携带可诊断的失败文本。

#### Scenario: Validation failure is visible without local handler execution
- **WHEN** provider 或 SDK 因参数缺失、schema 不匹配或类似原因拒绝工具调用
- **THEN** runtime MUST 发出一条失败活动事件
- **THEN** 事件 MUST 明确表明失败发生在本地 handler 之前

#### Scenario: Timeline distinguishes attempt failure from local execution failure
- **WHEN** 一次工具调用失败
- **THEN** timeline/UI MUST 能区分这是 provider-side attempt failure 还是本地执行失败
- **THEN** 用户 MUST 能看到对应阶段的失败信息

### Requirement: TUI default tool exposure SHALL favor a minimal reliable read-only set
Textual workbench 默认暴露给模型的工具集合 MUST 优先选择高频只读最小集合，而不是一次性暴露完整 fileglide 能力面。

#### Scenario: Default workbench starts with minimal read-only tools
- **WHEN** workbench 使用默认 agent 配置启动
- **THEN** 默认工具集合 MUST 至少覆盖基础目录列举和文本读取能力
- **THEN** 默认工具集合 MUST 不要求同时暴露所有写入类、二进制类和 batch 类工具

#### Scenario: Tool activity remains visible for default read-only operations
- **WHEN** 用户在默认 workbench 中发起查看目录或读取文本的任务
- **THEN** 若模型尝试调用对应默认工具，timeline MUST 展示对应工具活动
- **THEN** 若工具调用失败，timeline MUST 展示失败阶段和失败原因
