# SmartIPO

SmartIPO 已收敛到 EasyHarness 主干架构：

- 默认 agent runtime 使用 `easyharness.Agent`。
- 默认纯文本生成使用 EasyHarness 无工具 agent，不再维护项目私有文本生成包装层。
- 默认文件系统工具使用 EasyHarness 官方 fileglide toolset。
- 自定义业务工具使用 `easyharness.tool` 声明。
- 默认业务工具当前只保留面向美股 IPO / 财报 / 估值研究的 FMP 工具集。
- TUI 直接消费 `easyharness.AgentEvent` 流，不再维护项目自研 timeline 协议。
- 默认装配入口位于 `src.agent`，只负责模型配置、system prompt 和工具集合。

## 本地运行

```powershell
.\.venv\Scripts\python -m src.tui
```

运行前需要配置默认模型渠道所需的环境变量：

- `API_KEY`: 模型 API key。
- `API_BASE`: 可选，未配置时使用 `src.agent` 中的默认 base URL。
- `FMP_API_KEY`: 可选；未配置时 workbench 仍可启动，但 FMP 工具在真实调用时会显式失败。
- `FMP_API_BASE`: 可选；未配置时使用 `src.ext.fmp` 中的默认 FMP stable base URL。
