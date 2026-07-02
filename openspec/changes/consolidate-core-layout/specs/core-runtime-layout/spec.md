## ADDED Requirements

### Requirement: 系统必须把运行时核心目录收敛到 src/core
系统 MUST 将当前运行时核心能力统一收敛到 `src/core/`，并 SHALL NOT 继续保留与之并列的 `src/base/` 目录作为运行时公开入口。

#### Scenario: 调用方导入运行时核心能力
- **WHEN** 调用方需要导入运行时核心能力，例如 `Agent`、`LLM` 或 `Text2Text`
- **THEN** 系统 MUST 通过 `src/core/` 提供这些能力
- **AND** 调用方 SHALL NOT 继续依赖 `src/base/` 路径

### Requirement: 系统必须使用单一 agent.py 模块承载公开 Agent 语义
系统 MUST 使用单一 `src/core/agent.py` 模块承载公开 `Agent` 及其相关会话数据结构，不得继续使用 `agent_loop.py` 这类过渡期命名。

#### Scenario: 调用方查看公开 Agent 定义
- **WHEN** 调用方查找 SmartIPO 的公开主脑控制器
- **THEN** 系统 MUST 在 `src/core/agent.py` 中提供该定义
- **AND** 系统 MUST 不再保留 `src/core/agent_loop.py` 作为并列入口

### Requirement: 系统必须保留 llm.py 抽象和 text2text.py 单实现
系统 MUST 保留 `llm.py` 抽象层与 `text2text.py` 单实现层，但可以调整它们的目录位置。系统 MUST 不得为了目录收敛而删除这层单实现抽象。

#### Scenario: 运行时装配文本模型调用器
- **WHEN** 系统需要创建文本生成调用器
- **THEN** 系统 MUST 继续保留 `LLM` 抽象与 `Text2Text` 实现的分层关系
- **AND** 目录收敛 MUST 不改变这两者的职责语义

### Requirement: 系统不得保留已无必要的后向兼容冗余
在本轮目录收敛后，系统 MUST 删除旧导入路径、死桥接层、重复装配层和仅为后向兼容存在的模块，不得通过别名或转发模块继续保留这些冗余。

#### Scenario: 旧运行时路径已被新路径替代
- **WHEN** 某个旧模块路径或旧命名已经被新的 `src/core/` 布局完全替代
- **THEN** 系统 MUST 删除旧路径或旧模块
- **AND** 系统 MUST 不再提供兼容性 re-export 或转发壳
