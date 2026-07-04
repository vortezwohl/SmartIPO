## 1. Waiting Feedback Coordination

- [x] 1.1 调整 `src/tui/app.py` 的 agent 事件应用收口逻辑，在每次事件处理后统一协调活跃 turn 的 waiting `Thinking ...` 占位
- [x] 1.2 复用并收紧现有 waiting placeholder 守卫条件，确保只在无真实运行态活动时回补，占位不会误留到已停止或已取消的 turn

## 2. Regression Coverage

- [x] 2.1 在 `test/test_tui_app.py` 增加 `thinking` 终态后、`assistant` 终态后以及 `system` 事件后的 waiting feedback 回补测试
- [x] 2.2 在 `test/test_tui_app.py` 增加“waiting placeholder 被后续真实 `thinking`、`tool`、`assistant` 或 `compress` 活动立即接管”的测试
- [x] 2.3 运行 `.\.venv\Scripts\python.exe -m unittest test.test_tui_app`，确认最小改动没有破坏现有时间线行为
