## 1. Thinking 历史消息分流

- [x] 1.1 调整 `src/tui/app.py` 中真实 thinking 历史升级点，把标题从 `Assistant > ` 改为 `Assistant (Thinking) > `。
- [x] 1.2 在 thinking 本地 metadata 中保留 waiting-only 与真实历史的边界，确保前缀切换只发生在收到非空 runtime thinking 文本之后。
- [x] 1.3 为真实 thinking 历史新增专属渲染分流，不再复用普通 assistant chat renderer。

## 2. 专属视觉样式

- [x] 2.1 在 `src/tui/app.py` 中为 thinking 历史新增专属前缀样式常量，使其绿色比正式 assistant 更暗。
- [x] 2.2 在 `src/tui/app.py` 中为 thinking 历史新增专属正文样式常量，使其正文比正式 assistant 更暗但保持可读。
- [x] 2.3 保持 waiting-only `Thinking ...` 占位与正式 assistant 回复的现有视觉行为不变，避免本次样式调整扩散到无关消息类型。

## 3. 测试与验证

- [x] 3.1 更新 `test/test_tui_app.py` 中真实 thinking 历史相关断言，使其匹配 `Assistant (Thinking) > ` 前缀。
- [x] 3.2 为真实 thinking 历史与最终 assistant 回复的并存场景补充测试，验证两者前缀和 chronology 都正确。
- [x] 3.3 为真实 thinking 历史 renderable 补充样式级断言，验证其前缀和正文颜色都比普通 assistant 更暗。
- [x] 3.4 运行聚焦 TUI 测试，确认 waiting-only、thinking history 和最终 assistant 回复三类路径均通过。
