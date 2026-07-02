## Context

当前项目内工具通过 `build_strands_tool()` 包装为 Strands tools。实现方式是把统一的 `_call(**kwargs)` 交给 `strands.tool(...)`，再用 `inputSchema=tool_spec.input_schema` 覆盖工具 schema。

问题在于 Strands decorator 的实际校验逻辑仍然依赖函数签名生成内部 Pydantic 模型，而不是完全依赖 override 后的 `inputSchema`。对于 `_call(**kwargs)` 这种签名，内部校验模型会把 `kwargs` 当成一个显式字段，导致 provider 发来的正常工具参数在进入本地 handler 之前就被校验拦截，报出类似：

- `1 validation error for _callTool`
- `kwargs`
- `Field required`

这会带来两个直接后果：

1. fileglide 这类 schema-driven 工具在真实工作流中基本不可用。
2. 因为失败发生在本地 handler 之前，当前 runtime 不会发出 `tool_started/tool_failed`，上层 TUI/WebUI 也看不到真实工具 timeline。

同时，当前 TUI 默认暴露完整 fileglide 工具集和生图工具，总数较多，会增加模型选错工具和填错参数的概率。

约束：

- 不考虑后向兼容。
- 不重写整个 agent/runtime 架构。
- 不引入新的依赖。
- 保留现有 `ToolSpec` / `ToolContext` / `ToolResult` 体系。

## Goals / Non-Goals

**Goals:**

- 修复 schema-driven 工具无法真实执行的问题。
- 让 Strands 直接消费项目内 `ToolSpec.input_schema` 与 provider 的 `tool_use["input"]`。
- 让 provider 侧工具尝试、参数校验失败、本地执行失败都能统一发出活动事件。
- 收缩 TUI 默认工具暴露集合，优先保障高频只读任务的成功率。
- 用测试锁住真实 fileglide 工具可执行和失败可观测性。

**Non-Goals:**

- 不改 fileglide facade 本身。
- 不实现 WebUI。
- 不保留旧的 decorator 包装路径。
- 不把所有工具都做成单独手写 wrapper。

## Decisions

### 1. 放弃 `tool(_call, inputSchema=...)`，改用低层 `PythonAgentTool`

新桥接层不再依赖 Strands decorator 的函数签名推断，而是直接构造低层 `PythonAgentTool`，让执行入口拿到原始 `tool_use`，再从 `tool_use["input"]` 中取参数调用项目内 `tool_spec.handler(context, **params)`。

原因：

- 项目工具本来就是 schema-driven，不需要再让 Strands 根据 Python 签名生成第二套输入模型。
- `PythonAgentTool` 更贴近现有 `ToolSpec` 结构，改动集中且稳定。

备选方案：

- 动态生成与 schema 一致的 Python 函数签名，再继续走 decorator。放弃，原因是实现更绕，维护成本更高，而且仍然把项目工具耦合到 decorator 规则。

### 2. 工具桥接层自己负责工具结果格式化

桥接层直接把本地 `ToolResult` 转成 Strands 期望的 tool result 结构，并在本地 handler 成功或失败时发出统一 `LoopEvent`。

原因：

- 这样工具执行语义完全由项目 runtime 控制，不再依赖 decorator 的隐式错误包装。
- 更容易在失败时同时保留原始错误文本和 timeline 事件。

### 3. 新增 provider-side tool attempt / validation failure 事件

runtime callback bridge 需要在 provider 发出 `toolUse` intent 时记录一次工具尝试事件；若随后没有进入本地 handler，或 provider/SDK 返回了 validation failure，需要补一条专门的失败活动事件。

原因：

- 用户需要看到“工具被尝试了但在执行前失败”。
- 这类失败不会落到当前 `tool_failed` 事件里，必须新增覆盖。

备选方案：

- 继续只记录进入本地 handler 后的事件。放弃，原因是这会让一整类真实失败在 UI 中完全不可见。

### 4. TUI 默认工具集收缩为高频只读集合

默认 workbench 只暴露最小高频只读集合，例如：

- `path.list`
- `file.list`
- `text.read`
- `text.grep`

必要时再逐步开放写入类和 batch 类工具。

原因：

- 先把读路径打通，比“一口气开放 24 个工具”更可靠。
- 工具越多，模型越容易选错和填错。

备选方案：

- 继续默认暴露全部工具。放弃，原因是当前目标是稳定可用，不是功能面最大化。

## Risks / Trade-offs

- [风险] 更换工具桥接实现会触发现有 runtime 与测试的大面积调整。  
  → Mitigation: 保持 `ToolSpec` / `ToolResult` / `build_tool_context()` 不变，只替换 Strands 接入边界。

- [风险] provider-side 尝试事件可能与真正本地执行事件重复。  
  → Mitigation: 明确区分 attempt、started、completed、failed 的语义，避免同名复用。

- [风险] 收缩 TUI 默认工具集会让部分高级操作暂时不可直接触发。  
  → Mitigation: 仅影响默认暴露集合，不删除工具注册表中的真实工具，后续可按需扩展。

## Migration Plan

1. 替换 `build_strands_tool()` 的实现，去掉 decorator 路径。
2. 调整 callback bridge 和事件定义，增加 provider-side 工具尝试/失败活动。
3. 调整 timeline reducer 与 TUI 渲染，展示新的活动事件。
4. 收缩 TUI 默认工具暴露集合。
5. 更新并运行针对真实工具执行与失败可见性的测试。

回滚策略：整轮回滚该 change；不维护 decorator 兼容分支。

## Open Questions

- provider-side 尝试事件是否单独命名为 `tool_attempt_started/tool_attempt_failed`，还是归入现有 `tool_*` 族并增加阶段字段。实现时优先选最直接、最不含糊的命名。
- TUI 默认只读工具集合的最终名单可以在实现时按最小闭环微调，但原则是不暴露大而全的工具面。
