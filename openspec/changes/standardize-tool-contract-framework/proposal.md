## Why

当前工具体系已经暴露出两个结构性问题：一是 tool 的描述、输入语义、结果语义、错误语义分散在具体实现里，缺少统一 contract，导致新 tool 很容易各写各的；二是 TUI 之类 UI 层开始携带默认工具策略与部分运行时装配责任，边界正在变模糊。

现在需要把 fileglide 上已经验证有效的做法上升为统一框架规范，让未来新增 tool、维护现有 tool、接入新 UI 时都有一致依据，而不是继续依赖 prompt、局部约定和人工记忆。

## What Changes

- 建立统一的 tool definition contract，把 tool identity、structured documentation、input schema、policies、handler contract 纳入同一套规范。
- 建立统一的 tool result and error contract，明确哪些字段面向模型、哪些字段面向 timeline/UI、哪些字段保留原始诊断。
- 建立可复用的 tool policy 和 formatter 机制，把路径规范化、只读探索策略、结果渲染、错误映射等从具体 tool 中抽离为公共能力。
- 建立 tool catalog validation 机制，校验 description、schema、result fields、error codes 与 English-only 规则的一致性。
- **BREAKING** 调整 tool framework 的默认定义方式，后续新 tool 不再直接手写自由文本 description 和临时 metadata 语义，而是通过统一 contract 生成 provider-facing description 与 runtime-facing result payload。
- **BREAKING** 收紧 UI 与底层框架的责任边界：TUI、WebUI 等界面层只负责呈现、交互和本地化文案，不负责解释 tool protocol，也不负责定义底层 contract。
- 把现有 fileglide tool 迁移为首个标准化实现，并让其他 tool（如 Seedream）进入同一框架以消除“特例工具”。

## Capabilities

### New Capabilities
- `tool-definition-contract`: 规范 tool 的结构化定义方式，包括文档结构、schema 对齐规则、English-only contract 输出与 provider-facing description 生成。
- `tool-execution-contract`: 规范 tool 的统一执行语义，包括结果正文、结果预览、错误分类、错误恢复提示、runtime 序列化与通用 policy/formatter 接入点。
- `ui-runtime-boundary`: 规范 TUI、WebUI 等 UI 层与 core/tool framework/composition 层之间的责任边界，避免 UI 越界承担 tool protocol 和 runtime contract 责任。

### Modified Capabilities

## Impact

- Affected code:
  - `src/tool/contracts.py`
  - `src/tool/registry.py`
  - `src/tool/fileglide_tools.py`
  - `src/tool/seedream_image.py`
  - `src/core/strands_runtime.py`
  - `src/core/timeline.py`
  - `src/tui/app.py`
  - 预计新增 `src/tool/framework/` 或同级公共 contract/policy 模块
- APIs:
  - `ToolSpec`、`ToolResult`、tool error payload、provider-facing description 生成路径会调整
  - 新 tool 的注册与定义方式会标准化
- Systems:
  - Strands runtime tool adapter
  - fileglide wrapper
  - TUI workbench
  - future WebUI / other UI surfaces
