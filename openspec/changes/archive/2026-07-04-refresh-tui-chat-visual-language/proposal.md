## Why

当前 TUI 仍以“纯文本时间线 + 日志式状态标签”为主，排队消息直接混在对话记录里，视觉上更像调试输出而不是聊天工作台。既然 `queue-tui-turn-submissions` 已经把串行队列跑通，现在需要把界面体验同步收敛到更自然的聊天表达：对话归对话，排队归排队，整体风格也要从暗沉的工具面板提升到明亮、统一的 SmartIPO 视觉语言。

## What Changes

- 把排队中的待处理消息从 timeline 主消息区移出，放到输入框上方的独立排队托盘区域，并以居中泡泡形式展示。
- 重做 TUI 聊天消息视觉语言，弱化日志式 `[]`、`你:`、`AI:` 等符号，改为更自然的聊天呈现，例如 `👨‍💻 hi` 与 `🤖 hi im SmartIPO`。
- 调整整体主题为明亮的浅绿色调，主阅读文字使用白色，并统一输入区、消息区和排队区的视觉层次。
- 更新输入框 placeholder 为 `SmartIPO 在线为你解答 ...`，同步提升整体文案与工作台质感。

## Capabilities

### New Capabilities
- `tui-chat-visual-language`: 定义 SmartIPO TUI 的消息呈现、角色标识、主题色和输入区文案规则。
- `tui-pending-queue-tray`: 定义待处理消息在 timeline 外的独立排队托盘展示与顺序表达。

### Modified Capabilities
- None.

## Impact

- 受影响代码主要位于 `src/tui/app.py` 的 `compose()` 布局、CSS、时间线渲染和排队状态渲染逻辑。
- 需要调整 `test/test_tui_app.py`，验证排队消息不再出现在 timeline、队列托盘可见、消息文案改为图标样式。
- 不引入新依赖，继续使用 Textual 与 Rich 现有能力完成渲染。
