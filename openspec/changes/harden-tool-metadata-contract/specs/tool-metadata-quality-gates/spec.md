## ADDED Requirements

### Requirement: 默认工具面必须接受 runtime 元数据校验
系统 MUST 在 runtime 层校验默认工具面最终暴露给模型的 `tool_spec`，而不是只检查源码中的装饰器参数。校验对象 MUST 是 EasyHarness 实际构造出的工具定义。

#### Scenario: 构造默认工具集合
- **WHEN** 调用方执行 `build_default_tools(...)`
- **THEN** 系统 MUST 能读取默认工具集合中每个工具最终生成的 `tool_spec`
- **AND** 元数据质量校验 MUST 基于这个 runtime 结果进行

### Requirement: 项目自有工具必须通过最小元数据质量门禁
系统 MUST 为项目自有工具建立最小元数据质量门禁，至少校验关键字段存在、描述不为空、关键相邻工具具备可区分文案，以及高风险模板化退化不会悄悄混入默认工具面。

#### Scenario: FMP 工具新增或改写后进入默认工具面
- **WHEN** 开发者新增或修改某个 FMP 工具并将其并入默认工具集合
- **THEN** 系统 MUST 能通过测试或等价门禁检测该工具的元数据是否满足最低质量标准
- **AND** 若文案退化为不可区分的模板，门禁 MUST 显式失败

### Requirement: 外部工具兼容性校验不得演变为重包装要求
系统 MUST 允许对外部官方工具做存在性和兼容性审查，但 MUST NOT 为了统一项目文案风格而强制要求项目重新包装官方 `fileglide` 工具。

#### Scenario: 默认工具面包含官方 fileglide 工具
- **WHEN** 系统校验默认工具集合的元数据质量
- **THEN** 它 MAY 对官方 `fileglide` 工具做抽样兼容性检查
- **AND** 它 MUST NOT 把“重写官方工具文案”当成本 change 的硬要求
