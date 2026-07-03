## 1. Header and fixed UI language

- [x] 1.1 调整 `src/tui/app.py` 的应用标题与 Header 样式，使顶部 Header 显示 `SmartIPO` 且使用更深的绿色背景
- [x] 1.2 将 `src/tui/app.py` 中状态摘要、queue tray 标题、输入框 placeholder 与本地 slash 命令固定反馈统一改为英文 UI 文案
- [x] 1.3 复查 `src/tui/app.py` 中所有本地生成的 timeline 固定标签，确保 UI 层固定元素不再输出中文

## 2. Thinking and tool activity rendering

- [x] 2.1 调整 `src/tui/app.py` 的 thinking 渲染逻辑，使等待态显示为 `duration · Thinking ...`
- [x] 2.2 调整 thinking 可见性规则，使 provisional thinking 在 assistant 首次真实输出后从可见 timeline 中消失
- [x] 2.3 重构 `src/tui/app.py` 的 tool activity 主行渲染，使其统一为 `duration · { Tool <name> · <status> }`
- [x] 2.4 将 tool follow-up lines 的固定标签统一为英文，例如 `Call`、`Summary`、`Result`、`Error`
- [x] 2.5 为计时、聊天前缀、thinking 与 tool 主行补充分层样式，确保计时弱于正文、工具块与聊天前缀可区分

## 3. Verification and regression coverage

- [x] 3.1 更新 `test/test_tui_app.py` 中与 thinking 文案和生命周期相关的断言，验证 assistant 开始输出后 thinking 不再残留
- [x] 3.2 更新 `test/test_tui_app.py` 中与 tool activity 主行、错误标签、结果标签相关的断言，验证新的 `{ Tool ... }` 结构
- [x] 3.3 更新 `test/test_tui_app.py` 中与 Header 标题、placeholder、queue tray、本地帮助和系统提示相关的英文 UI 文案断言
- [x] 3.4 运行聚焦 TUI 测试，确认英文 UI、thinking 消失逻辑、tool 主行格式和既有聊天/排队行为没有回归
