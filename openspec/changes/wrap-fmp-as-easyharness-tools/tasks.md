## 1. FMP 工具声明层

- [x] 1.1 新增 `src/tool/fmp_tools.py`，集中定义 FMP 工具注册表、统一元数据和 `build_fmp_tools()` 入口。
- [x] 1.2 在 `src/tool/fmp_tools.py` 中实现少量固定签名的 wrapper 工厂，覆盖日期区间、symbol、symbol+year+period、symbol+year+quarter 与仅 `extra_params` 这几类 FMP 方法形状。
- [x] 1.3 为 FMP 工具补齐统一的 `ToolOutput` 构造逻辑，确保原始结果、模型摘要和 TUI 预览字段都有稳定语义。

## 2. 默认 agent 注入

- [x] 2.1 更新 `src/tool/__init__.py`，导出 FMP 工具构造入口或必要常量，保持业务工具表面一致。
- [x] 2.2 更新 `src/agent.py` 的默认 business tool 名和 `build_default_tools(...)`，把 FMP 工具集并入默认装配路径。
- [x] 2.3 只在必要处更新默认 system prompt 或说明文案，明确 FMP 工具用于美股 IPO / 估值 / 财报研究任务。

## 3. 聚焦验证

- [x] 3.1 新增或扩展工具测试，验证 FMP 工具数量、稳定命名和代表性方法委托调用。
- [x] 3.2 新增或扩展失败边界测试，验证缺少 `FMP_API_KEY`、参数校验失败和 HTTP 失败都会按 EasyHarness 失败语义暴露。
- [x] 3.3 更新默认装配测试，确认 `build_default_tools(...)` 和默认 agent 已包含 FMP 工具，而不需要 TUI 额外注入。

## 4. 交付复查

- [x] 4.1 运行聚焦测试，至少覆盖 `test_fmp_client.py`、新增 FMP 工具测试和默认 tool/agent 装配测试。
- [x] 4.2 复查工具层与 `src/ext/fmp.py` 的职责边界，确认未把 HTTP/鉴权逻辑错误搬进 wrapper。
- [x] 4.3 视需要更新 README 或开发说明，记录默认 workbench 已接入 FMP 工具及其适用范围。
