## Context

当前系统的时间线语义分散在两处：
- `src/core/strands_runtime.py` 负责发出 `LoopEvent` 事实；
- `src/tui/app.py` 直接把这些事件翻译成 `TimelineItem` 并渲染。

这套做法在 workbench 初版足够快，但一旦需求变成“同一时间线语义既服务 TUI，也服务未来 WebUI”，问题就暴露出来了：
- TUI 正在承担本该属于 core 的事件解释逻辑；
- 工具结果目前只有 `result_summary`，不够支撑“概要 + 详情 + 折叠”；
- thinking 动画如果继续靠 runtime 发事件，会污染通用事件流。

本轮真正要收敛的不是某个 UI 细节，而是“运行时事实 -> 会话时间线状态”的中间表示层。

## Goals / Non-Goals

**Goals:**
- 在 `src/core` 定义通用 timeline entry/state/reducer。
- 让工具调用成为可复用的标准时间线项目，支持耗时、概要、详情和折叠建议。
- 让 thinking 动画成为 UI 本地渲染行为，而不是 runtime 事件风暴。
- 让 TUI 改为消费通用 timeline state，为 WebUI 直接复用铺路。

**Non-Goals:**
- 不重写 strands runtime 主流程。
- 不引入前后端共享协议层或网络同步层。
- 不在本轮实现 WebUI。
- 不为“未来可能有更多动画”提前引入复杂插件系统。

## Decisions

### 1. 用 reducer 收敛 `LoopEvent -> TimelineEntry`

决策：在 `src/core` 新增一个 timeline reducer，把运行时事实事件翻译为稳定的 timeline state。

理由：TUI 和 WebUI 真正共享的是“状态解释规则”，不是 widget 代码。

备选方案：继续让每个 UI 自己解释 `LoopEvent`。拒绝，因为这会复制业务语义并制造双份 bug。

### 2. thinking 动画只保留基础状态，不进入事件流

决策：runtime 只发 `thinking_started` / `thinking_completed` / `thinking_failed` 这类事实；UI 根据 entry.status 本地渲染 `thinking . .. ...`。

理由：动画是表示问题，不是领域事实。把动画写进事件流会让所有消费者承担噪音。

备选方案：runtime 周期性发 `thinking .` / `thinking ..` / `thinking ...`。拒绝，因为这会污染事件模型且无法复用。

### 3. 工具结果拆成 preview + detail，而不是只保留 summary

决策：工具完成事件或 timeline reducer 产物里需要至少区分：
- 结果概要 `preview`
- 长结果详情 `detail`
- 是否可折叠 `collapsible`
- 默认折叠建议 `collapsed_by_default`

理由：未来 TUI/WebUI 的“折叠展示”依赖这个语义分层。

备选方案：继续只传 `result_summary`。拒绝，因为这不足以支持长结果展开。

### 4. 先做统一模型，再让 TUI 适配

决策：TUI 不再维护自己的临时 `TimelineItem` 解释规则，而是消费 core timeline state。

理由：这能把跨 UI 共享逻辑收回 core，同时保持 UI 端只关心渲染。

## Risks / Trade-offs

- [timeline reducer 过早抽象] → 只覆盖当前已经存在的 user/thinking/tool/assistant/system 五类条目，不做泛化插件层。
- [工具详情过大] → reducer 只生成 preview 和 detail 分层，不要求所有 UI 默认全量展开。
- [旧 TUI 逻辑迁移时回归] → 用现有 TUI smoke test 补强工具卡片和 thinking 展示断言。

## Migration Plan

1. 在 core 增加 timeline entry/state/reducer。
2. 扩展运行时工具完成事件的可消费信息，至少能支撑 preview/detail 分层。
3. 让 TUI 改为消费 timeline reducer 结果，并本地渲染 thinking 动画。
4. 补测试，确认 reducer 语义与 TUI 展示不回归。

## Open Questions

- 工具 detail 的默认截断长度是否需要放到配置。当前建议：先写成 reducer 内部稳定默认值，本轮不引入配置项。
