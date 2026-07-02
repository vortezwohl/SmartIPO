## ADDED Requirements

### Requirement: 系统必须把 thinking 状态与动画展示解耦
系统 MUST 把 thinking 视为活动状态事实，而 SHALL 由 UI 在本地渲染动画效果。系统 MUST NOT 通过持续发事件的方式把 `thinking . .. ...` 动画本身编码进运行时事件流。

#### Scenario: 会话进入思考中状态
- **WHEN** 运行时发出 `thinking_started`
- **THEN** 系统 MUST 在 timeline state 中标记一个运行中的 thinking 条目
- **AND** UI MAY 基于该条目本地渲染 `thinking . .. ...` 这样的循环动画

#### Scenario: 思考状态结束
- **WHEN** thinking 条目收到完成或失败事件
- **THEN** 系统 MUST 停止该 thinking 条目的运行状态
- **AND** UI MUST 停止对应本地动画

### Requirement: 系统必须让工具运行中展示与 thinking 展示共享同一活动语义
系统 MUST 使用统一的活动状态语义表示 running 中的 thinking 与 tool 条目，从而让不同 UI 可以复用同一套计时与状态展示规则。

#### Scenario: 工具仍在执行
- **WHEN** 某个工具条目处于运行中
- **THEN** 系统 MUST 在 timeline state 中保留该条目的 running 状态与持续时长
- **AND** UI MUST 能依据统一状态规则展示进行中的工具卡片
