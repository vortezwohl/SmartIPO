## Why

当前仓库里已经出现少量“看起来像 lint 噪音”的代码，例如真正未使用的形参、以及语义不够准确的渠道键名。这些问题现在规模还小，适合在不扩散范围的前提下做一次保守清理，避免后续继续堆积成机械式大改。

## What Changes

- 在不改变运行行为的前提下，清理一小批已经确认无业务作用的 import 和未使用形参。
- 明确排除包级 re-export、抽象接口签名、测试替身签名这类不能机械删除的情况。
- 把 `src/model_config.py` 中 DeepSeek 渠道的配置键从 `openai` 调整为 `deepseek`，让渠道命名与真实语义一致。
- 保留底层 `provider="openai"` 和生成出的 `model_id` 语义，不把兼容 OpenAI 的 provider 标识误改为渠道名。

## Capabilities

### New Capabilities
- `runtime-static-hygiene`: 定义运行时代码静态清理的安全边界，只允许删除已确认无语义作用的 import 和未使用形参。
- `channel-config-naming`: 定义模型渠道配置必须使用语义化渠道键名，同时保持 provider 兼容语义不变。

### Modified Capabilities
- None.

## Impact

- 受影响代码主要位于 `src/model_config.py`、`src/service/model_hub.py`、`src/core/llm.py`、`src/tool/fileglide_tools.py` 与相关测试。
- 不新增依赖，不引入新的 lint 工具链，不改变对外 API 和运行时行为。
- 测试需要覆盖渠道键名调整后模型装配仍然生成相同的 `model_id`，以及保守清理没有伤害现有行为。
