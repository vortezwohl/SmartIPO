## Context

`build-textual-agent-workbench` 已经把 SmartIPO 的真实主路径固定为 Textual workbench + 会话型运行时，但 [src/core/agent_loop.py](/D:/github-project/SmartIPO/src/core/agent_loop.py) 仍然同时公开 `AgentLoop.run_once(...)` 和 `AgentSessionLoop.run_turn(...)` 两种语义。前者本质上只是早期过渡层，后者才是当前产品实际依赖的入口。

在当前状态下，双接口带来三个问题：
- 主脑控制器名字和真实语义不一致，workbench 用的是 session agent，却要引用 `AgentSessionLoop`；
- 单轮 `run_once` 让调用方看起来仍然可以围绕“一次调用”构造新入口，和当前产品方向相反；
- `_SingleTurnSessionRunner` 这类兼容层只为双接口并存而存在，增加了不必要的实现面。

当前约束很明确：
- 用户已明确表示不考虑后向兼容；
- 这次只收敛 API，不改模型配置、工具注册和 Textual 可见行为；
- 需要保留会话历史、持久 runner 和统一事件流。

## Goals / Non-Goals

**Goals:**
- 对外只保留一个公开主脑控制器，名字统一为 `Agent`。
- 公开控制器默认代表“单会话、可连续多工具调用”的 workbench 语义。
- 删除 `run_once(...)` 和只为其存在的兼容层。
- 让 `src/core/__init__.py`、TUI 与测试都依赖统一后的公开名字。

**Non-Goals:**
- 不改变 strands runtime 的事件桥接协议。
- 不改变 fileglide、Seedream 或默认工具注册行为。
- 不引入新的抽象层、工厂或多种 agent 模式。
- 不做任何后向兼容别名或迁移包装。

## Decisions

### 1. 公开控制器收敛为单一 `Agent`

决策：删除 `AgentLoop` 与 `AgentSessionLoop` 双公开类，保留一个公开类 `Agent`，其职责等同于当前会话型 `AgentSessionLoop`。

理由：当前产品只有 workbench 这一条真实入口，而它需要的就是持久会话语义。让公开类名直接表达真实语义，比保留“Loop/SessionLoop”二分更清晰。

备选方案：继续保留 `AgentLoop` 和 `AgentSessionLoop`。拒绝，因为这只是延续过渡期形态。

### 2. 不再保留 `run_once(...)`

决策：公开 API 不再提供单轮 `run_once(...)`，统一为 `run(prompt)`。

理由：当前没有第二个需要“一次性无状态调用”的正式入口，而单轮 API 只会诱导后续代码继续围绕错误抽象扩散。

备选方案：保留 `run_once(...)` 作为内部 helper。拒绝，因为即便只降为内部 helper，也会继续维持两种心智模型。

### 3. 删除 `_SingleTurnSessionRunner` 兼容层

决策：删除当前只为双接口共存服务的 `_SingleTurnSessionRunner`。

理由：在不考虑后向兼容的前提下，运行时要么支持 `create_session_runner(...)`，要么测试替身直接模拟这条接口；没必要继续保留单轮回退层。

备选方案：保留兼容层给假 runtime 用。拒绝，因为测试替身改成提供 `create_session_runner(...)` 成本更低，也更贴近真实运行时。

### 4. `StrandsRuntime` 以会话 runner 为唯一主入口

决策：保留 `create_session_runner(...)` 作为运行时主入口；若 `run(...)` 仍保留，也只作为内部薄包装，不作为对外推荐使用面。

理由：真正稳定的抽象是“先建会话 runner，再连续处理 prompt”，而不是“每次单轮调用都重新拼装”。

备选方案：公开 `run(...)` 和 `create_session_runner(...)` 并列。拒绝，因为这会重新引入双心智模型。

## Risks / Trade-offs

- [测试替身需要同步改成 session runner 形态] → 直接让 fake runtime 实现 `create_session_runner(...)`，保持测试契约与真实运行时一致。
- [局部文件里仍会出现 `strands.Agent` 与项目内 `Agent` 同名] → 在实现文件中把框架类显式别名为 `StrandsAgent`，避免歧义。
- [删除单轮 API 后，未来若真出现离线单次调用场景需要重建入口] → 未来若出现真实需求，再基于 `Agent` 的会话语义新增明确场景名入口，而不是恢复通用 `run_once`。

## Migration Plan

1. 把当前 `AgentSessionLoop` 重命名并收敛为唯一公开 `Agent`。
2. 删除 `AgentLoop`、`run_once(...)` 与 `_SingleTurnSessionRunner`。
3. 调整 `src/core/__init__.py`、TUI 和测试导入，全部改为依赖 `Agent`。
4. 运行聚焦测试，确认行为不变但公开 API 更简单。

## Open Questions

- `StrandsRuntime.run(...)` 是否也一并删掉，只保留 `create_session_runner(...)`。当前建议是：若没有其他内部调用方，就一起删。
