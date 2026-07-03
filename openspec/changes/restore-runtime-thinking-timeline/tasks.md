## 1. Thinking 生命周期收敛

- [x] 1.1 在 `src/tui/app.py` 中区分本地 provisional waiting 与真实 runtime thinking 的 metadata 和状态流转。
- [x] 1.2 调整 `thinking` 事件处理逻辑：收到非空 runtime `thinking delta/completed` 后，将可见输出升级为持久历史，而不是继续清空或标记为可删除占位。
- [x] 1.3 调整 thinking 渲染路径，让真实 runtime thinking 内容通过 assistant-style 会话表面进入 timeline；没有真实 thinking 文本时，保留当前临时 `Thinking ...` 等待反馈。

## 2. 阶段顺序与 timeline 保留

- [x] 2.1 调整 tool 事件处理逻辑，确保同一轮中的 tool 活动追加在已有 thinking 历史之后，而不是覆盖或隐式移除 thinking 内容。
- [x] 2.2 调整 assistant 事件处理逻辑，确保最终回复作为 thinking/tool 之后的新阶段追加，而不是复用并覆盖前置真实历史。
- [x] 2.3 调整 timeline 可见项筛选与 turn 收口逻辑，只移除空 waiting 占位，不移除已收到真实 thinking 文本的历史项。

## 3. 回归验证

- [x] 3.1 更新 `test/test_tui_app.py` 中与 “assistant 开始后 thinking 必须消失” 相关的旧断言，使其符合新的 runtime thinking 可见性合同。
- [x] 3.2 为 `thinking -> tool -> assistant` 的完整 chronology 补充测试，验证真实 thinking 历史在 tool 和最终回复之后仍然可见。
- [x] 3.3 为 “只有 provisional waiting、没有真实 thinking 文本” 的回退路径补充测试，验证空占位仍可在后续阶段开始后消失。
- [x] 3.4 运行 TUI 相关测试，确认新 chronology 行为通过，且未引入与本次改动相关的回归。
