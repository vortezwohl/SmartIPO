## 1. 替换 Strands 工具桥接实现

- [x] 1.1 重写 `src/core/strands_runtime.py` 的工具包装逻辑，移除 `tool(_call, inputSchema=...)` 路径，改为直接桥接 `tool_use["input"]`
- [x] 1.2 保持现有 `ToolSpec` / `ToolContext` / `ToolResult` 契约不变，并在新桥接层内完成 Strands tool result 格式化
- [x] 1.3 更新 `test/test_strands_runtime.py`，验证 `path.list` / `text.read` 这类 schema-driven 工具能真实进入本地 handler

## 2. 补齐工具尝试与失败可观测性

- [x] 2.1 扩展 `src/core/events.py` 与 `src/core/strands_runtime.py`，增加 provider-side tool attempt / validation failure 事件
- [x] 2.2 调整 `src/core/timeline.py`，让 timeline 能区分 provider-side attempt failure 与本地执行 failure
- [x] 2.3 更新 `test/test_timeline.py`，覆盖 attempt、validation failure、本地执行 failure 的归约语义

## 3. 修正 TUI 默认工具暴露与活动展示

- [x] 3.1 调整 `src/tui/app.py` / 默认 agent 装配逻辑，仅暴露最小高频只读工具集合
- [x] 3.2 调整 TUI 工具活动渲染，确保 provider-side tool attempt 和 failure 也会出现在 timeline 中
- [x] 3.3 更新 `test/test_tui_app.py`，覆盖默认只读工具集和 attempt/failure 可见性

## 4. 完成验证

- [x] 4.1 运行最小对照验证，确认最小无参工具、单参数工具和默认 fileglide 只读工具都可调用
- [x] 4.2 运行 `.venv\\Scripts\\python.exe -m unittest discover -s test -p "test_*.py"`
- [x] 4.3 运行 `.venv\\Scripts\\python.exe -m compileall src test`
