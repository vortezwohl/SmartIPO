## 1. 聊天渲染收口

- [x] 1.1 调整 `src/tui/app.py` 的 timeline 渲染路径，支持 `User > ` 与 `Assistant > ` 的浅绿色前缀样式，同时保留稳定的纯文本断言接口
- [x] 1.2 调整 `src/tui/app.py` 的 queue tray 渲染，移除单条排队消息的独立泡泡/边框，改为轻量扁平列表式展示
- [x] 1.3 更新 `src/tui/app.py` 的输入框 placeholder 与相关文案，使普通输入和 `/stop`、`/new`、`/help` 的发现路径清晰

## 2. 命令与中断控制

- [x] 2.1 在 `src/tui/app.py` 中增加 slash 命令分发，确保 `/stop`、`/new`、`/help` 不进入普通消息排队流程
- [x] 2.2 在 `src/tui/app.py` 中复用 Textual worker 取消能力实现当前回复中断，并保证半截 assistant 文本保留在历史中、旧 turn 迟到事件被忽略
- [x] 2.3 在 `src/tui/app.py` 中增加 Tab 命令补全，并使用 `vortezwohl.nlp.LevenshteinDistance` 对闭集命令候选做模糊匹配
- [x] 2.4 复核 timeline 滚动链路，确保主消息区继续基于 `VerticalScroll` 提供历史滚动能力，必要时补最小事件处理或聚焦调整

## 3. 验证

- [x] 3.1 更新 `test/test_tui_app.py`，验证新的文本前缀、queue tray 压平展示和 placeholder 命令提示
- [x] 3.2 更新 `test/test_tui_app.py`，验证 slash 命令分发、Tab 自动补全、中断后半截回复保留以及 `/new` 后旧事件隔离
- [x] 3.3 运行相关 TUI 测试，并补充滚动行为的手测结论或最小自动化验证
