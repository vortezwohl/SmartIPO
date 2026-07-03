## Context

当前默认工具面来自三部分：
- 官方 `fileglide` toolset；
- 项目内 [src/tool/basic_tools.py](/D:/github-project/SmartIPO/src/tool/basic_tools.py)；
- 项目内 [src/tool/fmp_tools.py](/D:/github-project/SmartIPO/src/tool/fmp_tools.py)。

实际 runtime 审查表明，EasyHarness 最终暴露给模型的是 `tool_spec.description` 与 `inputSchema`，而不是函数对象表面属性。与此同时：
- `fileglide` 的 runtime 描述相对完整；
- `basic_tools` 的准确性基本可接受，但风格不统一；
- `FMP tools` 通过 [src/tool/fmp_tools.py](/D:/github-project/SmartIPO/src/tool/fmp_tools.py) 的统一模板生成 `when_to_use`、`returns` 与 `extra_params` 描述，导致 40+ 工具在边界表达上高度同质化。

这说明问题不在 agent runtime，而在项目如何组织并验证自有工具元数据。

## Goals / Non-Goals

**Goals:**
- 把项目自有工具元数据提升成稳定合同，而不是散落在装饰器参数里的临时字符串。
- 让 FMP 工具的用途、参数与返回说明具备类别区分度，并对关键高价值工具支持定制覆盖。
- 用 runtime 级测试锁住最终暴露给模型的 `tool_spec` 质量。
- 保持系统边界清晰：治理项目自有工具，不重包装官方 `fileglide`。

**Non-Goals:**
- 不修改 EasyHarness 或官方 `fileglide` SDK 源码。
- 不在本轮增加新的业务 tool，只治理元数据表达与质量门禁。
- 不把所有 FMP endpoint 文档完整复制进本地工具文案。

## Decisions

### 1. 为项目自有工具引入“元数据单一事实源”

决策：把项目自有工具的元数据从分散字符串提升为项目内的单一事实源。`basic_tools` 仍可保留内联声明；`fmp_tools` 则改为显式 metadata registry，由该 registry 生成 `purpose`、`when_to_use`、`returns` 与参数文案。

理由：当前 FMP 工具的问题本质上不是字段缺失，而是文案来源过于粗糙。把来源显式化之后，才有可能按类别模板、参数示例和关键工具覆盖做持续治理。

备选方案：继续从 `FmpClient` docstring 首行机械推导。拒绝，因为这只能产生“取什么数据”的表述，不能产出“何时应该用它”的研究语义。

### 2. FMP 工具采用“类别模板 + 关键工具覆盖”而非全量手写

决策：FMP 工具元数据分两层：
- 第一层：按工具类别提供基础模板，例如 `quote/profile`、`historical series`、`financial statements`、`valuation outputs`、`screeners/peers`、`macro`；
- 第二层：对关键高价值工具提供定制覆盖，例如 `quote`、`historical_price_eod_full`、`historical_market_cap`、`stock_peers`、`company_screener`、`financial_estimates`、`earnings_transcripts`。

理由：全量手写 40+ 工具文案维护成本太高，继续纯模板又无法解决问题。分层模板是最稳的中间解。

备选方案：为每个 FMP 工具完整手写五段文案。拒绝，因为后续新增方法时维护成本会迅速膨胀。

### 3. 参数文案按 family 统一约束，再按工具补示例

决策：保留现有 family 架构，但把 family 层参数文案升级为“基础约束”，例如：
- `symbol` 会被标准化为大写；
- 显式参数优先于 `extra_params` 同名字段；
- `from_date` / `to_date` 映射到底层 FMP 的 `from` / `to`。

同时，对 `extra_params` 依赖较重的工具增加少量高频字段示例。

理由：当前 family 已经承担了大部分 schema 生成职责，继续复用它比重做 schema 更优雅。缺的是有信息量的参数提示，而不是缺一个新框架。

备选方案：把所有高频透传字段都提升成显式参数。当前不采用，因为这会把 FMP wrapper 重新膨胀成接口镜像层。

### 4. `returns` 按结果形状而不是按“原始 JSON”表述

决策：返回说明改成“原始 JSON + 结果形状提示”，至少覆盖：
- 单对象快照；
- 列表记录；
- 时间序列；
- 文本内容或摘要。

理由：调用方最需要的是在调用前知道“这是不是我想要的结果形状”，而不是再次被告知它来自 FMP。

备选方案：维持统一 `returns` 句式。拒绝，因为这正是当前低区分度的来源之一。

### 5. 质量门禁必须校验 runtime `tool_spec`

决策：新增 metadata regression tests，直接针对 `build_default_tools(...)` 产出的工具对象读取 `tool_spec` 做断言，而不是只测试装饰器入参。

理由：runtime 暴露给模型的才是真实合同。只测源码很容易出现“源码看着对，但 runtime 退化了”的假阳性。

备选方案：只检查函数上定义的字符串。拒绝，因为现有审查已经证明那不是最终暴露面。

## Risks / Trade-offs

- [元数据治理可能演变成无边界文案工程] → 通过“类别模板 + 关键工具覆盖 + 最小示例”限制范围，不追求把 FMP 文档完整本地化。
- [过度追求中文统一会逼着项目重包第三方 toolset] → 明确只治理项目自有工具，外部 `fileglide` 保持原样。
- [新增门禁可能让后续小改动更容易失败] → 只锁住关键质量底线，不做脆弱的长文本全量比对。
- [FMP 工具数量继续增长时 registry 可能膨胀] → 用类别模板吸收大多数增量，只给关键工具保留覆盖入口。

## Migration Plan

1. 盘点默认工具面，确认“项目自有工具”与“外部工具”的治理边界。
2. 在项目内建立 FMP 元数据 registry 与少量辅助构造逻辑，替换当前纯模板式文案生成。
3. 统一修订 `basic_tools` 与 `FMP tools` 的元数据文案策略。
4. 补充 runtime metadata tests，覆盖关键工具和最低质量门禁。
5. 通过默认工具集合相关测试后，再逐步扩展到后续新增工具。

## Open Questions

- 是否要把 `basic_tools` 全量切到中文元数据；当前倾向于统一，但这不应阻塞 FMP 元数据治理主线。
- 是否需要增加一个只读审查脚本导出当前默认工具面的 metadata 报告；本轮可选，不设为硬要求。
