## 1. Runtime Tool Lifecycle Repair

- [x] 1.1 审核并调整 EasyHarness runtime 的 tool phase 跟踪结构，使其按 `tool_use_id` 跟踪多条活跃工具调用而不是只保留单个当前工具槽位
- [x] 1.2 修改工具终态事件聚合逻辑，确保 `completed`、`failed`、`cancelled` 都能按正确调用实例收口并清理活跃状态
- [x] 1.3 补充 runtime 层针对交错 started/completed、同名工具重复调用和取消收口的回归测试

## 2. TUI Timeline Binding Hardening

- [x] 2.1 调整 `src/tui/app.py` 的 tool 终态关联逻辑，保持 `tool_use_id` 精确匹配优先，并在失败时执行保守回绑
- [x] 2.2 确保终态回填后不会再残留持续计时的旧 `Running` 工具项，也不会额外生成重复终态行
- [x] 2.3 为 TUI 增加“首条 tool 残留”、“同名工具不串线”、“终态缺少首选键时兜底回绑”的回归测试

## 3. Verification

- [x] 3.1 运行与 tool 生命周期相关的测试集，确认首条 tool call 不再持续计时
- [x] 3.2 手工或集成验证一批连续 tool call 的时间线输出，确认每条调用只收口为一条最终活动行
