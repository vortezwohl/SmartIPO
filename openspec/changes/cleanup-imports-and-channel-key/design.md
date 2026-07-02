## Context

这次改动本质上不是“全仓 lint 整治”，而是一次很窄的运行时代码清理。当前已经确认的两个问题分别是：
- 少量真正未使用的形参会制造静态噪音；
- `src/model_config.py` 里 DeepSeek 渠道使用 `openai` 作为配置键名，语义不准确。

同时，仓库里也存在一批“看起来像未使用、实际不能删”的结构：
- `__init__.py` 中用于重导出的 import；
- `LLM.__call__` 这类抽象接口签名；
- 测试里的 fake runtime / fake runner 签名；
- 继续服务于 Python 3.10 兼容书写习惯的 `from __future__ import annotations`。

这意味着本轮设计重点不是“删得越多越好”，而是把可删和不可删的边界先钉死。

## Goals / Non-Goals

**Goals:**
- 只清理已经确认无业务作用的 import 和未使用形参。
- 把 DeepSeek 渠道键名调整为 `deepseek`，并同步修正引用点。
- 保持 `provider="openai"`、`model_id` 和现有模型装配行为不变。
- 用现有测试和编译检查证明这是一次行为等价清理。

**Non-Goals:**
- 不做全仓批量 lint。
- 不引入 `ruff`、`flake8` 或新的 CI 门禁。
- 不大规模移除 `from __future__ import annotations`。
- 不重构 `ModelHub`、`LLM` 抽象或 fileglide 工具组织结构。

## Decisions

### 1. 静态清理采用“白名单式删除”，不做机械扫描式整改

决策：只修改已经人工确认的少数位置，例如 fileglide handler 中未使用但必须保留签名的形参，优先改成前导下划线；对于抽象方法和测试替身签名，只在必要时做同样的保守标注，不删除参数。

理由：这类代码高度依赖上下文。机械删除很容易误伤 re-export、接口契约和测试替身。

备选方案：按 AST 或 lint 结果批量清理。拒绝，因为当前仓库没有现成 lint 工具链，且假阳性已经可见。

### 2. 渠道键名与 provider 字段刻意分离

决策：仅把 `CHANNEL_CONFIGS` 的 key 和 `BrainModelConfig.channel` 从 `openai` 改为 `deepseek`；保留 `ChannelConfig.provider = "openai"` 不变。

理由：渠道键名表达“这是谁的渠道”，provider 字段表达“底层 SDK 如何路由”。这两个维度不是一回事。

备选方案：把 provider 也一起改成 `deepseek`。拒绝，因为当前 LiteLLM / runtime 兼容路径依赖 `openai` provider 语义。

### 3. 验证沿用现有最小闭环

决策：使用 `compileall` 和现有 `unittest` 套件完成验证，并补充与渠道键名相关的断言。

理由：这轮改动非常小，现有检查已经足够覆盖“签名没坏、装配没坏、运行行为没变”。

备选方案：顺手引入新的静态检查命令。拒绝，因为这会把一次小清理扩成工具链变更。

## Risks / Trade-offs

- [把“未使用”误判为“可删除”] → 只处理人工确认的点，并优先重命名为前导下划线而不是改签名。
- [渠道键名调整遗漏引用点] → 全文搜索 `CHANNEL_CONFIGS` 和 `channel="openai"` 的使用点，并用现有模型装配测试兜底。
- [把渠道键名和 provider 语义混淆] → 在设计和测试里明确要求 `model_id` 保持不变。

## Migration Plan

1. 收敛本轮允许修改的静态噪音位置，逐个确认是否属于可安全清理项。
2. 修改 `CHANNEL_CONFIGS` 键名及主脑配置引用。
3. 更新测试断言，确保渠道键名变化不影响 `model_id` 和 client args。
4. 运行编译检查与现有测试，确认行为等价。

本轮没有独立部署或回滚要求；如果验证失败，直接回退本轮局部代码改动即可。

## Open Questions

- 是否要在后续单独立一个 change，为仓库补一套稳定的静态检查工具链。当前建议：不在本轮处理。
