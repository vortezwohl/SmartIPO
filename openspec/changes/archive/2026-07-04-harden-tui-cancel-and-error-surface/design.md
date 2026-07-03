## Context

SmartIPO 当前已经迁移到 `easyharness.Agent` 事件流主干，TUI 直接消费 `AgentEvent`，这是对的；但 `/stop` 仍停留在 EasyHarness 0.1.2 之前的假设上，只取消 Textual worker，不驱动 runtime 的真实取消。这导致三个问题同时出现：

- UI 认为当前 turn 已结束，但底层 agent 可能仍在生成或执行工具；
- queue 可以继续推进，但旧 turn 的真实终态与新 turn 的可见状态发生竞态；
- runtime 已经提供的 `cancelled` 语义没有被 UI 正确消费，导致取消被误当成完成、失败或普通系统消息。

另一条问题链在失败展示边界：EasyHarness 工具失败时会保留完整 traceback 作为内部诊断，这对模型、测试和调试有价值；但 TUI 当前会把这些 detail 直接渲染进主 timeline。对最终用户而言，这既噪音过大，也会破坏聊天面而不是帮助理解问题。

约束很明确：

- 不新增依赖，不改动项目整体 runtime 架构；
- 不重新引入跨 UI 共享 timeline/reducer 协议；
- 优先复用 `easyharness.Agent.cancel()` 和现有 `AgentEvent(status="cancelled")`；
- 完整异常仍要保留给 agent 和内部调试链路，不能为了“界面干净”而丢失诊断。

## Goals / Non-Goals

**Goals:**
- 让 `/stop` 真正触发 EasyHarness runtime 取消，而不是只在 UI 侧假装结束。
- 让 active turn 以 runtime 的真实终态事件完成收口，避免 UI 与底层运行状态分叉。
- 为用户主动停止建立稳定的 timeline 留痕，英文、低存在感、长期留在历史中。
- 让 `cancelled` 成为 TUI 的一等终态，而不是落回 `completed` / `failed` 的近似语义。
- 让主 timeline 只显示用户级失败摘要，不再默认展示 traceback 等原始堆栈。
- 保留完整失败诊断在内部元数据中，供 agent、测试和后续调试能力复用。

**Non-Goals:**
- 不修改 `src/agent.py` 的外部构造协议或模型/tool 装配方式。
- 不修改 EasyHarness 上游包或在 `.venv` 中做本地补丁。
- 不增加“错误详情面板”“展开 traceback”或新的 inspector UI，本次只收敛默认主对话面。
- 不把 TUI 展示策略抽成新的共享格式化层或跨 UI 合同。

## Decisions

### 1. `/stop` 改为“两阶段取消”，而不是立即本地结案

用户执行 `/stop` 后，TUI 先发出真实取消请求，再等待当前流以 `cancelled` 终态事件或流结束完成收口。也就是说，`/stop` 不再立即调用本地 `_finish_active_turn()`，而是把 active turn 标记为“正在停止”，并把最终收口权交还给 runtime 事件流。

这样做的原因：

- runtime 才知道模型流或工具流是否真的停下；
- queue 只有在当前 turn 真实结束后再启动下一条，才不会和旧流抢状态；
- 这能自然复用 EasyHarness 已有的 `cancelled` 语义，而不是在 UI 侧自创一套“中断但其实不知道底层是否停了”的假状态。

备选方案：
- 立即取消 Textual worker 并本地收尾。拒绝，因为这正是当前问题根源。

### 2. `cancelled` 作为一等终态贯穿 thinking / tool / assistant / system

TUI 必须显式处理 `event.status == "cancelled"`，而不是默认把未知终态落到 Done 或 Failed。assistant 在 cancelled 时保留已累计的 partial body；tool 在 cancelled 时显示用户中止语义，而不是失败；thinking 在 cancelled 时停止计时并退出活动状态；system cancelled 事件用于完成 turn 级收口。

这样做的原因：

- 用户主动停止不等于异常失败；
- “保留半截 assistant 文本 + 独立停止事件”比“把半截文本标成 failed”更符合聊天心智；
- tool cancelled 与 tool failed 分开，后续如果要做更多状态样式也有稳定基础。

备选方案：
- 把 cancelled 统一映射成 completed。拒绝，因为会掩盖主动停止这一真实事实。
- 把 cancelled 统一映射成 failed。拒绝，因为这会把用户控制动作误报成系统错误。

