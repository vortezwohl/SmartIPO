## Why

`src/ext/fmp.py` 已经提供了完整的 FMP 研究客户端，但它目前只停留在 Python 调用层，TUI 默认 agent 仍然无法直接调用这些能力完成 IPO/估值类任务。上一轮架构收敛已经把 “FMP 是否需要包装成 EasyHarness 工具” 明确记录为后续问题；现在用户已经给出明确方向，这一层该补上了。

## What Changes

- 新增一组标准 `easyharness.tool` 业务工具，把 `FmpClient` 的全部 38 个公开查询方法一一包装成可调用工具。
- 为 FMP 工具建立稳定命名、统一元数据和统一 `ToolOutput` 输出格式，保持底层仍然复用 `src/ext/fmp.py` 的薄客户端边界。
- 处理 EasyHarness 工具不支持 `**kwargs` 的约束：对核心参数显式建模，并为 FMP 透传查询参数提供统一的结构化 `extra_params` 输入。
- 把 FMP 工具集注入默认 `build_default_tools(...)` / `build_default_agent(...)`，让 TUI workbench 启动后默认持有这批工具。
- 补充工具装配、代表性调用、失败透传和默认 agent 工具面的测试；不新增第三方依赖。

## Capabilities

### New Capabilities
- `fmp-easyharness-tools`: 定义 FMP 客户端公开方法如何被包装成标准 EasyHarness 工具，以及这些工具的参数与输出合同。
- `fmp-tool-enabled-workbench-agent`: 定义默认 workbench agent 如何装配并暴露 FMP 工具集，而不要求 TUI 再做额外注入层。

### Modified Capabilities
- 无。

## Impact

- 受影响代码主要集中在 `src/tool/`、`src/agent.py`、`test/` 和必要的 README/说明文档。
- `src/ext/fmp.py` 继续作为外部服务客户端边界存在；本次不把 HTTP/鉴权逻辑迁移到工具层。
- 默认 agent 的工具面会扩大，TUI 用户从此可以直接让 agent 调用 FMP 接口做研究辅助。
- 不新增新依赖；继续依赖现有 `easyharness`、`requests` 与项目本地测试设施。
