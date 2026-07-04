## 1. Placeholder Lifecycle

- [x] 1.1 调整 `src/tui/app.py` 中 waiting placeholder 与真实 `thinking/tool/assistant/compress` 阶段的切换逻辑，确保真实动作开始时覆盖当前 `Thinking ...` 占位符
- [x] 1.2 调整 `src/tui/app.py` 中真实动作终态后的回补逻辑，确保只要 turn 尚未结束且当前没有其他真实运行中的阶段，就立即重新显示 `Thinking ...`
- [x] 1.3 调整 turn 收尾逻辑，确保 turn 完成、失败或取消后移除最后的 `Thinking ...` 占位符

## 2. Thinking Animation

- [x] 2.1 在 `src/tui/app.py` 中为运行中的 thinking 指示器实现基于现有刷新节拍的 `.` / `..` / `...` 动画帧
- [x] 2.2 确保动画只作用于 waiting placeholder 和运行中的真实 thinking，不影响 `Assistant (Thinking) > ...` 历史消息

## 3. Regression Coverage

- [x] 3.1 在 `test/test_tui_app.py` 增加“真实动作开始时覆盖 placeholder、真实动作结束后回补 placeholder”的时间线回归测试
- [x] 3.2 在 `test/test_tui_app.py` 增加 running thinking 动画帧变化测试，并验证 history thinking 不会继续动画
- [x] 3.3 运行 `.\.venv\Scripts\python.exe -m unittest test.test_tui_app`，确认新的生命周期与动画逻辑没有破坏现有时间线行为
