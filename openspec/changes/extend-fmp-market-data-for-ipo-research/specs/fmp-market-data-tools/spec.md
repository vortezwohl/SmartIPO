## ADDED Requirements

### Requirement: 新增 FMP 市场数据方法必须暴露为默认 EasyHarness 工具
系统 MUST 将新增的 FMP 市场数据公开方法继续按既有规则包装为 `fmp_` 前缀的 EasyHarness 工具，使默认 agent 在不新增专用装配层的前提下即可调用完整历史价格、历史市值和公司筛选能力。

#### Scenario: 构造默认 FMP 工具集合
- **WHEN** 系统根据 `FmpClient` 公开方法构造默认 FMP 工具集合
- **THEN** 返回结果 MUST 包含新增市场数据方法对应的工具对象
- **AND** 这些工具 MUST 继续遵守现有的一方法一工具映射规则

### Requirement: 历史序列型 FMP 工具必须显式暴露日期区间参数
对于完整历史价格和历史市值这类时间序列研究工具，系统 MUST 提供显式、可验证的日期区间参数合同，而不是要求调用方把核心时间窗口完全藏在 `extra_params` 中。

#### Scenario: 调用历史价格或历史市值工具
- **WHEN** 调用方执行某个历史序列型 FMP 工具
- **THEN** 工具输入 MUST 显式包含 `symbol` 与日期区间字段
- **AND** 工具层 MUST 把这些显式字段正确映射到对应的 `FmpClient` 方法调用

### Requirement: 公司筛选工具必须保留结构化透传能力
对于公司筛选这类条件面较宽的接口，系统 MUST 继续允许通过结构化 `extra_params` 传递筛选字段，并返回统一 `ToolOutput`，而不是在工具层提前固化少量筛选条件。

#### Scenario: 调用公司筛选工具
- **WHEN** 调用方需要向 FMP company screener 传递行业、国家、市值或成交量等筛选字段
- **THEN** 工具 MUST 允许通过结构化 `extra_params` 承接这些字段
- **AND** 工具成功返回时 MUST 继续输出包含原始结果和最小摘要的 `ToolOutput`
