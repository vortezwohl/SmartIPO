## Why

`SmartIPO` 最近两轮已经把运行时语义收敛到会话型 `Agent`，但目录结构还停留在过渡状态：`src/base/` 与 `src/core/` 职责交叉，`agent_loop.py` 的名字也已经不再匹配真实语义。继续保留这些过渡层，只会把临时布局固化成长期维护成本。

现在推进这次收敛是合适的，因为公开 API 已经稳定为单一会话型 `Agent`，可以顺势把目录边界、模块命名和冗余兼容层一次收干净，而且用户已经明确本轮不考虑后向兼容。

## What Changes

- **BREAKING** 把 `src/base/` 的运行时相关内容整合进 `src/core/`，删除 `base` 目录层级。
- **BREAKING** 把当前 `src/core/agent_loop.py` 收敛为单个 `src/core/agent.py` 模块，统一承载公开 `Agent` 语义。
- 保留 `llm.py` 抽象和 `text2text.py` 单实现，但移动到 `src/core/`，不再通过 `src/base/` 暴露。
- 清理项目内所有已无必要的后向兼容冗余，包括死代码、重复装配层、旧导入路径和旧命名。
- 保持当前 workbench、模型配置、fileglide 工具能力和会话行为不变，只收敛布局和语义。

## Capabilities

### New Capabilities
- `core-runtime-layout`: 定义 SmartIPO 运行时核心目录必须收敛到 `src/core/`，并使用单一 `agent.py` 模块承载公开 `Agent` 语义。

### Modified Capabilities
- None.

## Impact

- 受影响代码主要位于 `src/base/`、`src/core/`、`src/service/`、`src/tui/` 与 `test/`。
- 这是一次明确的内部布局与导入路径破坏性收敛，不提供后向兼容别名。
- 不新增依赖，不改变 `llm.py` / `text2text.py` 的保留决定，不改变当前用户可见运行行为。
