## ADDED Requirements

### Requirement: Strands bridge SHALL execute project tools from provider tool input directly
项目内工具接入 Strands 时，runtime MUST 直接使用 provider 传入的 `tool_use["input"]` 调用项目内 `ToolSpec.handler`，不得再依赖一个与项目 schema 无关的 Python 函数签名推导输入模型。

#### Scenario: Fileglide tool executes with provider-supplied input
- **WHEN** provider 发起一次 `path.list` 或 `text.read` 工具调用并提供合法 input
- **THEN** runtime MUST 将该 input 直接映射到对应 `ToolSpec.handler`
- **THEN** 工具调用 MUST 进入本地 handler，而不是在 `_call(**kwargs)` 这类通用签名校验阶段失败

#### Scenario: Tool schema remains the single source of truth
- **WHEN** runtime 将项目内工具暴露给 Strands
- **THEN** provider 可见的工具 schema MUST 与项目内 `ToolSpec.input_schema` 一致
- **THEN** runtime MUST NOT 再生成一套会改变字段要求的隐式输入模型

### Requirement: Tool bridge SHALL format project tool results into Strands-compatible results
工具桥接层 MUST 把项目内 `ToolResult` 转成 Strands 可接受的 tool result 结构，同时保留项目内工具摘要与详情语义。

#### Scenario: Successful tool result is returned to the model
- **WHEN** 本地工具 handler 成功返回 `ToolResult`
- **THEN** bridge MUST 返回带有 `toolUseId`、`status=success` 和结果内容的 Strands tool result
- **THEN** 上层模型 MUST 能继续基于该结果完成当前回合

#### Scenario: Local tool failure is returned as tool error result
- **WHEN** 本地工具 handler 抛出异常
- **THEN** bridge MUST 返回带有 `toolUseId`、`status=error` 和原始错误文本的 Strands tool result
- **THEN** 上层 MUST 能区分这是一次真实进入本地执行后的工具失败
