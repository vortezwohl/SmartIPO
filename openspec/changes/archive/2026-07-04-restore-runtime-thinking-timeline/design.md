## Context

当前 SmartIPO TUI 直接消费 `easyharness.AgentEvent`，但 `src/tui/app.py` 仍把 `thinking` 分成一种特殊的、只用于等待回复的动态活动行。结果是：

- 本地 provisional `Thinking ...` 占位可以出现；
- 真实 runtime `thinking delta/completed` 文本不会被累计进可见正文；
- 一旦 assistant 或 tool 阶段开始，现有逻辑会移除 `ephemeral thinking`，导致真实 reasoning 历史丢失；
- 用户最终只能看到 tool 摘要和 assistant 结论，看不到“先想了什么，再为什么调工具”的过程。

这与项目已经确定的 “TUI 直接消费 `AgentEvent` 作为事实源” 相冲突：runtime 已经提供了事实，但展示层把事实又降级回了占位提示。与此同时，本项目此前的 `refine-tui-english-activity-rendering` 变更把 thinking 定义为“assistant 开始后必须消失的临时态”，这正是当前行为的来源，因此这次设计必须显式推翻这个旧假设，而不是仅在实现层打补丁。

约束也很明确：

- 不改 EasyHarness runtime，不新增事件类型；
- 不引入新的跨 UI timeline/view-model 协议；
- 继续把展示态局限在 TUI 本地；
- 默认保留当前简洁的 tool 主行语法，不把界面重新做成调试日志。

## Goals / Non-Goals

**Goals:**

- 让真实 runtime `thinking` 文本进入用户可见历史，而不是只显示本地 `Thinking ...` 占位。
- 让 thinking、tool、assistant 在同一轮中按实际发生顺序保留，形成完整 chronology。
- 让“等待态”和“真实 reasoning 内容”在展示层有清晰边界，避免继续混为一谈。
- 在不新增底层协议的前提下，把修复控制在 `src/tui/app.py` 与测试层。

**Non-Goals:**

- 不修改 `easyharness.AgentEvent` 结构或 runtime flush 逻辑。
- 不重新设计 TUI 整体视觉语言或工具结果详情面板。
- 不把所有内部调试信息都暴露到用户界面；本次只恢复 runtime 已公开给 UI 的 `thinking` 文本。
- 不处理与本次目标无关的 `/stop` 失败用例或其他 TUI 遗留问题。

## Decisions

### 1. 把 provisional waiting 和 runtime thinking 明确拆成两种展示语义

决策：保留当前本地 `Thinking ...` 占位，但仅把它视为“尚未收到任何真实 reasoning 内容前的过渡态”。一旦收到 runtime `thinking delta/completed`，界面必须立刻切换到“真实 thinking 历史”语义。

原因：

- 这保留了用户在首包前的交互反馈，不会出现静默空窗；
- 同时避免继续把 runtime 真正发来的文本当成可删除占位；
- 这是最小改动，因为现有 `_TimelineItem` 已足够承载两类状态，只需要通过 metadata 区分即可。

备选方案：

- 完全删除本地 provisional waiting。  
  不采用，因为当 provider 不发 reasoning 或 reasoning 首包较慢时，交互反馈会退化。

- 继续只保留 `Thinking ...`，不展示真实 reasoning 文本。  
  不采用，因为这正是当前缺陷本身。

### 2. 真实 thinking 内容走 Assistant 表面，而不是新增长期独立消息语法

决策：当 runtime 发来真实 thinking 文本时，TUI 应将其渲染为 assistant-style 会话内容，使用现有聊天消息表面进入 timeline；必要的阶段区分放在本地 metadata，而不是对用户再引入一种长期独立的消息语法。

原因：

- 用户明确期待 “thinking 的内容通过 Assistant 输出”，这比保留一条抽象的 `thinking` 技术行更符合直觉；
- thinking 文本本质上仍是模型侧生成的自然语言，只是阶段早于最终回答；
- 复用 assistant 渲染路径能让阅读体验保持一致，同时避免再造一套“第三类历史消息”的长期视觉规范。

备选方案：

- 把真实 thinking 保留为独立 `thinking` 历史项。  
  不采用，因为这会在长期历史里同时存在 `Thinking ...`、`Assistant >`、`Tool` 三种主语法，增加扫描负担。

- 把 thinking 直接并入最终 assistant 正文。  
  不采用，因为这样会丢失阶段边界，也无法体现 tool 调用前已经发生过 reasoning。

