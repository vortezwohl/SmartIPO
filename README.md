# OpenBuffett

OpenBuffett 是一个以美股专业级估值分析为主轴的研究 workbench，当前能力优先级为：

- 专业级估值分析：围绕公司质量、财务质量、估值区间、可比公司，以及 `1个月 / 6个月 / 1年 / 3年 / 5年` 视角输出结论先行的研究；其中短期视角必须补看货币/经济政策、地缘政治、广泛市场情绪与资金流向。
- 打新分析：仅针对尚未上市、正在申购或即将申购的美股新股，在估值分析基础上继续研读招股书、发行结构、稀释、锁定期与市场情绪。
- 市场数据辅助：查看股票、ETF 及当前数据面可严谨覆盖标的的历史 OHLC、市值与相关行情线索。

当前项目已收敛到 EasyHarness 主干架构：

- 默认 agent runtime 使用 `easyharness.Agent`。
- 默认纯文本生成使用 EasyHarness 无工具 agent，不再维护项目私有文本生成包装层。
- 默认文件系统工具使用 EasyHarness 官方 fileglide toolset。
- 自定义业务工具使用 `easyharness.tool` 声明。
- 默认业务工具当前只保留面向美股估值分析、IPO/打新研究与财报数据查询的 FMP 工具集。
- TUI 直接消费 `easyharness.AgentEvent` 流，不再维护项目自研 timeline 协议。
- 默认装配入口位于 `src.agent`，只负责模型配置、system prompt 和工具集合。

## 当前研究边界

- 默认业务范围暂限美股。
- 若用户提供的是公司名称、模糊名称或可能有笔误的名称，agent 会先推断候选 ticker，并要求用户确认后再进入正式估值分析。
- 凡涉及信息面、政策、地缘政治、市场情绪、资金流、新闻事件或 IPO 进度，agent 必须联网获取最新信息，并对来源做可信度分级，而不是盲信单一媒体或传闻。
- 对期货、期权、广义衍生品、加密资产等，若当前数据面不足以严谨验证，agent 会明确承认边界，而不会伪装成完整支持。
- agent 默认保持去情绪化、可审计表达；输出中会尽量保留精简版来源、时间戳、置信等级与未证实项说明。
- 完整研究结束后，agent 会主动询问是否在当前工作路径下生成中文 Markdown 研究报告。

## 本地运行

```powershell
.\.venv\Scripts\python -m src.tui
```

运行前需要配置默认模型渠道所需的环境变量：

- `API_KEY`: 模型 API key。
- `API_BASE`: 可选，未配置时使用 `src.agent` 中的默认 base URL。
- `FMP_API_KEY`: 可选；未配置时 workbench 仍可启动，但 FMP 工具在真实调用时会显式失败。
- `FMP_API_BASE`: 可选；未配置时使用 `src.ext.fmp` 中的默认 FMP stable base URL。
