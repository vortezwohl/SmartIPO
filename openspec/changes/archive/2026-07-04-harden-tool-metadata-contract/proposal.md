## Why

当前 SmartIPO 的默认工具面已经能工作，但元数据质量不一致：官方 `fileglide` 工具描述较完整，`basic_tools` 基本可用，而 `FMP tools` 明显模板化，`when_to_use`、`parameters` 与 `returns` 对模型选 tool 的帮助不足。这已经不是“文案润色”问题，而是 agent 产品面的合同问题；如果不收敛成稳定、可审查、可测试的元数据体系，后续每次新增 tool 都会继续积累歧义和误选风险。

## What Changes

- 为项目自有工具建立统一的元数据合同，明确 `purpose`、`when_to_use`、`parameters`、`returns` 与 `common_failures` 的质量标准和职责边界。
- 重构 FMP 工具元数据生成方式，从“纯模板拼接”升级为“类别模板 + 关键工具定制 + 参数示例”的可维护结构。
- 为默认工具面建立 runtime 级元数据质量门禁，直接检查 EasyHarness 最终暴露给模型的 `tool_spec`，而不是只检查源码字符串。
- 只对项目自有工具做深度治理；外部官方 `fileglide` 工具保留现有来源，但纳入兼容性审查范围。

## Capabilities

### New Capabilities
- `project-tool-metadata-contract`: 定义 SmartIPO 项目自有工具的元数据必须如何表达用途、参数、返回与失败边界。
- `tool-metadata-quality-gates`: 定义默认工具面必须如何在 runtime 层接受元数据质量校验与回归保护。

### Modified Capabilities

无。

## Impact

- 受影响代码主要位于 `src/tool/fmp_tools.py`、`src/tool/basic_tools.py` 与对应测试。
- 可能新增一个项目内的轻量元数据辅助层，用于收敛 FMP 工具分类模板与定制文案。
- 不引入新的第三方依赖，不改 EasyHarness 或官方 `fileglide` toolset 的源码。
