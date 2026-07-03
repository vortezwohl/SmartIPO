## ADDED Requirements

### Requirement: TUI 输入框必须支持最小 slash 命令集
SmartIPO TUI MUST 在输入框层支持最小 slash 命令集，至少包括 `/stop`、`/new` 和 `/help`。这些命令 MUST 直接由 TUI 处理，而不是作为普通 prompt 进入 agent 队列。

#### Scenario: slash 命令不进入普通排队流程
- **WHEN** 用户提交以 `/` 开头且命中已支持命令的输入
- **THEN** 系统 MUST 在 TUI 内部处理该命令
- **AND** 系统 MUST NOT 把该输入作为普通消息加入 `_pending_turns`

#### Scenario: placeholder 暴露可发现命令
- **WHEN** 系统渲染输入框
- **THEN** placeholder MUST 同时提示常用命令与普通输入用途
- **AND** placeholder MUST 至少包含 `/stop`、`/new` 或 `/help` 中的命令提示

### Requirement: TUI 必须支持命令 Tab 自动补全
SmartIPO TUI MUST 支持对 slash 命令进行 Tab 自动补全，并复用 `vortezwohl.nlp.LevenshteinDistance` 对闭集命令候选做模糊排序。

#### Scenario: 近似命令可被补全
- **WHEN** 用户输入近似命令文本，例如 `/stp`，并触发 Tab 补全
- **THEN** 系统 MUST 把输入补全为最接近的受支持命令
- **AND** 补全排序 MUST 基于 `LevenshteinDistance` 的闭集匹配结果

#### Scenario: 非命令输入不触发命令补全
- **WHEN** 当前输入不以 `/` 开头
- **THEN** 系统 MUST NOT 把该输入当作 slash 命令候选进行补全

### Requirement: `/stop` 必须收口当前回复并保留已生成历史
SmartIPO TUI MUST 允许用户中断当前活跃回复。中断后，assistant 已经生成的半截文本 MUST 保留在 timeline 历史中；该轮次后续迟到事件 MUST NOT 污染当前界面状态。

#### Scenario: 中断后半截 assistant 回复保留
- **WHEN** assistant 正在流式输出，且用户执行 `/stop`
- **THEN** timeline 中已生成的 assistant 文本 MUST 保留
- **AND** 系统 MUST 把当前回复收口为已中断状态，而不是清空或覆盖已有文本

#### Scenario: 中断后旧轮次事件被忽略
- **WHEN** 用户已中断当前 turn，且旧 worker 仍迟到发送事件
- **THEN** 这些事件 MUST NOT 再更新当前活跃界面状态

### Requirement: `/new` 必须安全重置当前会话
SmartIPO TUI MUST 允许用户通过 `/new` 创建新会话。若当前存在活跃回复，系统 MUST 先安全收口当前状态，再清空本地 timeline、队列和会话状态。

#### Scenario: 空闲状态下创建新会话
- **WHEN** 当前没有活跃 turn，用户执行 `/new`
- **THEN** 系统 MUST 清空本地消息、队列和计数状态
- **AND** 系统 MUST 调用 agent 的 `reset()`（若可用）

#### Scenario: 运行中执行 `/new`
- **WHEN** 当前存在活跃 turn，用户执行 `/new`
- **THEN** 系统 MUST 保证旧 turn 后续事件不会污染新会话
- **AND** 新会话 MUST 以干净的 timeline 与队列状态开始
