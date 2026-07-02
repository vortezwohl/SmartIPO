## ADDED Requirements

### Requirement: 系统必须提供跨 UI 复用的会话时间线状态模型
系统 MUST 在核心层提供一套独立于具体 UI 框架的会话时间线状态模型，用于把运行时事件归约为可被 TUI 与未来 WebUI 共同消费的 timeline entries。

#### Scenario: UI 读取一轮会话时间线
- **WHEN** UI 需要展示用户消息、思考、工具调用和 assistant 输出
- **THEN** 系统 MUST 通过统一的 timeline state 提供这些条目
- **AND** UI MUST NOT 直接各自解释底层 `LoopEvent` 负载来重建业务语义

### Requirement: 系统必须把工具调用表示为标准时间线条目
系统 MUST 把工具调用表示为一等时间线项目，并至少包含运行状态、耗时、结果概要和结果详情分层。

#### Scenario: 工具调用成功并返回较长结果
- **WHEN** 某个工具调用完成且结果内容较长
- **THEN** 系统 MUST 提供结果概要与结果详情两个层次
- **AND** 系统 MUST 提供该条目是否可折叠以及默认折叠建议

#### Scenario: 工具调用失败
- **WHEN** 某个工具调用失败
- **THEN** 系统 MUST 把失败状态和失败信息写入对应工具时间线条目
- **AND** UI MUST 能继续使用统一条目模型展示失败结果
