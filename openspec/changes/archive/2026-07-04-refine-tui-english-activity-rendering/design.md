## Context

SmartIPO 当前的 TUI 主渲染职责集中在 `src/tui/app.py`：Header、状态摘要、主 timeline、queue tray、本地 slash 命令提示和活动计时都由这一层直接消费 `easyharness.AgentEvent` 并转换为可见文本。此前几轮变更已经完成了聊天式前缀、排队托盘、终端原生化表面和基本主题色，因此这次调整不需要触碰 agent runtime 或 tool contract，核心问题已经收敛为“如何让同一条消息时间线在语言、品牌和活动结构上表达得更稳定”。

当前主要不一致点有四类：

- Header 仍沿用 Textual 默认标题，品牌识别不完整；
- 固定 UI 文案仍中英混杂，无法建立“UI 是英文、agent 内容可中文”的稳定边界；
- thinking 既是临时等待态，又会以历史项残留在 timeline 中，容易污染主会话记录；
- tool activity 仍然是纯文本拼接格式，无法与聊天前缀和计时层级形成一致的视觉语法。

这轮设计的目标不是做一次更炫的皮肤，而是建立一套以后还能继续扩展的展示协议：用户一眼就能分辨“这是系统 UI 元素、这是 assistant 内容、这是工具活动、这是时间消耗信息”。

## Goals / Non-Goals

**Goals:**

- 把 TUI 的所有固定 UI 元素统一成英文，建立稳定的语言边界。
- 让 Header 明确体现 SmartIPO 品牌，而不是框架默认标题。
- 让 thinking 成为真正的临时动态态，只在 assistant 真正输出前占位。
- 让 tool activity 具备统一且可扫读的主行结构：`计时 · { Tool <name> · <status> }`。
- 为聊天前缀、thinking、tool 主行和计时建立分层着色，减少视觉混淆。
- 保持实现改动局限在 `src/tui/app.py` 和测试层，不扩散到底层 runtime。

**Non-Goals:**

- 不改 `easyharness.AgentEvent` 结构或事件来源。
- 不改 agent/tool 执行逻辑、排队语义或滚动策略。
- 不把 assistant 正文强制英文化；agent 输出可以继续使用中文。
- 不引入新的主题系统、配置文件或跨 UI 共享展示协议。

## Decisions

### 1. 继续把展示语义收敛在 TUI 层，而不是下沉到 runtime

决策：所有这轮变化都留在 `src/tui/app.py` 渲染层完成，包括 Header 标题、固定 UI 文案、thinking 可见性和 tool 主行结构。

原因：

- 这些变化本质上都是展示偏好，不是运行时事实；
- 当前项目已经明确放弃自研跨 UI timeline 协议，继续把这类偏好留在 TUI 层，符合现有架构方向；
- 这样可以把修改范围限制在单文件和对应测试里，降低回归面。

备选方案：

- 把 “thinking 是否保留历史”“tool 主行文本格式”等再抽成共享 view-model。  
  不采用，因为这会重新引入一个展示层中间抽象，和仓库当前“直接消费 `AgentEvent`”的方向冲突。

### 2. 把固定 UI 英文化，但不改 agent 正文语言

决策：将 Header、状态摘要、queue tray、输入 placeholder、本地 slash 命令反馈和固定活动标签统一成英文；assistant 或工具返回的正文内容保持原样。

原因：

- 这能建立一条清晰边界：UI 是系统外壳，agent 内容是业务表达；
- 避免把模型生成文本也强行英文化，造成语义失真或不必要翻译；
- 对测试也更稳定，因为固定 UI 文案来自本地代码，可控性更高。

备选方案：

- 全界面彻底英文化，包括 agent 默认欢迎词、系统提示正文甚至工具结果文本。  
  不采用，因为这些文本未必都属于 UI 元素，有些是 agent 内容，强制改语言会越权。

### 3. 把 thinking 定义为临时动态态，而不是历史消息

决策：本地 provisional thinking 仅在等待 assistant 首次真实输出时可见；一旦 assistant 收到 `started` 或首个 `delta`，该 thinking 条目从可见 timeline 中消失，不再以 completed 项残留。

原因：

- thinking 的职责是“填补等待空窗”，不是生成可复盘的历史语义；
- 用户真正关心的是 assistant 回答和 tool activity，保留 thinking 历史只会增加噪音；
- 这符合你要求的 “Thinking ... 消失在 timeline 中，然后立刻看到 `Assistant >`”。

备选方案：

