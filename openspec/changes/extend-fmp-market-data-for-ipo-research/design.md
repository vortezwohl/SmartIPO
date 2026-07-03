## Context

当前仓库里 [src/ext/fmp.py](/D:/github-project/SmartIPO/src/ext/fmp.py) 已经提供 38 个公开研究方法，[src/tool/fmp_tools.py](/D:/github-project/SmartIPO/src/tool/fmp_tools.py) 会按公开方法自动生成默认 FMP EasyHarness 工具，因此这次扩展不需要再新造一层工具注册框架。真正缺的是市场行情研究的几个关键端点：当前只有 `get_quote` 和 `get_historical_price_eod_light`，不足以支撑 IPO 对标公司的历史价格复盘、历史市值区间观察和候选可比公司发现。

约束也比较明确：
- 继续使用 FMP stable API，不引入新的数据源或 SDK；
- 保持 `FmpClient` 薄封装，返回 FMP 原始 JSON，不在 client/tool 层生成投研结论；
- 默认 agent 已经自带 FMP 工具装配，本次只扩 public methods 和必要的工具签名家族；
- 优先最小增量，不顺手补第二批批量行情、技术指标或缓存层。

## Goals / Non-Goals

**Goals:**
- 在 `FmpClient` 中补齐首批美股市场数据研究端点，至少覆盖完整历史价格、历史市值和公司筛选。
- 让这些新增方法自动进入默认 FMP 工具集合，并保持稳定命名与统一输出。
- 对历史序列查询补上更适合 agent 使用的显式日期区间工具签名。
- 为新增端点建立最小回归测试，验证路径、参数和失败边界。

**Non-Goals:**
- 不新增 IPO 评分器、估值报告生成器、缓存层、批量抓取框架或异步任务层。
- 不在本轮接入第二批市场数据端点，例如 batch quote、技术指标或期权链。
- 不修改默认 agent 装配架构，也不新增专门的 “市场数据 agent”。

## Decisions

### 1. 首轮只补三类市场数据端点

决策：首轮只在 [src/ext/fmp.py](/D:/github-project/SmartIPO/src/ext/fmp.py) 新增三类方法：
- 完整 EOD 历史价格；
- 历史市值序列；
- 公司筛选结果。

理由：这三类端点已经能覆盖用户当前提出的“历史其他公司股票行情分析”和“估值分析”主链路。它们分别对应价格路径、估值时间序列和可比样本发现，收益最高，且不会把这轮工作膨胀成全量市场数据 SDK。

备选方案：把 batch quote、技术指标、sector multiples 一次性全加上。拒绝，因为这些要么改变工具签名面更多，要么与当前 IPO 研究主链路相比优先级更低。

### 2. 客户端继续保持薄封装，不在 client 层建结果模型

决策：新增方法继续复用现有 `_get()` / `_get_symbol_resource()` 风格，直接返回 FMP 原始 JSON，不引入 dataclass、估值快照对象或统一时序模型。

理由：当前最需要的是稳定拉数而不是预加工。历史价格和历史市值本身就可能因为参数不同返回不同结构，过早建模只会增加维护成本。

备选方案：为行情序列单独定义领域结果对象。拒绝，因为当前没有重复解析痛点支撑这层复杂度。

### 3. 为历史序列工具新增 `symbol_date_range` 签名家族

决策：在 [src/tool/fmp_tools.py](/D:/github-project/SmartIPO/src/tool/fmp_tools.py) 中新增一个只服务时间序列研究的工具签名家族，使完整历史价格和历史市值工具显式接收 `symbol`、`from_date`、`to_date` 与 `extra_params`。

理由：如果继续把时间窗口完全塞进 `extra_params`，模型可发现性和工具 schema 可读性都会变差。历史区间是这类查询的一等输入，应该在工具合同里直接体现。

备选方案：沿用现有 `symbol` 家族，把 `from` / `to` 继续藏进 `extra_params`。拒绝，因为这会让最关键的研究窗口字段退化成隐式约定。

### 4. 公司筛选工具继续使用 `extra_params`，不提前固化几十个筛选字段

决策：公司筛选方法在 client 层保持薄封装，在 tool 层沿用 `extra_params` 承接 industry、country、exchange、marketCapMoreThan、priceMoreThan 等条件。

理由：company screener 的查询面很宽，若在工具函数签名里硬展开全部字段，会立刻制造大量样板和维护噪音。这里继续使用结构化透传，是当前最省事也最稳的做法。

备选方案：把常见筛选字段都提升为显式工具参数。暂不采用，因为当前没有证据表明 agent 已经需要这么细的显式 schema。

### 5. 工具扩展继续依赖“公开方法自动包装”机制

决策：不新建第二套 FMP tool registry。新增 client 方法后，继续由现有 `FMP_TOOL_SPECS` / `build_fmp_tools()` 机制自动纳入默认工具集合，仅在签名识别逻辑需要时补充一个新的 family。

理由：仓库已经有正确的边界分层。重复造一套“只给市场数据用”的工具集只会引入路径漂移。

备选方案：单独维护 market-data tool 列表。拒绝，因为它破坏了现有 public method 到 tool 的机械映射。

## Risks / Trade-offs

- [历史序列结果可能很长] → 通过显式日期区间和现有 `ToolOutput` 摘要控制上下文面，首轮不再引入分页聚合层。
- [新增 `symbol_date_range` family 会触碰工具签名识别逻辑] → 只为明确的时间序列方法补这一类，并用定向测试锁住行为。
- [company screener 查询字段很多，`extra_params` 仍需调用方理解 FMP 参数] → 接受这点，优先保持薄包装；只有出现高频重复条件时再提升显式字段。
- [首轮不做 batch quote/technical indicators，市场数据仍非“全能”] → 这是有意收敛，先覆盖 IPO 研究最短路径。

## Migration Plan

1. 在 [src/ext/fmp.py](/D:/github-project/SmartIPO/src/ext/fmp.py) 增加新增市场数据方法，并保持中文说明与现有请求边界一致。
2. 在 [src/tool/fmp_tools.py](/D:/github-project/SmartIPO/src/tool/fmp_tools.py) 补充必要的签名家族识别与 wrapper，使新增方法自动暴露为工具。
3. 扩展 [test/test_fmp_client.py](/D:/github-project/SmartIPO/test/test_fmp_client.py) 与 [test/test_fmp_tools.py](/D:/github-project/SmartIPO/test/test_fmp_tools.py) 的代表性回归用例。
4. 运行定向测试确认客户端路径映射、工具委托和失败语义未回归。
5. 若需要回滚，只需回退本 change 涉及的 FMP client / tool / test 代码，不涉及数据迁移。

## Open Questions

- FMP 文档中的 company screener 是否需要在首轮就补常见字段别名说明；当前建议先不做，保留原始参数名。
- 第二阶段是否需要再补 batch quote 或技术指标工具；当前不纳入本 change。
