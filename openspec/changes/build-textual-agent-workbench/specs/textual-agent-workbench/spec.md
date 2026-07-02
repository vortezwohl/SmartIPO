## ADDED Requirements

### Requirement: 系统必须提供基于 Textual 的本地 agent workbench
系统 MUST 提供一个基于 Textual 的本地 workbench，作为 SmartIPO 默认的本地 agent 入口，并 SHALL 让用户在单个会话界面中提交任务、观察过程并接收回复。

#### Scenario: 用户在本地 workbench 中提交任务
- **WHEN** 用户在 Textual workbench 输入一个任务并提交
- **THEN** 系统 MUST 启动对应的 agent 会话回合
- **AND** workbench MUST 在同一时间线中展示后续过程与回复

### Requirement: workbench 必须流式展示 assistant 输出
系统 MUST 以流式方式展示 assistant 面向用户的输出，而不是只在一轮结束后一次性显示完整文本。

#### Scenario: assistant 回复分块到达
- **WHEN** 主脑在一次会话回合中逐块产生文本输出
- **THEN** workbench MUST 按到达顺序追加这些文本块
- **AND** 用户 SHALL 在回合结束前看到中间输出

### Requirement: workbench 必须展示思考与工具调用过程
系统 MUST 在时间线中展示主脑思考占位、工具调用开始、工具调用完成和工具调用失败，并 MUST 展示相应耗时。

#### Scenario: 一次任务触发思考和工具调用
- **WHEN** 主脑开始判断下一步并随后调用一个或多个工具
- **THEN** workbench MUST 先显示思考占位和思考耗时
- **AND** 工具开始与结束 MUST 以独立过程项展示
- **AND** 每个过程项 MUST 显示对应耗时

#### Scenario: assistant 输出覆盖思考占位
- **WHEN** assistant 开始向用户输出最终回复
- **THEN** 已完成的思考占位 SHALL 被移除或覆盖
- **AND** 时间线中不得同时保留过时的“思考中”占位