### 3. timeline 停止留痕使用稳定的本地英文事件，而不是直接显示 runtime 原文

当一轮因用户停止而结束时，timeline 追加一条本地英文事件，例如 `Reply stopped.`，并使用与 `Thinking ...` 接近的低对比样式。它是一个事实留痕，不承担错误解释或调试输出职责。

原因：

- runtime cancelled 事件携带的 `text` 可能是 partial assistant 文本，也可能为空，不能直接拿来当用户提示；
- 停止事件需要稳定、可测试、可跨模型复用，不能依赖底层模型/SDK 的自然语言输出；
- 低强调样式可以保留历史事实，同时不抢占用户对正文与工具结果的注意力。

备选方案：
- 直接显示 `Interrupted the active reply.` 这类系统消息。可用，但视觉上过重，且没有把“停止”与普通系统提示区分开。
- 不留痕，只保留半截 assistant 文本。拒绝，因为用户之后无法判断回复是自然结束还是被主动停下。

### 4. 失败展示在 TUI 边界做“摘要/诊断分层”，不修改 runtime 合同

EasyHarness 现有工具失败合同已经同时保留 `error`、`preview`、`detail(traceback)`。本次不改 runtime，也不删掉 detail；TUI 只是在主 timeline 渲染时采用“用户级摘要优先”，并把原始 detail 留在 `_TimelineItem.metadata` 或内部字段中，默认不显示。

原因：

- 这是最小变更面：只收口用户体验，不扩散到依赖包或公共协议；
- 保持 agent/测试仍可拿到完整异常；
- 后续如果真要做 inspector，只需要复用已保留的 metadata，不必再回头补采集。

备选方案：
- 直接改 EasyHarness 的失败输出合同。拒绝，因为当前仓库依赖公开包，不适合在本 change 中修改上游实现假设。
- 简单地把 `detail` 清空。拒绝，因为会丢失有价值的内部诊断。

### 5. 继续依赖 turn_id 隔离迟到事件，但把 turn 收口时机后移到真实终态

当前 `_apply_agent_event_for_turn()` 已有 turn_id 过滤能力，这是对的，继续保留；变化点不是机制本身，而是 turn 何时从 active 变成 inactive。新的 inactive 时机应在 cancelled/completed/failed 真实终态后发生，而不是在用户刚按下 `/stop` 的那一刻。

原因：

- turn_id 过滤已经足够解决迟到事件污染问题，没必要再造更重的并发控制层；
- 只要把收口时机放对，现有隔离机制就能继续成立。

备选方案：
- 引入额外线程同步对象或 per-turn cancellation token。拒绝，因为当前运行模型与问题规模都不需要。

## Risks / Trade-offs

- [runtime 取消返回速度取决于底层模型/工具] → UI 先进入“stopping”本地状态，给出状态反馈，但不抢先宣告 turn 已结束。
- [cancelled 事件顺序可能因不同底层路径略有差异] → 以“任一终态事件 + 流结束”作为稳态边界，避免把单一子事件顺序写死。
- [隐藏 traceback 后，用户定位问题的信息变少] → 主 timeline 保留 concise error summary，同时在内部 metadata 保留完整 detail，测试和未来 inspector 仍可用。
- [新增 cancelled 样式与状态标签会影响既有文本断言] → 保留 `_render_timeline_text()` 稳定接口，并为 stopped/cancelled 行补专门断言。

## Migration Plan

1. 先调整 TUI turn 状态机，让 `/stop` 改为 runtime-backed cancel request。
2. 补齐 `cancelled` 在 thinking/tool/assistant/system 四类事件中的本地收口逻辑。
3. 增加停止留痕渲染和低强调样式。
4. 引入失败摘要提取逻辑，确保 tool/system failure 的主 timeline 不再展示 traceback。
5. 用 TUI 测试覆盖真实取消闭环、旧事件隔离、停止留痕和异常摘要边界。

回滚策略：

- 若真实取消链路出现兼容性问题，可临时回退到现有 UI-only `/stop` 行为；
- 失败摘要逻辑可独立回滚，不影响 runtime 取消主链路。

## Open Questions

- None. 当前关键约束和依赖接口都已明确，适合直接进入实现。
