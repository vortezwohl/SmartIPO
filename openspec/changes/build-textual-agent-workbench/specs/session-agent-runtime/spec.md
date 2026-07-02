## ADDED Requirements

### Requirement: 系统必须提供会话型主脑运行时
系统 MUST 提供一个会话型主脑运行时，使同一会话中的主脑能够保留消息历史并在一次任务中连续调用多个工具，直到任务自然结束，而不是只调用一次工具就提前停止。

#### Scenario: 一个任务需要多个工具步骤
- **WHEN** 用户提交的任务需要主脑先读取信息再执行修改或其他后续动作
- **THEN** 系统 MUST 允许主脑在同一任务回合中连续调用多个工具
- **AND** 系统 MUST 只在主脑自然结束该回合时返回最终用户回复

### Requirement: 系统必须完整暴露 fileglide 工具集给本地会话
系统 MUST 将 fileglide Python facade 对应的完整本地文件系统工具集接入默认工具注册表，并在本地 workbench 会话中暴露这些工具。

#### Scenario: 本地 agent 处理文件系统任务
- **WHEN** 用户提交涉及读取、写入、搜索、移动或删除文件系统对象的任务
- **THEN** 主脑 MUST 能调用 fileglide 相关工具完成这些操作
- **AND** 系统 MUST 不要求用户切换到外部 shell 才能完成常见文件 I/O

### Requirement: 系统必须把主脑与工具过程桥接为统一事件流
系统 MUST 把主脑思考、工具调用和 assistant 流式输出桥接为统一事件流，供 Textual workbench 消费。

#### Scenario: 主脑回合运行时产生过程事件
- **WHEN** 主脑开始思考、调用工具、接收工具结果并输出最终回复
- **THEN** 系统 MUST 产生对应的进度事件和输出事件
- **AND** 这些事件 MUST 能被 workbench 按顺序消费和渲染

### Requirement: 工具执行失败必须保持可见并向上暴露
系统 MUST 在工具执行失败时保留失败事件与耗时信息，并 MUST 让异常继续向上暴露，而不是把失败伪装为成功回复。

#### Scenario: fileglide 或其他工具执行失败
- **WHEN** 一个已暴露工具在会话回合中抛出执行异常
- **THEN** 系统 MUST 产生对应的工具失败事件
- **AND** workbench MUST 能看到该失败
- **AND** 调用链 MUST 不得把该失败伪装成已完成任务
