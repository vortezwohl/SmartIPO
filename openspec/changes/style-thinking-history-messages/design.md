## Context

当前 TUI 已经能把真实 runtime thinking 文本保留为历史消息，但真实 thinking 历史仍沿用普通 assistant 的前缀和亮度样式。这样虽然 chronology 正确，却让“推理过程”和“正式结论”在视觉上几乎没有边界，用户需要靠阅读内容本身才能判断消息性质。

现有实现已经具备一个适合演进的基础：waiting-only thinking 继续以 `kind == "thinking"` 的临时活动行存在，真实 runtime thinking 在收到非空文本后也仍保留 `kind == "thinking"`，只是渲染路径被分流到了普通 chat renderer。这个现状意味着本次改动不需要引入新的 runtime 协议，也不需要新增跨层消息类型，只需要在 TUI 本地 view-state 中补齐 thinking history 的专属视觉语义。

约束很明确：

- 不修改 runtime `AgentEvent` 结构；
- 不改变 thinking/tool/assistant 的 chronology 合同；
- 不影响 waiting-only `Thinking ...` 占位的现有行为；
- 不新增外部依赖，只在现有 Rich/Textual 渲染层内完成样式分流。

## Goals / Non-Goals

**Goals:**

- 让真实 thinking 历史消息使用专属前缀 `Assistant (Thinking) > `。
- 让真实 thinking 历史消息整体比正式 assistant 回复更暗，形成明确但可读的视觉降权。
- 保留当前 waiting-only `Thinking ...` 与真实 thinking 历史的语义边界。
- 保留当前 chronology：thinking 历史、tool 活动、最终 assistant 回复的顺序不得因视觉调整被破坏。
- 让测试能稳定覆盖前缀切换和渲染路径分流。

**Non-Goals:**

- 不重新设计整个 TUI 视觉语言。
- 不把 thinking 历史改成新的 runtime 消息类型或新的 timeline 协议。
- 不改变 tool 渲染方式、system 消息样式或正式 assistant 回复文案。
- 不在本次处理 `/stop`、滚动跟随或其他已有无关测试失败。

## Decisions

### 1. 真实 thinking 历史继续保留 `kind == "thinking"`，只调整渲染语义

决策：真实 runtime thinking 在 view-state 中继续作为 `thinking` 条目存在，不转换为 `assistant` 条目；通过 metadata 和专属 renderer 区分“waiting-only”与“history-thinking”。

原因：

- 这保留了“它本质上是 thinking 历史，不是最终答复”的语义边界；
- 可以直接复用现有 `_is_waiting_thinking_item` 分流逻辑；
- 避免为了视觉目标去伪造消息类型，降低后续维护歧义。

备选方案：

- 在升级为历史时直接把 `kind` 改成 `assistant`。  
  不采用，因为这样会抹平 thinking 与最终答复的状态边界，未来再做 thinking 专属行为会更绕。

### 2. 为真实 thinking 历史新增专属 renderer，而不是复用普通 chat renderer

决策：waiting-only thinking 继续走当前 `_render_thinking_item_renderable`；真实 thinking 历史改走一个新的 thinking-history renderer，单独控制前缀和正文颜色。

原因：

- 需求不仅改文案，还改前缀颜色和正文颜色；
- 普通 `_render_chat_message_renderable` 只有一套 chat 样式，不适合继续承载 thinking 历史的降权视觉；
- 独立 renderer 更容易测试，也更符合“一个渲染路径只服务一种视觉语义”的原则。

备选方案：

- 在通用 chat renderer 中根据 metadata 条件分支。  
  不采用，因为会把普通 assistant 与 thinking history 的样式判断耦合在一个函数里，增加局部复杂度。

### 3. 在 thinking 历史升级点一次性写入专属标题 metadata

决策：当 runtime thinking 首次升级为真实历史时，就把标题赋值为 `Assistant (Thinking) > `，而不是在渲染时动态拼接。

原因：

- 现有 `_TimelineItem` 已经把 `title` 作为展示面的直接字段使用；
- 文本渲染和纯文本断言都可直接读取统一值，减少不同输出面不一致的风险；
- 不需要额外的 title 计算函数或新的消息结构。

备选方案：

- 保持 title 为空，在 renderer 中拼接 thinking 前缀。  
  不采用，因为测试中的 `_render_timeline_text()` 和 Rich renderable 都会分叉处理，容易让字符串输出与富文本输出不一致。

### 4. 颜色只做降权，不做低对比度到难读

决策：thinking 历史使用比正式 assistant 更暗的绿色前缀和更暗的浅灰正文，但仍保持在深色背景上的稳定可读性。

原因：

- thinking 历史是“次级重点”，不是“隐藏信息”；
- 用户仍然需要快速扫描 reasoning 文本，因此不能把对比度压得过低；
- 这符合当前 TUI 以终端可读性优先的基调。

备选方案：

- 仅改前缀，不改正文。  
  不采用，因为这样整条消息仍会在视觉上过于接近正式 assistant 回复。

## Risks / Trade-offs

- [Risk] thinking 历史颜色过暗，影响阅读效率。  
  → Mitigation：优先选择“明显降权但仍可读”的颜色，保持正文对比度在深色背景下可接受。

- [Risk] 真实 thinking 历史与 waiting-only thinking 的分流条件被写乱。  
  → Mitigation：继续以现有 `ephemeral` / waiting 判定为唯一分叉条件，不新增第二套并行状态。

- [Risk] 测试只验证前缀文本，没有验证富文本样式。  
  → Mitigation：至少补一条 renderable 级别的样式测试，避免只有字符串断言而漏掉颜色回归。

- [Risk] 后续如果要继续细化 thinking 历史样式，通用 chat 样式与 thinking 样式可能再次分叉。  
  → Mitigation：现在就把 thinking history renderer 独立出来，为后续微调保留明确边界。

## Migration Plan

1. 调整 thinking 历史升级点，把标题改成 `Assistant (Thinking) > `，并显式标记为真实历史而非 waiting。
2. 为 thinking 历史新增专属渲染路径和样式常量，保留 waiting-only thinking 的现有渲染。
3. 更新 timeline 文本输出和测试断言，使真实 thinking 历史前缀与正式 assistant 回复明确区分。
4. 运行聚焦 TUI 测试，确认 waiting-only、thinking history、assistant chronology 三类路径都通过。

回滚策略：

- 本次只改 TUI 本地渲染和测试，不涉及数据迁移；
- 若视觉效果不理想，可直接回滚 thinking history 标题和 renderer 分流，恢复当前普通 assistant 样式。

## Open Questions

- 当前无阻塞性开放问题。
- 实现阶段若发现仅靠颜色仍不足以区分 thinking 历史，可再评估是否增加轻量的字重或额外空白策略，但这不属于本次最小闭环。
