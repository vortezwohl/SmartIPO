## 1. Independent Runtime Display for Tool Activities

- [x] 1.1 为 TUI 本地活动项引入独立的单调计时元数据，并只在运行中显示阶段使用它刷新 tool 耗时
- [x] 1.2 调整 tool 活动的 started 与 terminal 路径，确保终态到来后停止本地刷新并冻结为权威最终耗时
- [x] 1.3 为并发或重叠 tool 活动补充“运行中独立计时、终态权威冻结”的回归测试

## 2. Post-Compress Feedback Continuity

- [x] 2.1 提炼“活跃 turn 反馈回补”判断逻辑，用于识别 compression 终态后的可见空窗
- [x] 2.2 在 compression 终态后恢复本地 `Thinking ...` 占位，并确保真实后续事件到来时立即让位
- [x] 2.3 为 compression 后占位恢复与真实事件接管增加回归测试

## 3. Verification

- [x] 3.1 运行 TUI 相关测试集，验证独立计时显示与 compression 后反馈连续性
- [x] 3.2 手工或集成验证多 tool 活动与 compression 后续响应场景，确认用户可见时间线连续且可信
