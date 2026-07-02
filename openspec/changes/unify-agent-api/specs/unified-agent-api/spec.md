## ADDED Requirements

### Requirement: 系统必须只暴露单一会话型 Agent 公开 API
系统 MUST 只保留一个公开主脑控制器，并将其作为本地 workbench 与后续调用方唯一依赖的主脑 API。该公开控制器 MUST 代表单会话、多工具、可持续处理多轮输入的语义。

#### Scenario: workbench 装配主脑控制器
- **WHEN** Textual workbench 需要创建本地主脑控制器
- **THEN** 系统 MUST 使用单一公开 `Agent` 类型完成装配
- **AND** workbench SHALL NOT 依赖额外的 `AgentLoop` 或 `AgentSessionLoop` 名称

### Requirement: 系统不得继续暴露单轮 run_once 风格入口
系统 MUST 删除或停止暴露 `run_once(...)` 这一类单轮公开入口，不得继续把单轮调用作为与会话调用并列的正式 API。

#### Scenario: 调用方查看公开主脑 API
- **WHEN** 调用方通过 `src/core/` 使用主脑控制器
- **THEN** 系统 MUST 不再暴露 `run_once(...)` 风格的公开方法
- **AND** 调用方 MUST 通过统一的会话型 `run(...)` 入口提交任务

### Requirement: 统一 Agent API 必须保留当前会话行为
系统在收敛到单一 `Agent` 公开 API 后，MUST 继续保留当前会话历史、多工具连续调用和统一事件流行为，不得因为 API 简化而退回单轮执行模型。

#### Scenario: 一个任务需要连续调用多个工具
- **WHEN** 用户提交的任务需要先读取信息再执行后续动作
- **THEN** 统一后的 `Agent` MUST 继续在同一会话回合中连续调用多个工具
- **AND** 系统 MUST 在任务自然结束后才返回最终 assistant 回复
