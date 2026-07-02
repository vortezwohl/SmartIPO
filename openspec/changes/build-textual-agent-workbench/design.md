## Context

`SmartIPO` 当前已经有最小 strands runtime、工具契约和一个真实业务工具，但它仍然停留在“单轮调用骨架”阶段。当前 [src/core/agent_loop.py](/D:/github-project/SmartIPO/src/core/agent_loop.py) 只能做一次 `run_once(...)`，既没有会话型消息历史，也没有思考/工具/流式输出事件桥接，更没有本地工作台入口。

这次需求并不是再做一个更大的业务流程，而是做一个类似 Claude Code / OpenClaw 的本地 agent workbench。核心约束有四个：
- agent 必须在一个任务中连续调用多个工具直到自然结束；
- fileglide 必须作为完整本地文件系统工具集接入；
- assistant 输出、思考和工具过程都必须可见且流式；
- 模型配置必须从调用点抽离到 `src/model_config.py`。

`resume-maker` 已经证明了一条正确路径：用 strands 负责主脑 loop，用 tool wrapper 负责真实工具执行边界，用 Textual 时间线负责过程可视化。但 `SmartIPO` 不需要照搬它的 session repository、deepdive/copilot 状态机和数据库持久化。

## Goals / Non-Goals

**Goals:**
- 提供一个基于 Textual 的本地 agent workbench，会话体验接近 Claude Code / OpenClaw。
- 把当前单轮运行时升级为会话型 agent runtime，让主脑在一次任务内连续规划并执行多个工具。
- 完整接入 fileglide Python 包提供的文件系统工具集。
- 建立统一事件流，覆盖思考、工具调用和 assistant 流式输出，并在 TUI 中展示耗时。
- 新增 `src/model_config.py` 与对应装配入口，集中管理主脑模型与采样参数。

**Non-Goals:**
- 不引入数据库持久化、历史会话管理或复杂多用户能力。
- 不复制 `resume-maker` 的 deepdive/copilot 业务状态机。
- 不在本次变更中把所有业务能力都接成工具，只要求 fileglide 和现有 SmartIPO 工具能共存。
- 不做 Web 前端或远程 API，仅做本地 Textual workbench。

## Decisions

### 1. Workbench 使用单会话 Textual 时间线，而不是复杂多面板 IDE

决策：新增一个 Textual App，主视图采用单列时间线 + 输入框。时间线中混排用户消息、assistant 流式回复、思考占位和工具卡片；每个运行中项目都显示实时耗时。

理由：这是最接近 Claude Code / OpenClaw 使用感、同时实现成本最低的形态。`resume-maker` 的 TUI 已经证明单列时间线足够承载过程可视化，没必要先做文件树、侧栏、标签页这些复杂外壳。

备选方案：直接做多栏 IDE 式 UI。拒绝，因为这会把重点从 agent loop 和事件流转移到界面装饰。

### 2. 运行时升级为会话型 AgentSessionLoop，而不是继续堆 `run_once`

决策：保留现有最小 runtime 桥接思路，但新增一个会话型 loop/controller，负责：
- 维护同一会话的消息历史；
- 维护 persistent `strands.Agent` 或等价 conversation state；
- 接收用户任务后启动一轮完整 agent invocation；
- 把回调事件和工具执行事件持续送给 UI。

理由：用户要的是“接一个任务后自己有序做完”，而不是“单次调用 + 最终文本”。这条能力必须在 loop 语义层成立，不能只靠 prompt 文案碰运气。

备选方案：继续用 `run_once`，每次工具调用完就由项目代码再手动发起下一轮。拒绝，因为这会重新退回手写 tool-call loop。

### 3. fileglide 工具层直接复用 `resume-maker` 的 Python facade 方案

决策：新增 `src/tool/fileglide_tools.py`，尽量复用 [resume-maker 的 fileglide_tools.py](/D:/github-project/resume-maker/src/tool/fileglide_tools.py) 的工具名、schema 和 `FileGlideFacade` 路线。

