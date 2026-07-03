## Why

当前 TUI 的基础队列和终端原生底板已经就位，但聊天体验还停留在“能用，不顺手”的阶段：排队消息仍然过于突兀，消息前缀缺少稳定的角色语义，运行中的 agent 也没有面向用户的中断入口。继续在这个状态上叠加功能，只会把工作台越做越像调试面板。

这次修改要把交互层补齐到一个可长期使用的最小闭环：消息更自然，命令可发现，回复可中断，滚动行为符合终端用户直觉。

## What Changes

- 压平排队托盘的视觉表达，去掉单条排队消息的独立泡泡/边框，改为更轻的居中列表式提示。
- 把聊天前缀统一为 `User > ` 与 `Assistant > `，并使用浅绿色主题色强调前缀，正文保持白色可读。
- 为输入框增加 `/stop`、`/new`、`/help` 等最小命令集；命令要写入 placeholder，便于发现。
- 支持命令输入的 Tab 自动补全，并使用 `vortezwohl.nlp.LevenshteinDistance` 对闭集命令做模糊匹配排序。
- 增加“中断当前回复”的 TUI 闭环：中断后当前 assistant 已生成的半截文本必须保留在历史中，旧轮次后续事件不得污染新状态。
- 明确 timeline 的滚轮滚动行为，确保主消息区能按终端用户预期滚动浏览历史。

## Capabilities

### New Capabilities
- `tui-chat-rendering-polish`: 定义排队托盘压平、角色前缀文本化、前缀主题色强调与 timeline 可滚动的聊天渲染规则。
- `tui-chat-command-controls`: 定义 TUI slash 命令、命令提示、Tab 补全与中断当前回复的控制行为。

### Modified Capabilities
- None.

## Impact

- 受影响代码主要位于 `src/tui/app.py` 的输入提交流程、worker 生命周期管理、timeline/queue tray 渲染和 CSS。
- 需要调整 `test/test_tui_app.py`，验证命令分发、Tab 补全、中断后半截回复保留、queue tray 压平和 timeline 滚动相关行为。
- 不修改 `src/agent.py` 的对外协议；中断优先复用 Textual worker 取消与现有旧轮次事件丢弃逻辑。
- 新增依赖为零，只复用项目已安装的 `vortezwohl`、Textual 和 Rich。
