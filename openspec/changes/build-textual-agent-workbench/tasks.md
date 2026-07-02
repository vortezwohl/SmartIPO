## 1. 主脑模型配置收敛

- [x] 1.1 新增 `src/model_config.py`，集中定义本地 agent 主脑模型、provider、temperature、top_p、seed 与环境变量映射
- [x] 1.2 新增 `src/service/model_hub.py`，把 strands 主脑模型装配收敛到统一入口，并让现有主脑调用路径改用该入口
- [x] 1.3 补充聚焦测试，验证主脑运行时只读取集中配置，普通调用点不能随意覆写采样参数

## 2. 会话型运行时与事件桥接

- [x] 2.1 扩展 `src/tool/contracts.py` 并新增统一事件定义，覆盖思考、工具调用与 assistant 流式输出的事件结构
- [x] 2.2 升级 `src/core/strands_runtime.py`，通过 strands callback handler 与工具包装桥接 `thinking_*`、`tool_*`、`assistant_stream_*` 事件及耗时
- [x] 2.3 新增会话型 `AgentSessionLoop` 或等价 controller，维护消息历史并确保一个任务内可连续调用多个工具直到自然结束
- [x] 2.4 补充 fake runtime 测试，验证多工具连续调用、事件顺序与工具失败向上暴露

## 3. fileglide 工具集接入

- [x] 3.1 新增 `src/tool/fileglide_tools.py`，基于已安装的 fileglide Python facade 暴露完整本地文件系统工具集
- [x] 3.2 调整默认工具注册表，使 fileglide 工具与现有 SmartIPO 工具可在本地会话中共同暴露
- [x] 3.3 补充工具边界测试，验证本地 agent 会话可完成常见文件 I/O，且不需要切换到外部 shell

## 4. Textual workbench 落地

- [x] 4.1 新增 `src/tui/app.py`，实现单会话的 Textual 时间线界面与任务输入入口
- [x] 4.2 把统一事件流接到时间线渲染，支持 assistant 文本流式追加、思考占位覆盖和工具调用计时展示
- [x] 4.3 补齐本地 workbench 启动入口，让 Textual workbench 成为默认本地 agent 交互入口

## 5. 集成验证

- [x] 5.1 新增 TUI smoke test，验证提交任务后时间线能依次展示用户消息、过程事件和 assistant 流式输出
- [x] 5.2 运行聚焦测试与本地手工冒烟，确认 fileglide、会话型 agent loop、事件流和 Textual workbench 能形成最小可用闭环
