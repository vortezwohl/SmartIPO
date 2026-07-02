## Why

`build-textual-agent-workbench` 已经把真实使用路径收敛到会话型 workbench，但当前运行时公开面仍然同时保留 `AgentLoop.run_once(...)` 和 `AgentSessionLoop.run_turn(...)`。这让同一套主脑语义出现了两套入口，增加理解和维护成本，而且 `run_once` 并不服务当前产品主路径。

现在收敛是合适的，因为 workbench、事件流和 fileglide 工具面都已经稳定，继续保留单轮 API 只会把“临时过渡层”固化成长期表面积。

## What Changes

- **BREAKING** 删除 `AgentLoop.run_once(...)` 这一套单轮公开 API。
- **BREAKING** 把当前 `AgentSessionLoop` 收敛为唯一公开主脑控制器，并统一命名为 `Agent`。
- 收敛 `src/core/` 对外导出，使 workbench、测试和后续调用方只依赖单一会话语义。
- 清理只为双接口并存而存在的兼容层、测试和文档表述。

## Capabilities

### New Capabilities
- `unified-agent-api`: 定义 SmartIPO 公开主脑 API 必须只保留单一会话型 `Agent`，不再暴露单轮 `run_once` 风格入口。

### Modified Capabilities
- None.

## Impact

- 受影响代码主要位于 `src/core/`、`src/tui/` 与 `test/`。
- 这是一次明确的内部 API 破坏性收敛，但当前不考虑后向兼容。
- 不新增依赖、不改变模型配置、不改变 fileglide 工具能力和 Textual workbench 的用户可见行为。
