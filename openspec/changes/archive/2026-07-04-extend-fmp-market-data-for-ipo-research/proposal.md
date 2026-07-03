## Why

当前 [src/ext/fmp.py](/D:/github-project/SmartIPO/src/ext/fmp.py) 和 [src/tool/fmp_tools.py](/D:/github-project/SmartIPO/src/tool/fmp_tools.py) 已经覆盖 IPO 文书、财报、估值指标和可比公司基础能力，但“市场行情研究”仍然偏薄，只有最新报价和轻量 EOD 历史价，无法稳定支撑 IPO 对标公司历史走势复盘、历史估值区间观察和候选可比样本筛选。现在补上这层是合适的，因为 agent 侧的 FMP 工具装配已经完成，只差把关键市场数据端点补进同一条研究链路。

## What Changes

- 在 FMP 客户端中新增首批美股市场行情研究端点，至少覆盖完整 EOD 历史价格、历史市值序列和公司筛选结果。
- 扩展 FMP EasyHarness 工具集合，使新增市场数据方法也能被默认 agent 直接调用。
- 为历史序列型工具补充更清晰的显式日期区间参数合同，避免把核心时间窗口完全隐藏在 `extra_params` 中。
- 补充针对新增端点的客户端与工具层回归测试，验证路径映射、参数委托和失败边界。

## Capabilities

### New Capabilities
- `fmp-market-data-research-client`: 定义 SmartIPO 的 FMP 客户端如何补充美股历史价格、历史市值和公司筛选能力。
- `fmp-market-data-tools`: 定义新增 FMP 市场数据方法如何暴露为默认 EasyHarness 工具，并保持可验证的参数合同。

### Modified Capabilities

无。

## Impact

- 受影响代码主要位于 `src/ext/fmp.py`、`src/tool/fmp_tools.py` 与对应测试文件。
- 默认 agent 的 FMP 工具面会自然扩展，但不新增第二套 agent 装配路径。
- 不引入新的第三方依赖；继续复用现有 FMP stable API、EasyHarness tool contract 和默认测试栈。
