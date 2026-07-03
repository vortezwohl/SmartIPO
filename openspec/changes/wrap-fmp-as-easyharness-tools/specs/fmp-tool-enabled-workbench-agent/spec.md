## ADDED Requirements

### Requirement: 默认 business tools 必须包含 FMP 工具集
系统 MUST 将 FMP 业务工具集并入默认 business tools 装配路径。默认工具集合 MUST 同时包含官方 fileglide 工具、现有保留业务工具和 FMP 工具对象列表，而不是让 TUI 或调用方自行拼装第二套默认集合。

#### Scenario: 构造默认工具集合
- **WHEN** 调用方执行 `build_default_tools(...)`
- **THEN** 返回值 MUST 包含 fileglide 工具、现有保留业务工具以及 FMP 工具对象
- **AND** FMP 工具对象 MUST 以普通 EasyHarness tool object 形式直接出现在工具列表中

### Requirement: TUI 默认 agent 必须天然持有 FMP 工具，不新增专用注入层
系统 MUST 通过默认 agent composition 路径把 FMP 工具暴露给 TUI workbench。TUI MUST 继续通过现有 `build_default_agent(...)` 获取默认 agent，而不是引入专门的 “带 FMP 的 TUI agent” 构造分支。

#### Scenario: workbench 启动默认 agent
- **WHEN** TUI workbench 在未显式注入自定义 agent 的情况下启动
- **THEN** 它获取到的默认 agent MUST 已经包含 FMP 工具
- **AND** TUI 层 MUST NOT 负责二次注册或手工注入 FMP 工具

### Requirement: FMP 能力不可用时不得阻塞默认 agent 启动
系统 MUST 允许默认 agent 在 FMP 配置不完整时仍然成功构造。若 FMP 实际不可调用，失败 MUST 推迟到具体 FMP 工具调用时再显式暴露，而不是在 workbench 启动阶段直接让整个 agent 装配失败。

#### Scenario: 未配置 FMP_API_KEY 时构造默认 agent
- **WHEN** 调用方创建默认 agent 且当前未配置 `FMP_API_KEY`
- **THEN** 默认 agent 构造 MUST 仍然成功
- **AND** FMP 工具的失败 MUST 只在真实调用时暴露

#### Scenario: FMP 工具实际被调用
- **WHEN** 默认 agent 中的某个 FMP 工具被模型或用户触发
- **THEN** 系统 MUST 复用底层 `FmpClient` 的失败边界处理这次调用
- **AND** 失败结果 MUST 通过 EasyHarness 工具事件流和工具输出显式可见
