## Context

经过 `build-textual-agent-workbench` 和 `unify-agent-api` 两轮收敛后，SmartIPO 的运行时主路径已经比较明确：
- `src/core/agent_loop.py` 实际上已经只承载公开 `Agent`；
- `src/core/strands_runtime.py` 和 `src/core/events.py` 负责运行时桥接；
- `src/service/model_hub.py` 负责把集中配置解析成主脑模型；
- `src/base/llm.py` 与 `src/base/text2text.py` 仍然是运行时核心依赖；
- `src/base/agent.py` 则已经成为与 `model_hub.py` 职责重叠的过渡层。

当前布局的问题不在功能，而在语义失真：
- `base` 与 `core` 的边界已经失真，`base` 中的大部分内容其实就是运行时核心能力；
- `agent_loop.py` 这个文件名仍然带着过渡期痕迹，不再表达真实职责；
- `src/base/agent.py` 和 `src/service/model_hub.py` 都在做主脑模型装配，属于重复表面积；
- 当前项目里已经不需要任何后向兼容别名或旧导入壳，但目录和模块名还没有完全收干净。

用户这轮要求非常明确：
- 把 `base` 和 `core` 整合成 `core`；
- 把 `agent_loop.py` 和 agent 语义收敛为单个 `agent.py`；
- 清理掉当前项目中所有后向兼容冗余；
- `llm.py` 和 `text2text.py` 必须保留；
- 单实现抽象可以保留，不需要为了“更纯”而删掉 `LLM -> Text2Text` 这一层。

## Goals / Non-Goals

**Goals:**
- 删除 `src/base/` 目录，把其中仍有价值的运行时能力迁移到 `src/core/`。
- 把当前 `src/core/agent_loop.py` 收敛并重命名为 `src/core/agent.py`。
- 保留 `llm.py` 抽象和 `text2text.py` 单实现，但移动到 `src/core/`。
- 删除 `src/base/agent.py` 以及所有旧导入路径、旧命名和死兼容层。
- 保持 workbench、模型配置和运行时行为不变，只收敛布局与语义。

**Non-Goals:**
- 不改变 `src/service/model_hub.py` 的职责边界。
- 不改变 `src/model_config.py` 的配置模型。
- 不改变 fileglide、Seedream、Textual UI 或事件流行为。
- 不引入新的 factory、facade、compat shim 或多实现插件层。

## Decisions

### 1. `src/base/` 完整并入 `src/core/`

决策：删除整个 `src/base/` 包，把 `llm.py` 与 `text2text.py` 平移到 `src/core/`。

理由：这两者已经是运行时核心依赖，不再属于一个独立“基础层”。继续保留 `base` 只会制造一层没有真实边界的目录。

备选方案：保留 `base`，只移动 `agent.py`。拒绝，因为这会继续保留一套失真的层级结构。

### 2. 公开 Agent 统一落到 `src/core/agent.py`

决策：把当前 `src/core/agent_loop.py` 重命名为 `src/core/agent.py`，并让该文件只承载公开 `Agent` 与相关会话数据结构。

理由：当前真实公开语义已经是会话型 `Agent`，文件名必须和职责一致。

备选方案：继续使用 `agent_loop.py`。拒绝，因为它表达的是旧实现阶段，而不是当前抽象。

### 3. `src/base/agent.py` 直接删除，不迁移

决策：删除 `src/base/agent.py`，不把其中的 `AgentModel` / `build_litellm_model(...)` 原样搬运到 `core`。

理由：它与 `src/service/model_hub.py` 已经职责重叠，而且当前主路径不再依赖它。迁移它只会把死层带到新目录里。

备选方案：把 `src/base/agent.py` 合并进 `src/core/agent.py`。拒绝，因为那会把“会话控制器”和“模型配置装配”揉成一个文件。

### 4. `service/model_hub.py` 本轮保留

决策：`src/service/model_hub.py` 继续保留在 `service/`，负责“配置 -> 模型客户端”的装配，不并入 `core/agent.py`。

理由：这是当前唯一清晰的配置装配入口。把它继续留在 `service/`，能避免本轮变成职责大重切。

备选方案：把 `model_hub.py` 一并并入 `core`。拒绝，因为这会让 change 从“布局收敛”升级成“架构重划”。

### 5. 不保留任何旧导入路径或兼容别名

决策：所有 `from src.base...` 和 `from src.core.agent_loop...` 风格引用都直接改到新路径，不保留桥接模块或兼容 re-export。

理由：用户已经明确不考虑后向兼容，这次就应该一次收干净。

备选方案：保留 `src/base/__init__.py` 或 `agent_loop.py` 做转发。拒绝，因为那只是把冗余藏起来。

## Risks / Trade-offs

- [移动 `llm.py` / `text2text.py` 会触发多处导入更新] → 先全仓搜索 `from src.base`，一次性改完并用测试兜底。
- [删除 `src/base/agent.py` 可能误伤隐藏依赖] → 先确认当前仓库中是否仍有引用；若没有，再直接删。
- [目录移动容易让 change 看起来像“大重构”] → 本轮只移动运行时核心文件，不顺手整理无关模块。
- [未来若真需要独立“基础层”会怎样] → 未来出现真实需求再拆，而不是为想象中的演化保留当前失真目录。

## Migration Plan

1. 新增 `src/core/agent.py`、`src/core/llm.py`、`src/core/text2text.py`。
2. 更新 `src/core/__init__.py`、`src/service/model_hub.py`、TUI 和测试导入。
3. 删除 `src/base/` 整个目录与 `src/core/agent_loop.py`。
4. 跑聚焦测试，确认行为不变且旧路径无残留。

## Open Questions

- `src/service/model_hub.py` 后续是否也应迁到 `src/core/`。当前建议：本轮不做，等出现更强的服务层收敛需求再说。