- 继续保留 completed thinking，但把它换成英文。  
  不采用，因为这只改了语言，没有解决临时态污染历史的问题。

- 完全移除 thinking，只显示 assistant。  
  不采用，因为在首个真实输出前会出现静默空窗，交互反馈变差。

### 4. 统一所有活动主语法为 `计时 · 动作`

决策：所有带活动态的条目都统一采用 `duration · action` 结构。thinking 和 tool 主行强制使用该格式；普通聊天消息保持前缀 + 正文，不强行附带计时。

原因：

- 这让用户可以快速建立阅读预期：看见 `0.96s ·` 就知道这是活动态；
- 保留聊天消息的自然阅读流，不把会话内容全部日志化；
- 可以为计时单独着色，建立“辅助信息”层级。

备选方案：

- 给所有消息都加上时间或耗时。  
  不采用，因为会让聊天区重新退化成日志视图。

### 5. 工具主行使用 `{ Tool ... }` 作为独立语法块

决策：tool activity 的第一行统一渲染为：

`0.96s · { Tool search_fmp_ipo · Running }`

工具的 `Call`、`Summary`、`Result`、`Error` 作为后续下挂行展示，不放进花括号。

原因：

- `{ }` 能显式把工具活动与 `User >` / `Assistant >` 区分开，形成第三种可见语法；
- 把主行限定在花括号内，能避免工具名、状态和附加结果混成一整段自然语言；
- 下挂行继续保留结果概要，既不损失信息，也不破坏主行扫读性。

备选方案：

- 使用 `Tool > ` 前缀与聊天前缀保持完全一致。  
  不采用，因为工具活动在语义上不是“说话者”，而是系统动作；继续用 `>` 会和聊天角色混淆。

- 把工具结果也全部包进 `{ }`。  
  不采用，因为长结果会破坏主行可读性，括号块会失控膨胀。

### 6. 使用 Rich 分段渲染，而不是继续依赖整行纯文本样式

决策：继续保留 `_render_timeline_text()` 作为稳定断言接口，但正式渲染走 Rich 分段对象，为计时、前缀、正文和 tool 语法块分别着色。

原因：

- 你要求 tool prefix、thinking、计时都使用不同层级颜色，这无法只靠整行字符串完成；
- 现有聊天前缀已经是 Rich renderable，延续这一方向改动成本最低；
- 文本版本继续存在，可防止测试被内部 Rich 结构绑定死。

备选方案：

- 完全把测试改成断言 Rich 对象内部样式结构。  
  不采用，因为测试会变得脆弱，和当前仓库偏好的“稳定文本断言”不一致。

## Risks / Trade-offs

- [Risk] 把固定 UI 文案全部改成英文后，现有测试和局部截图预期会大面积变化。 → Mitigation：把断言收敛到稳定的英文 UI 文案和关键活动格式，避免继续依赖旧中文串。
- [Risk] thinking 从历史中消失后，若 assistant 首包迟到或异常中断，可能出现短暂状态切换理解成本。 → Mitigation：仅在 assistant 已真实开始输出后才隐藏 thinking；异常路径仍保留系统失败消息。
- [Risk] Header 的 Textual 组件样式选择器可能受框架默认主题影响，首次实现时存在选择器试探成本。 → Mitigation：把 Header 改动局限在 CSS 层最小范围，并用最小测试或手工预览确认。
- [Risk] tool 主行改为 `{ Tool ... }` 后，旧的文本快照与人工阅读习惯需要重新适应。 → Mitigation：保留 `Summary` / `Result` 下挂行，不让主行承载过多信息。

## Migration Plan

1. 先更新 `src/tui/app.py` 中的固定 UI 文案、Header 标题和 Header 样式。
2. 再调整 thinking 的渲染与可见性规则，确保它从“历史条目”退化为“临时占位”。
3. 然后重构 tool activity 的主行 renderable 和下挂结果行英文标签。
4. 最后统一修正 `test/test_tui_app.py` 的文案与格式断言。

回滚策略：

- 这是一轮纯 TUI 层改动，不涉及数据迁移或 runtime 协议升级；
- 若上线后阅读体验不理想，可通过回滚对应提交恢复旧渲染；
- 因为没有 schema 或数据面改动，不存在额外回滚脚本需求。

## Open Questions

- 当前无阻塞性开放问题。
- 若实现阶段发现 Textual Header 需要额外 subclass 才能稳定控制标题或背景色，再在实现中做最小例外说明，但默认优先尝试保持现有 `Header()` 组件。
