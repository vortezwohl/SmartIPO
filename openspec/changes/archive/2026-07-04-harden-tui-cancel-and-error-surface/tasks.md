## 1. Runtime-backed cancellation

- [x] 1.1 调整 `src/tui/app.py` 的 `/stop` 处理流程，让活跃 turn 先请求 `easyharness.Agent.cancel()`，再等待真实终态事件完成收口。
- [x] 1.2 为 active turn 增加 stopping / cancelled 收口语义，确保 `thinking`、`tool`、`assistant` 与队列推进都基于真实终态而不是本地抢先结案。
- [x] 1.3 保持并验证 turn_id 迟到事件隔离，确保被停止的旧 turn 后续事件不会污染下一条排队消息。

## 2. Timeline stop and failure surface

- [x] 2.1 调整 timeline 渲染与状态标签，显式支持 `cancelled`，并为用户主动停止追加低强调英文留痕事件。
- [x] 2.2 调整工具失败与系统失败的默认展示，只输出用户级摘要，不在主 timeline 中渲染 traceback 等原始堆栈。
- [x] 2.3 保留完整失败诊断在内部 metadata 或等价存储中，避免为界面收敛而丢失调试与测试可见性。

## 3. Verification

- [x] 3.1 更新 `test/test_tui_app.py`，覆盖 `/stop` 真实取消、partial assistant 保留、cancelled tool 收口和停止留痕事件。
- [x] 3.2 更新 `test/test_tui_app.py`，覆盖空闲 `/stop`、旧 turn 迟到事件忽略，以及 queue 在取消收口后继续推进。
- [x] 3.3 更新 `test/test_tui_app.py`，覆盖 tool/runtime failure 仅显示摘要、默认不展示 traceback、原始诊断仍可在内部状态中访问。
