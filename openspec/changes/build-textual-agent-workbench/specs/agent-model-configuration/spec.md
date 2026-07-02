## ADDED Requirements

### Requirement: 系统必须提供主脑模型总配置文件
系统 MUST 在 `src/model_config.py` 中集中定义主脑模型配置，包括模型名、provider、temperature、top_p、seed 以及对应环境变量映射，不得把这些参数继续散落在 TUI、runtime 或调用点代码中。

#### Scenario: 主脑运行时装配模型
- **WHEN** 系统需要为本地 agent 会话创建主脑模型
- **THEN** 系统 MUST 从 `src/model_config.py` 读取模型与采样参数
- **AND** 运行时 MUST 使用该集中配置装配主脑模型

### Requirement: 调用点不得覆写集中采样参数
系统 MUST 把主脑采样参数视为集中配置的一部分；普通调用点 SHALL NOT 在运行时任意覆写 temperature、top_p 或 seed。

#### Scenario: 调用方尝试覆写主脑采样参数
- **WHEN** 调用点试图绕过集中配置直接传入新的采样参数
- **THEN** 系统 MUST 拒绝该覆写或忽略该覆写
- **AND** 实际主脑调用 MUST 继续使用 `src/model_config.py` 中的配置值
