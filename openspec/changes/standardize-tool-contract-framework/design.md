## Context

当前 `ToolSpec` 仍然是偏薄的定义对象，只能直接承载自由文本 description、schema 和 handler，缺少结构化文档、统一结果合同、统一错误合同和可复用 policy 插槽。结果是：

- `fileglide` 已经在局部实现里承担了 description builder、path contract、result rendering、error mapping 等框架职责；
- 其他 tool 仍然停留在“单文件手写 description + metadata 约定”的状态；
- runtime 已经开始统一 tool result 序列化，但可消费的 contract 还没有正式建模；
- TUI 中仍然存在默认 system prompt、默认 tool set、默认 agent 组装，这些属于应用装配责任，不是纯 UI 责任。

这次变更不是再修一个工具，而是把已验证有效的经验提炼为最小统一框架，形成后续所有 tool 的标准入口。

约束：

- 不引入新的外部依赖；
- 不重建现有 Agent / Strands 主流程；
- 保持渐进迁移，避免一次性重写所有 tool；
- provider-facing description、model-facing result/error contract 必须使用英文；
- UI 可以保留中文展示和本地化，但不得承担 tool protocol 解释责任。

相关角色：

- `src/tool/*`: concrete tool 与 tool framework
- `src/core/strands_runtime.py`: runtime adapter
- `src/core/timeline.py`: cross-UI timeline semantics
- `src/tui/app.py` 与 future WebUI: presentation layer
- application composition layer: 默认 prompt、默认 tool set、默认 session/agent assembly

## Goals / Non-Goals

**Goals:**

- 为所有 tool 建立统一、可校验、可生成的结构化 definition contract。
- 为所有 tool 建立统一的 result/error execution contract，明确模型通道、UI 通道和原始诊断通道。
- 把可复用策略从 concrete tool 中抽离出来，形成公共 policy / formatter / validator 机制。
- 把 TUI、WebUI 等 UI 层与 core/runtime/tool framework 的责任边界明确切开。
- 提供一条渐进迁移路径，让现有 fileglide 和其他 tool 能逐步进入同一框架。

**Non-Goals:**

- 不引入插件市场、动态远程加载、权限引擎等大型平台能力。
- 不在这一轮重写 fileglide facade 或 strands provider 适配层的底层实现。
- 不要求所有 legacy tool 在一个提交中全部迁移完成。
- 不把 UI 本地化文本强行统一为英文；英文要求只约束 tool contract 层。

## Decisions

### 1. 引入结构化 Tool Definition Contract，而不是继续手写自由文本

框架层新增结构化定义对象，至少覆盖：

- `ToolIdentity`: name / display_name / kind
- `ToolDoc`: purpose / when_to_use / parameters / returns / common_failures / optional notes
- `ToolPolicies`: path policy / traversal policy / result formatter / error mapper / mutation safety policy
- `ToolSpec`: 组合 identity、doc、schema、handler、policies

provider-facing description 由统一 renderer 从 `ToolDoc` 生成，禁止 concrete tool 直接手写长 description 字符串。

原因：

- 这能把 `_tool_description(...)` 从 fileglide 私有 helper 升级为公共 contract 标准；
- 文档结构可校验，能避免 schema 字段、returns 字段和错误说明互相漂移；
- 后续可以复用到 CLI、provider adapter、文档生成和测试断言。

备选方案：

- 保留 `description: str`，只把 `_tool_description` 挪成公共函数。放弃，原因是仍然不可校验，只是把自由文本拼接器搬家。
- 把完整 tool 文档写进 system prompt。放弃，原因是 prompt 不是工具定义容器，责任边界错误。

### 2. 引入统一 Tool Result / Tool Error Contract，分离模型正文、UI 预览和原始诊断

框架层统一定义：

- `ToolResult.data`: 原始结构化数据
- `ToolResult.model_text`: 面向模型的英文正文
- `ToolResult.preview_text`: 面向 timeline / UI 的短摘要
- `ToolResult.detail_text`: 面向 UI 的可折叠详细文本
- `ToolResult.annotations`: 截断、计数、warning 等元信息

以及：

- `ToolError.code`: 稳定英文错误码
- `ToolError.model_message`: 面向模型的英文错误文本
- `ToolError.retry_hint`: 面向模型的英文恢复提示
- `ToolError.raw_error`: 原始异常诊断
- `ToolError.retryable`: 是否可重试

runtime 只消费这套统一合同，不再依赖具体 tool 约定临时 metadata key。

原因：

- 现有 `summary` 与 `metadata["model_text"]` 已经暴露出语义混叠问题；
- 统一合同后，runtime 可以稳定序列化，UI 可以稳定渲染，tool 可以稳定测试。

备选方案：

- 继续允许 tool 自由往 metadata 塞字段。放弃，原因是长期必然变成不可维护的隐式协议。

### 3. 可复用逻辑采用 Strategy + Template Method，不走继承大树

框架执行骨架统一为：

`normalize_input -> validate_contract -> execute_handler -> map_result/map_error -> emit runtime payload`

其中变化点以 strategy 注入：

- `ScopedPathPolicy`
- `ReadonlyTraversalPolicy`
- `ToolResultFormatter`
- `ToolErrorMapper`
- `MutationSafetyPolicy`

