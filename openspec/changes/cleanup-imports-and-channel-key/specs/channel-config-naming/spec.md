## ADDED Requirements

### Requirement: 系统必须使用语义化的 DeepSeek 渠道键名
系统 MUST 在 `CHANNEL_CONFIGS` 中使用 `deepseek` 作为 DeepSeek 渠道配置键名。引用该渠道的主脑模型配置 MUST 使用同一个键名，避免继续使用与渠道语义不一致的 `openai` 键名。

#### Scenario: 读取主脑模型渠道配置
- **WHEN** 系统从 `BRAIN_MODEL_CONFIGS` 读取主脑模型配置
- **THEN** 系统 MUST 能通过 `channel="deepseek"` 找到对应的渠道定义
- **AND** 系统 MUST NOT 再依赖 `channel="openai"` 作为 DeepSeek 渠道键名

### Requirement: 系统必须保留 provider 兼容语义
系统 MUST 仅调整渠道键名，不得改变底层 provider 兼容语义。对于当前 DeepSeek 文本模型装配，provider MUST 继续保持 `openai`，从而保证生成出的模型端点与现有运行时兼容。

#### Scenario: 装配 DeepSeek 主脑模型
- **WHEN** 系统创建默认主脑模型
- **THEN** 系统 MUST 继续生成兼容当前 runtime 的 provider/model 端点
- **AND** 调整渠道键名 MUST NOT 改变当前 `model_id` 的值
