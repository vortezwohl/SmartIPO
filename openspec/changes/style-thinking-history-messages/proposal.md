## Why

当前 TUI 已经能把真实 runtime thinking 文本保留为会话历史，但它在视觉上仍按普通 assistant 消息渲染，导致用户很难快速区分“模型思考过程”和“正式回复”。现在修正这件事是合适的，因为 thinking 历史能力刚刚恢复，可见性问题已经解决，下一步最自然的收敛就是补上稳定、低歧义的视觉语义。

## What Changes

- 为真实 thinking 历史消息引入专属前缀 `Assistant (Thinking) > `，不再复用正式 assistant 的 `Assistant > `。
- 为真实 thinking 历史消息引入专属降权渲染：前缀绿色比正式 assistant 更暗，正文白色也更暗，形成“可读但非最终结论”的视觉层级。
- 保留当前 waiting-only `Thinking ...` 占位行为，不把本地等待态与真实 runtime thinking 历史混为一谈。
- 保留当前 chronology 合同：thinking 历史仍应先于 tool 和最终 assistant 回复出现，视觉调整不得破坏已有时间线顺序。
- 更新 TUI 相关测试，使真实 thinking 历史断言从普通 assistant 前缀切换到 thinking 专属前缀，并补充对专属渲染分流的覆盖。

## Capabilities

### New Capabilities
- `tui-thinking-history-visual-treatment`: 定义真实 runtime thinking 历史消息在 TUI 中的专属前缀、颜色层级和与正式 assistant 回复的视觉区分。

### Modified Capabilities
- None.

## Impact

- 主要影响 `src/tui/app.py` 中 thinking 历史消息的 metadata、前缀赋值和 renderable 分流逻辑。
- 需要同步更新 `test/test_tui_app.py` 中与真实 thinking 历史前缀和 chronology 相关的断言。
- 不涉及 runtime 协议、tool 事件结构、agent 输出结构或新的外部依赖。
