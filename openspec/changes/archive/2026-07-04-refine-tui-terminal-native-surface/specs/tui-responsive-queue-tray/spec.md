## ADDED Requirements

### Requirement: queue tray 仅在有待处理消息时显示
SmartIPO TUI MUST 只在待处理队列非空时显示 queue tray。若当前没有排队消息，该区域 MUST 完全隐藏，而不是显示空态占位文案或保留固定空白高度。

#### Scenario: 空队列时隐藏托盘
- **WHEN** `_pending_turns` 为空
- **THEN** queue tray MUST 不显示
- **AND** timeline 与输入区之间 MUST NOT 保留仅用于空托盘的固定占位空间

#### Scenario: 有排队消息时显示托盘
- **WHEN** 当前存在至少一条待处理消息
- **THEN** queue tray MUST 显示这些排队消息
- **AND** 这些消息 MUST 继续保持不进入 timeline 主消息区

### Requirement: queue tray 与整体布局必须按内容收缩
SmartIPO TUI MUST 避免为 queue tray 和相关辅助区域设置与内容无关的大块固定高度或固定空白，以保证不同终端窗口下的响应式可用性。

#### Scenario: 窄窗口下托盘不应挤占主视区
- **WHEN** 用户在较窄或较矮的终端窗口中使用 TUI
- **THEN** queue tray MUST 按内容高度收缩
- **AND** timeline MUST 保持尽可能大的可用显示区域

#### Scenario: 空托盘不显示空态提示
- **WHEN** 当前没有排队消息
- **THEN** 系统 MUST NOT 在 queue tray 位置显示“暂无排队消息”之类的空态文本

