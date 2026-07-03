## ADDED Requirements

### Requirement: TUI 对话区必须使用自然聊天视觉语言
SmartIPO TUI MUST 把主消息区渲染为聊天式对话记录，而不是以日志式前缀、方括号状态串或调试输出风格作为默认消息语言。

#### Scenario: 用户消息使用图标而不是文本前缀
- **WHEN** 系统在主消息区渲染一条用户消息
- **THEN** 该消息 MUST 使用类似 `👨‍💻` 的角色标识
- **AND** 系统 MUST NOT 以 `你:` 作为默认用户消息前缀

#### Scenario: 助手消息使用图标而不是 AI 文本前缀
- **WHEN** 系统在主消息区渲染一条助手回复
- **THEN** 该消息 MUST 使用类似 `🤖` 的角色标识
- **AND** 系统 MUST NOT 以 `AI:` 或 `EasyHarness:` 作为默认助手消息前缀

### Requirement: TUI 主题必须采用明亮浅绿色视觉方向
SmartIPO TUI MUST 使用明亮的浅绿色作为整体主题方向，并保证主要消息阅读文字使用白色。

#### Scenario: 主消息和输入区遵循浅绿色主题
- **WHEN** TUI 完成布局与主题渲染
- **THEN** 主消息区、输入区和相关面板 MUST 呈现统一的浅绿色视觉语言
- **AND** 主要正文文字 MUST 以白色显示

#### Scenario: 输入框使用新的 SmartIPO 文案
- **WHEN** TUI 渲染输入框
- **THEN** placeholder MUST 显示为 `SmartIPO 在线为你解答 ...`

