## ADDED Requirements

### Requirement: 运行中的 thinking 指示器必须显示动态省略号动画
系统 MUST 为所有运行中的 thinking 指示器显示动态变化的省略号动画，而不是固定不变的 `Thinking ...` 文本。

#### Scenario: waiting placeholder 显示动态省略号
- **WHEN** turn 当前显示运行中的 `Thinking` 前置占位符
- **THEN** 系统 MUST 在后续刷新周期中让其省略号帧发生变化

#### Scenario: 真实 thinking 运行态显示动态省略号
- **WHEN** runtime 已进入真实 `thinking started` 或 `thinking delta` 阶段且该 thinking 尚未收口为历史消息
- **THEN** 系统 MUST 让该运行中 thinking 指示器显示动态省略号动画

### Requirement: 已完成的 thinking 历史消息不得继续动画
系统 MUST 在 `thinking` 已收口为历史消息后停止动画，并把该消息作为稳定的历史内容展示。

#### Scenario: history thinking 作为静态历史消息保留
- **WHEN** 某条 thinking 已升级为 `Assistant (Thinking) > ...` 历史消息
- **THEN** 系统 MUST 不再对该历史消息继续播放省略号动画
