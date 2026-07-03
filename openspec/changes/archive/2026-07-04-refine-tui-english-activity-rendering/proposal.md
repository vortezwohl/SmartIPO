## Why

当前 SmartIPO 的 TUI 已经具备基本聊天、排队、工具活动与流式输出能力，但界面语言和活动表达仍然混杂了中文 UI 文案、默认框架标题、残留的 `thinking` 占位和不统一的工具活动结构。这会让界面在“品牌识别”“活动可扫读性”“中英文边界”和后续视觉扩展上都持续积累负担。

现在推进这轮变更的时机合适，因为相关聊天渲染、排队托盘和终端原生化调整已经完成，主消息区的渲染职责已经集中在 `src/tui/app.py`。此时补齐英文 UI 语义、品牌化 Header 和统一活动格式，可以在不扩散到底层 runtime 的前提下，把 TUI 收敛成一套更稳定、可演进的展示约定。

## What Changes

- 将 Textual 顶部 Header 的默认应用标题替换为 `SmartIPO`，并把 Header 背景收敛到更深的绿色品牌色。
- 把所有固定 UI 元素统一改为英文，包括状态摘要、排队托盘、输入提示、本地 slash 命令反馈和时间线中的固定动作标签。
- 将运行中的思考占位统一为 `Thinking ...` 结构，并采用 `计时 · 动作` 的显示模式。
- 调整 thinking 条目的可见性规则：它只作为等待真实输出前的临时动态态存在；一旦 assistant 开始真正输出，旧的 thinking 条目必须从主 timeline 中消失，而不是作为完成历史残留。
- 将工具活动从当前的纯文本行改为统一的英文活动格式，主工具行采用 `计时 · { Tool <name> · <status> }` 结构，工具结果概要继续以下挂行展示。
- 为聊天前缀、thinking、tool 主行与计时分别建立更清晰的视觉层级，避免所有活动都挤在同一种白字或同一种浅绿色里。
- **BREAKING** 调整 TUI 固定文案和 timeline 文本快照格式；依赖旧中文 UI 文案或旧工具行文本结构的测试断言将需要同步更新。

## Capabilities

### New Capabilities
- `tui-english-activity-rendering`: 定义 SmartIPO TUI 的英文 UI 元素、品牌化 Header、临时 thinking 生命周期以及统一的 tool activity 主行格式。

### Modified Capabilities
- 无

## Impact

- 主要影响代码位于 `src/tui/app.py` 的 Header、状态栏、timeline renderable、queue tray 和本地命令提示链路。
- 需要同步更新 `test/test_tui_app.py` 中与 thinking、tool activity、系统提示、placeholder 和标题文案相关的断言。
- 不影响 `easyharness.AgentEvent` 事件来源、agent/tool runtime 协议和业务工具实现。
