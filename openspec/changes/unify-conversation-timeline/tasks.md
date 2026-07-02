## 1. 核心时间线模型

- [x] 1.1 在 `src/core` 新增通用 timeline entry/state/reducer，负责把 `LoopEvent` 归约为跨 UI 复用的会话时间线状态
- [x] 1.2 扩展工具相关时间线语义，支持状态、耗时、结果概要、结果详情和折叠建议
- [x] 1.3 保持 thinking 只作为运行时事实事件存在，不把 `thinking . .. ...` 动画编码进事件流

## 2. TUI 适配

- [x] 2.1 让 `src/tui/app.py` 改为消费通用 timeline state，而不是继续在 UI 内直接解释 `LoopEvent`
- [x] 2.2 在 TUI 中把 thinking 文案改为 `thinking` 基础文本，并本地渲染 `. .. ...` 循环动画
- [x] 2.3 在 TUI 中把工具调用展示为聊天时间线条目，显示计时、概要与可折叠详情

## 3. 验证

- [x] 3.1 增加聚焦测试，覆盖 timeline reducer 对 thinking/tool/assistant 事件的归约结果
- [x] 3.2 更新 TUI smoke test，覆盖工具条目展示、长结果折叠和 thinking 动画基础行为