### 3. chronology 采用追加保留策略，后置阶段不得覆盖前置真实历史

决策：同一轮里的真实 `thinking`、`tool`、`assistant` 一旦进入可见历史，就按实际到达顺序保留。tool started/completed 只能在 thinking 之后追加，assistant started/delta/completed 只能在 tool 或 thinking 之后追加，后置阶段不得通过“复用同一条 item”抹掉前置真实内容。

原因：

- 用户关心的是过程链路，不只是终点；
- 追加保留比“阶段之间复用一个活动条目”更容易推理，也更容易测试；
- 这能直接满足“tool timeline 应该覆盖 thinking”的要求，即 tool 是承接 thinking，而不是替换 thinking。

备选方案：

- 让 thinking/tool/assistant 共用一条可变 item。  
  不采用，因为阶段一多就会互相覆盖，正是当前问题来源。

### 4. 只有没有真实 thinking 文本时，provisional waiting 才允许完全消失

决策：若一轮从头到尾都没有收到任何真实 `thinking text`，则本地 `Thinking ...` 仍可像今天一样在 assistant 或 tool 真正开始后消失；但只要曾收到过真实 `thinking delta/completed`，这段历史就必须保留。

原因：

- 这保留了原有 waiting 行为中合理的部分；
- 同时避免“空占位残留成历史垃圾”；
- 规则简单，可直接写成测试：是否收到过真实 thinking 文本，是唯一分叉条件。

备选方案：

- 所有 thinking 都一律保留历史。  
  不采用，因为没有文本的占位留在历史里没有价值。

### 5. 不新增跨层协议，只在 TUI 本地 view-state 中修正生命周期

决策：所有改动都留在 `src/tui/app.py` 本地，包括 item metadata、visible filter、assistant/tool/thinking 生命周期和文本渲染规则；不新增共享 reducer、跨 UI model 或 runtime adapter。

原因：

- 现有架构已经明确“直接消费 `AgentEvent`，不再引入第二套 timeline 协议”；
- 这次问题纯属展示层把事实处理错了，不值得上升成新架构；
- 改动边界最小，验证半径也最小。

备选方案：

- 引入独立 TUI timeline model 或跨 UI phase reducer。  
  不采用，因为这是为一个局部生命周期问题付出长期架构成本。

## Risks / Trade-offs

- [Risk] thinking 文本进入主会话后，timeline 会比现在更长。  
  → Mitigation：只保留真实文本，不保留空占位；tool 仍保持单行主摘要，避免全局日志化。

- [Risk] 某些 provider 可能不会稳定提供 reasoningText。  
  → Mitigation：保留 provisional waiting 回退路径；没有真实 thinking 时，界面仍维持当前最小等待反馈。

- [Risk] 复用 assistant 表面展示 thinking，可能让“阶段不同但前缀一致”。  
  → Mitigation：阶段区分保留在 chronology 和本地 metadata 中；用户视角优先保持自然阅读，而不是暴露技术分类。

- [Risk] 当前 active OpenSpec 中已有 “thinking 必须消失” 的旧要求，若不一并修正，后续 archive 时会产生行为冲突。  
  → Mitigation：本 change 显式建立新的 capability/spec，并在实现阶段把旧行为相关断言一起替换。

## Migration Plan

1. 先调整 `src/tui/app.py` 中 thinking 的 metadata 和生命周期，明确 provisional 与 runtime thinking 的分界。
2. 再修改 assistant/tool 事件处理逻辑，保证后置阶段只追加、不覆盖前置真实历史。
3. 接着更新 timeline 可见性和渲染逻辑，让真实 thinking 使用 assistant-style 表面展示。
4. 最后更新 `test/test_tui_app.py`，新增真实 `thinking delta/completed` 展示覆盖，并替换旧的 “assistant 开始后 thinking 必须完全消失” 断言。

回滚策略：

- 本变更仅涉及 TUI 本地展示层与测试，不涉及数据迁移或 runtime 合同迁移；
- 若最终阅读体验不理想，可直接回滚对应实现与测试；
- 回滚后会恢复当前 “thinking 仅为临时占位” 的旧行为。

## Open Questions

- 当前无阻塞性开放问题。
- 若实现中发现 assistant-style thinking 仍需要轻微视觉区分，应优先通过局部样式或 metadata 驱动的小调整解决，而不是重新引入独立长期消息语法。
