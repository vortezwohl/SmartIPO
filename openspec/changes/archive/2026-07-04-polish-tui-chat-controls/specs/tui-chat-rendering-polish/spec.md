## ADDED Requirements

### Requirement: TUI 对话前缀必须使用文本化角色标签并支持主题色强调
SmartIPO TUI MUST 在主消息 timeline 中把用户消息前缀渲染为 `User > `，把助手消息前缀渲染为 `Assistant > `。这两个前缀 MUST 使用浅绿色主题色强调，正文 MUST 保持白色或其他高可读正文颜色。

#### Scenario: 用户消息使用文本前缀
- **WHEN** 系统在 timeline 中渲染一条用户消息
- **THEN** 该消息 MUST 以 `User > ` 作为可见前缀
- **AND** 系统 MUST NOT 再以 emoji、`你:` 或其他日志式标签作为默认用户前缀

#### Scenario: 助手消息使用文本前缀
- **WHEN** 系统在 timeline 中渲染一条助手消息
- **THEN** 该消息 MUST 以 `Assistant > ` 作为可见前缀
- **AND** 该前缀 MUST 与用户前缀一样使用浅绿色主题色强调

### Requirement: 排队托盘必须压平为轻量文本列表
SmartIPO TUI MUST 把 queue tray 中的待处理消息渲染为轻量、扁平的列表式提示。系统 MUST NOT 再给每条排队消息单独渲染泡泡、面板或多层边框。

#### Scenario: 单条排队消息不再显示独立气泡
- **WHEN** queue tray 中只有一条待处理消息
- **THEN** 该消息 MUST 以扁平文本样式展示
- **AND** 系统 MUST NOT 为该消息单独渲染独立气泡边框

#### Scenario: 多条排队消息保持顺序且不显拥挤
- **WHEN** queue tray 中同时存在多条待处理消息
- **THEN** 系统 MUST 以轻量列表方式展示这些消息
- **AND** 用户 MUST 能从展示顺序辨认排队先后

### Requirement: timeline 必须保持原生滚动可用
SmartIPO TUI MUST 继续把主消息区构建在可滚动容器上，并允许用户滚动浏览历史消息，而不是把 timeline 固定成只可自动跟随到底部的只读区域。

#### Scenario: 用户可以滚动查看旧消息
- **WHEN** timeline 中的消息高度超过当前可视区域
- **THEN** 用户 MUST 能通过终端支持的滚动方式浏览更早的消息

#### Scenario: 新消息到来时保留自动跟随到底部策略
- **WHEN** 当前视口靠近底部且系统收到新的 agent 输出
- **THEN** timeline MUST 继续自动跟随到底部
- **AND** 该自动跟随行为 MUST NOT 破坏用户对历史消息的主动滚动能力