具体 tool 只声明自己用哪些策略，不自己重复拼执行样板。

原因：

- 当前 fileglide 里的路径规范化、结果渲染、错误包装已经证明这些是横切关注点；
- strategy 比继承层次更容易局部复用，也更符合未来不同 tool 的组合需求。

备选方案：

- 为每类 tool 建一个抽象基类，再由子类 override。放弃，原因是会很快形成脆弱继承树。
- 保持 helper 函数散落在各个 tool 文件里。放弃，原因是规范无法集中治理。

### 4. 将 UI、Core、Composition 三层职责显式分离

边界定义如下：

- Tool framework / core runtime 负责：
  - tool contract
  - result/error contract
  - policy/formatter/validator
  - provider adapter
  - runtime event schema
- Application composition 负责：
  - 默认 system prompt
  - 默认 tool sets / tool presets
  - 默认 model 选择
  - session / agent 组装
- UI 层负责：
  - 输入输出交互
  - timeline 呈现
  - 本地化文案
  - 折叠、动画、滚动、状态展示

因此，`src/tui/app.py` 不应长期保有默认 agent 组装函数；TUI 和 future WebUI 都应接收一个已经装配好的 session/agent 或 composition factory。

原因：

- 这能避免 UI 越界定义工具协议和运行时默认行为；
- 同时保留 `src/core/timeline.py` 作为跨 UI 共享语义层，这是合理的，不需要下沉到 UI。

备选方案：

- 把所有默认值继续留在 TUI，WebUI 再复制一份。放弃，原因是重复和漂移不可避免。

### 5. 增加 Tool Catalog Validator，把规范从“建议”变成“门禁”

在 registry build 或启动阶段增加校验，至少覆盖：

- provider-facing description 可由结构化 doc 成功生成；
- schema 中每个公开参数都能在 `ToolDoc.parameters` 中找到说明；
- result / error contract 字段满足框架要求；
- contract 层字段与错误码使用英文；
- tool name 唯一且 provider name 映射无冲突；
- UI-only metadata 不得泄漏进 provider-facing contract。

原因：

- 没有 validator，这套框架最终还是会退化回“约定靠自觉”。

备选方案：

- 只写文档，不做校验。放弃，原因是新 tool 很快会破坏规范。

### 6. 采用渐进迁移，而不是一次性重构所有 tool

迁移顺序：

1. 引入新 contract 对象与 renderer / validator；
2. 让 runtime 优先兼容新旧结果对象；
3. 迁移 fileglide 为首个标准化 concrete tool；
4. 迁移 Seedream 等其他 tool；
5. 将默认 composition 从 TUI 抽离；
6. 收紧 legacy freeform path，最终只保留兼容 shim。

原因：

- 这是跨 core/tool/UI 的变更，一次性切换风险不必要地高；
- fileglide 已经是最佳样板，先迁它最省。

## Risks / Trade-offs

- [Risk] contract 对象变多，初看比当前 `ToolSpec` 更重  
  → Mitigation: 保持对象数量最小，只抽真正跨 tool 复用的部分，不引入插件系统或抽象工厂大全。

- [Risk] result/error contract 迁移期间出现 runtime 兼容层复杂度  
  → Mitigation: 先做向后兼容适配，再逐个 tool 迁移，最后删除 shim。

- [Risk] “English-only contract” 规则难以完全自动判断自然语言质量  
  → Mitigation: validator 先校验结构、字段和禁用中文字符的硬规则，语义质量通过测试和 review 补齐。

- [Risk] 把默认 agent 组装从 TUI 挪走后，启动路径会短期变复杂  
  → Mitigation: 新增单一 composition entrypoint，UI 只做依赖注入，不做多套装配逻辑。

- [Risk] 未来新 tool 类别可能并不需要 scoped path policy  
  → Mitigation: policy 采用可选 strategy，而不是强制所有 tool 继承同一文件系统模型。

## Migration Plan

1. 新增框架层 contract/doc/policy/result/error/validator 模块。
2. 调整 `ToolSpec`、`ToolResult` 及 runtime adapter，使其支持结构化 contract。
3. 抽离 fileglide 中可复用的 description builder、result formatter、error mapper、path policy。
4. 迁移 fileglide tools 到新 contract，保留必要兼容层。
5. 迁移 Seedream 等其他 tool，使其不再手写自由文本 description 和临时 metadata 约定。
6. 抽离默认 system prompt、tool set、agent factory 到 composition 层。
7. 让 TUI 接入 composition 层；future WebUI 直接复用同一装配入口。
8. 补充 validator、runtime、tool migration、UI boundary 相关测试。

回滚策略：

- 若新 contract 导致 runtime 不稳定，可先保留 runtime 兼容层并暂时仅迁移 fileglide；
- 若 composition 拆分影响 UI 启动，可先保留旧入口作为薄兼容包装，待 WebUI 接入后再删除。

## Open Questions

- 英文 contract 的校验是否只做“禁用中文字符 + 必填结构”即可，还是需要更严格的 lint 规则。
- `ToolResult.detail_text` 是否始终由 tool 提供，还是允许 runtime 从 `data` 兜底生成。
- application composition 层最终命名应落在 `src/app/`、`src/composition/` 还是 `src/runtime_profiles/`，需要结合现有目录再收敛。
