## Context

当前 `src/tui/app.py` 已经具备三项基础能力：串行 turn 队列、独立 queue tray、终端原生底板。剩余问题集中在最后一层交互收口：

- queue tray 仍以居中泡泡渲染，视觉存在感过强；
- timeline 仍以纯字符串整体渲染，难以只给 `User >` / `Assistant >` 前缀着色；
- 输入框只支持“提交 prompt”，不支持面向用户的 slash 命令；
- 当前 worker 生命周期只有“开始 / 自然结束 / 失败”，缺少“用户主动中断”的 UI 闭环。

约束也很明确：不应改动 `src/agent.py` 的对外协议，不应新增第三方依赖，不应为几个简单命令引入额外命令总线或配置层。

## Goals / Non-Goals

**Goals:**
- 让 queue tray 改成更扁平、更轻的排队提示，不再给每条待处理消息单独加泡泡边框。
- 让 timeline 使用带样式的 `User > ` / `Assistant > ` 前缀，同时保留现有文本渲染接口供测试断言。
- 增加 `/stop`、`/new`、`/help` 的最小命令集，并把命令提示写进 placeholder。
- 支持 Tab 对闭集命令进行自动补全，底层复用 `vortezwohl.nlp.LevenshteinDistance`。
- 支持用户主动中断当前回复，并确保半截 assistant 输出保留在历史中，旧事件不会污染后续状态。

**Non-Goals:**
- 不修改 EasyHarness agent 的 `stream()` / `reset()` 协议。
- 不实现命令下拉菜单、命令历史、参数解析器或插件化命令系统。
- 不重写 Textual 的滚动机制，只保证 timeline 继续使用原生 `VerticalScroll` 并围绕当前行为补验证。

## Decisions

### 1. 保留单文件 TUI 状态机，不拆命令子模块

命令入口直接放在 `on_input_submitted()` 前置分发：以 `/` 开头的输入先命令解析，普通文本仍走现有 `_enqueue_turn()`。  
这样改动只落在 `src/tui/app.py`，不会为了 3 个命令引入新的命令 registry、parser 或配置文件。

备选方案：
- 新建 `src/tui/commands.py`：结构更“整洁”，但当前命令量太小，属于过度抽象。

### 2. 中断优先复用 Textual worker 取消，而不是扩展 agent 协议

当前 `_run_turn_worker()` 已经由 `@work(thread=True)` 驱动。设计上新增 `_active_worker` 引用，并在 `/stop` 时调用 `Worker.cancel()`；UI 层同步执行本地收口：结束运行中的 thinking / assistant 条目、保留已有 assistant 半截文本、把当前 turn 标记为已中断或已结束，然后允许下一条排队 turn 启动。

旧轮次后续若仍有迟到事件，到达 `_apply_agent_event_for_turn()` 时会因 turn 不再活跃而被丢弃。这样可以在不改 agent 的情况下满足“中断立即生效于 UI”的核心诉求。

备选方案：
- 给 `src/agent.py` 增加显式 `cancel()` 协议：理论上更彻底，但会扩大变更面，也会把 TUI 层需求倒灌到 agent 组合层，不值当。

### 3. timeline 改为 Rich renderable，保留文本版本供测试

当前 `_render_timeline()` 直接 `update(Text(self._render_timeline_text()))`，无法只给前缀上色。  
改法是新增 `_render_timeline_renderable()`，返回 `Group` / `Text` 组合；`_render_timeline_text()` 继续存在，仅作为无样式串行化结果给测试使用。

这样前缀颜色、工具多行说明和正文留白都能继续精细控制，同时不打破现有测试习惯。

备选方案：
- 在纯字符串里嵌 ANSI 或 Rich markup：测试和渲染会互相污染，不稳。

### 4. queue tray 只保留容器级弱强调，消息本身改为纯文本居中

移除单条排队消息的 `Panel.fit(...)`，改为一组轻量 `Text` 行或一个 `Group`。queue tray 作为整体保留细边框或轻标题即可，避免形成“大框里套小框”的视觉噪音。

备选方案：
- 完全删除 queue tray 外框：更极简，但当前界面中输入区和 timeline 之间仍需要一个弱分组边界，否则排队状态不够可发现。

### 5. 命令补全只做闭集最佳匹配

命令集合固定为 `/stop`、`/new`、`/help`。Tab 补全对当前输入做一次 `LevenshteinDistance.rank()`，只取第一名，且仅在距离足够近或明确以前缀 `/` 开头时替换输入框值。  
这能满足易用性，同时避免做候选列表、分页和复杂交互。

备选方案：
- 下拉候选菜单：更完整，但对当前需求过重。

## Risks / Trade-offs

- [线程 worker 取消后底层流未必立刻停止] → UI 必须先本地收口，并继续依赖 turn_id 过滤迟到事件，不能把“线程已 cancel”误当成“模型流立刻停止”。
- [timeline 从纯文本改为 renderable 后测试可能脆弱] → 保留 `_render_timeline_text()` 和 `_render_queue_tray_text()` 作为稳定断言接口，测试优先断言语义而不是样式对象内部结构。
- [Tab 模糊补全可能误选] → 只对闭集命令启用，并设置“输入必须以 `/` 开头”的保护条件；模糊度不够时宁可不补全。
- [滚轮问题可能其实来自终端环境] → 先保持 Textual 原生 `VerticalScroll`，通过测试与手测验证当前链路；只有确认当前 app 层吞事件时才加显式处理。
