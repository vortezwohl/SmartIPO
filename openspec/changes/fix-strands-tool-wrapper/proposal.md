## Why

当前项目把业务工具通过 `tool(_call, inputSchema=...)` 包装进 Strands，但 `_call(**kwargs)` 的函数签名会让 Strands 先基于 `kwargs` 构造内部校验模型，导致 fileglide 等 schema-driven 工具在真正进入本地执行前就因参数校验失败。结果是工具明明被尝试调用，用户却只能看到 assistant 的转述，看不到真实工具 timeline 和失败原因。

现在需要修正工具桥接层，让 Strands 直接消费项目内 `ToolSpec.input_schema` 与 `tool_use["input"]`，并补齐 provider 侧工具尝试失败的可观测性。

## What Changes

- **BREAKING** 替换当前基于 `tool(_call, inputSchema=...)` 的通用工具包装方式，改为使用更贴合 schema-driven 工具模型的低层桥接实现。
- **BREAKING** 调整 Strands runtime 的工具执行入口，确保 tool input 直接来自 provider 的 `tool_use["input"]`，不再被 `_call(**kwargs)` 的签名误导。
- 为 runtime 增加 provider-side tool attempt / validation failure 事件，让工具在真正进入本地 handler 前失败时也能被上层 UI 观察到。
- 收缩 TUI 默认暴露工具集为高频只读最小集合，减少模型选错工具和填错参数的概率。
- 补充针对 fileglide 工具真实可调用、provider 侧失败可见、TUI timeline 可见性的测试。

## Capabilities

### New Capabilities
- `strands-tool-execution-bridge`: 规范项目工具如何以 schema-driven 方式接入 Strands，并保证 provider 工具输入能真实进入本地执行层。
- `tool-attempt-observability`: 规范工具在 provider 侧尝试、校验失败和本地执行失败时，统一暴露为可被 UI 消费的活动事件。

### Modified Capabilities
- 无

## Impact

- Affected code:
  - `src/core/strands_runtime.py`
  - `src/core/events.py`
  - `src/core/timeline.py`
  - `src/tui/app.py`
  - `src/tool/registry.py`
  - `test/test_strands_runtime.py`
  - `test/test_timeline.py`
  - `test/test_tui_app.py`
- APIs:
  - Strands runtime 内部工具桥接实现会变化
  - `LoopEvent` 的工具活动事件种类和语义会扩展
- Systems:
  - Textual workbench
  - fileglide 默认工具接入链路
  - 后续 WebUI 可复用的工具活动 timeline
