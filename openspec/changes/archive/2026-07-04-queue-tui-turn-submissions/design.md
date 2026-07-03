## Context

当前 `AgentWorkbenchApp` 在 `on_input_submitted()` 中收到输入后，会立即追加用户消息、本地 thinking 占位，并直接启动 `_run_turn_worker(prompt)`。该 worker 使用 `Textual @work(thread=True, exclusive=True, group="agent")`，实际语义是“新任务启动时取消同组旧 worker”，不是“按顺序排队执行”。

这带来两个直接问题：
- 多次快速提交时，新任务会在旧任务尚未自然结束前启动，旧任务又因为线程取消不具备即时终止保证，事件可能交错进入 UI。
- TUI 当前只维护“正在运行的单轮展示态”，没有待处理队列模型，因此无法稳定显示多个排队消息。

这个改动只触及 TUI 本地状态层，不修改 EasyHarness runtime、工具协议或模型装配。

## Goals / Non-Goals

**Goals:**
- 在单个 TUI 会话内把用户提交收敛为严格串行语义。
- 允许用户在上一轮尚未完成时继续提交，并把所有待处理消息保留在时间线中。
- 为每条用户消息显示明确状态，包括排队中、处理中、已完成和失败。
- 在会话重置后清空队列，并阻止旧轮次线程的晚到事件污染新会话界面。

**Non-Goals:**
- 不提供排队消息取消、重排或优先级调整。
- 不改变 agent 的对话语义或 EasyHarness 的事件格式。
- 不引入跨进程、跨会话或持久化队列。

## Decisions

### 1. 使用 App 本地 FIFO 队列串行消费提交

`AgentWorkbenchApp` 新增一个最小待处理队列，例如 `deque[_PendingTurn]`，每次提交只负责入队。若当前没有 active turn，则立即启动队首；否则保持排队，等待当前 turn 完成后自动启动下一个。

选择这个方案，而不是继续依赖 `exclusive=True` 或让 Textual worker 帮忙排队，原因是当前需求是“可见的业务队列”，而不是单纯“后台只能跑一个线程”。队列状态必须成为 TUI 本地状态的一部分，才能正确渲染多个待处理消息。

备选方案：
- 保留 `exclusive=True`：会取消旧 worker，不满足串行执行。
- 在提交时禁用输入框：会阻止多条排队消息存在，不满足需求。

### 2. 复用用户消息条目作为队列可视化载体

不新增独立“队列面板”或新的消息类型。每次提交仍然先追加一条 `user` 时间线项，并在其 `metadata` 中记录 `turn_id`、`queue_state` 和 `queue_position`。渲染时直接把这条用户消息展示为“处理中”或“排队中 #N”。

这样做的原因是最小 diff 且最符合当前时间线模型：队列里的本质对象就是用户提交本身，没有必要再复制出第二份显示数据。

备选方案：
- 额外插入 `system`/`queue` 条目：会让时间线冗余，并带来双份状态同步。

### 3. 仅在 turn 真正开始执行时创建本地 thinking 占位

提交进入排队时不创建 thinking。只有当该 turn 成为 active turn、真正启动 `agent.stream()` 前，才调用 `_start_local_thinking()`。

原因是 thinking 表示模型当前正在处理，而不是“这条消息未来会处理”。如果在排队阶段也创建 thinking，会让多个待处理项看起来像同时执行。

### 4. 用 turn_id 保护 UI，忽略旧线程的晚到事件

每次启动 turn 时生成唯一 `turn_id` 并记录为当前 active turn。worker 在线程回传事件或完成通知时，必须携带对应 `turn_id`；UI 侧只接受与当前 active turn 匹配的事件。`new_session` 会同时清空 active turn 和待处理队列，因此旧线程即使晚到，也只能被丢弃。

选择这个方案是因为线程 worker 的取消不可靠，不能把“不会再有旧事件”当成前提。比起尝试强杀线程，更小也更稳的是在 UI 层做事件归属校验。

## Risks / Trade-offs

- [Risk] 队列状态、active turn 和时间线项元数据之间出现不同步。 → Mitigation：把“入队、启动、完成、失败、重置”收敛为少数集中方法，统一更新状态。
- [Risk] 失败路径只追加错误消息但没有继续拉起下一条，导致队列卡死。 → Mitigation：完成和失败都必须走同一套 drain-next 逻辑。
- [Risk] 新会话后旧线程继续回传事件。 → Mitigation：所有事件和完成回调都携带 `turn_id`，不匹配则直接忽略。
- [Trade-off] 当前不支持取消排队中的单条消息。 → 这是刻意简化；只有在真实使用场景出现时再增加局部操作。