理由：你已经把 `fileglide` Python 包装进 `.venv`，最优雅的方案就是直接复用 Python facade，而不是再包一层 CLI subprocess adapter。这样工具语义稳定、测试也更干净。

备选方案：调用全局 `fileglide.exe`。拒绝，因为 CLI 解析、Windows 路径和错误处理都更脆。

### 4. 过程可视化统一走事件流，不把 UI 逻辑塞进工具或主脑 prompt

决策：新增统一事件类型，至少包含：
- `thinking_started/completed/failed`
- `tool_started/completed/failed`
- `assistant_stream_started/delta/completed/failed`

其中：
- strands `callback_handler` 负责推送模型的流式文本与 reasoning 片段；
- tool wrapper 负责推送真实工具生命周期与耗时；
- Textual UI 只消费事件，不直接理解 strands 内部对象。

理由：这能把“运行时事实”与“UI 表现”解耦。工具的开始/结束/失败必须由 wrapper 定义，不能只靠模型事件猜测。

备选方案：UI 直接轮询 agent 结果或只显示最终文本。拒绝，因为不满足过程可视化要求。

### 5. `model_config.py` 只先管理主脑模型配置

决策：新增 `src/model_config.py` 与 `src/service/model_hub.py`，第一版只集中管理主脑模型调用点，例如 `agent_session_round`，以及对应的 provider、model、temperature、top_p、seed、api key env、api base env。

理由：用户明确要求抽离配置，这是合理的。但当前还没有多个文本类智能工具，不需要一开始就复制 `resume-maker` 那种 brain/tool 双表配置。

备选方案：所有调用参数先继续写在装配代码里。拒绝，因为这与需求直接冲突。

### 6. 第一版会话状态先保存在内存，而不是数据库

决策：本地 workbench 第一版只做当前进程内单会话状态，必要时可以支持“新建会话”清空上下文，但不做持久化恢复。

理由：真正复杂的是 agent loop、事件桥接和 UI，不是存储。现在先把交互闭环做对，后续如果真需要历史会话，再单独引入 repository。

备选方案：一开始就做数据库持久化。拒绝，因为那会把这次 change 变成状态管理项目。

## Risks / Trade-offs

- [strands callback 的 reasoning/token 事件颗粒度不完全符合 UI 预期] → 先用最小 callback handler 适配，UI 以 assistant delta 和 thinking placeholder 为主，不依赖底层事件完全稳定。
- [fileglide 工具集很多，初版 prompt 可能滥用工具] → 通过 system prompt 明确“先读再改、不要重复试探、能一次完成就不要拆碎”。
- [单会话内存状态在长任务中会膨胀] → 第一版先提供明确的 turn/token 限制；真正需要时再加 context compaction。
- [没有持久化导致重启丢会话] → 明确作为第一版非目标，后续若用户需要再单独做 session storage change。
- [UI worker 与 agent callback 的线程边界容易出错] → 使用线程安全队列把事件从 worker 线程送回 Textual 主线程，不直接跨线程更新 widget。

## Migration Plan

1. 新增 `src/model_config.py` 和 `src/service/model_hub.py`，收敛主脑模型配置。
2. 新增 `src/tool/fileglide_tools.py`，并把 fileglide 工具集接入默认注册表。
3. 扩展 `src/tool/contracts.py` 和 `src/core/strands_runtime.py`，支持事件流与更丰富的 tool context。
4. 新增会话型 `AgentSessionLoop` / controller，并让 strands callback 与工具 wrapper 都输出统一事件。
5. 新增 `src/tui/app.py`，构建 Textual 工作台并渲染时间线。
6. 补充 focused tests，锁定模型配置、fileglide 暴露边界、事件流和 TUI 基本交互。

本次不涉及数据迁移。若实现失败，回滚代码即可。

## Open Questions

- 第一版是否需要支持多个并行本地会话。当前建议只做一个当前会话。
- 是否要把 `Seedream` 工具默认暴露给本地 workbench。当前建议保留，但 fileglide 作为主工具面。
- assistant 的 reasoning 文本是否全部展示给用户。当前建议只显示“思考中”占位和耗时，不直接暴露全部原始 reasoning。
