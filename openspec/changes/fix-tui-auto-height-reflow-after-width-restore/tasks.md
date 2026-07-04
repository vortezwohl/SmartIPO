## 1. 重排生命周期修正

- [x] 1.1 调整 `src/tui/app.py` 中统一 repaint 路径的顺序，让 `status-banner`、timeline 与 `queue-tray` 的最终内容更新发生在高度收敛所需的 layout pass 之前
- [x] 1.2 为 `#body` 或等价父容器补充统一的二次布局重测收口，确保横向宽度恢复后 auto 高度区域重新按最终内容测量
- [x] 1.3 检查 `scroll_end`、follow-scroll 与输入框 focus 的调度时机，确保它们发生在最终布局稳定之后而不破坏高度回收

## 2. 关键区域回归验证

- [x] 2.1 更新 `test/test_tui_app.py` 的横向 resize 回归用例，为 `status-banner`、`queue-tray` 等关键区域增加“缩窄后变高、恢复后回到初始高度”的断言
- [x] 2.2 保留并调整稳定截图对比逻辑，确认恢复宽度后的整体界面在垂直间距和边框高度上与初始稳定界面一致

## 3. 聚焦测试与收尾

- [x] 3.1 运行聚焦的 TUI 单元测试，验证宽度恢复、高度回收与稳定截图回归全部通过
- [x] 3.2 根据测试结果更新本次 change 的任务勾选状态，确保方案进入 apply-ready 状态
