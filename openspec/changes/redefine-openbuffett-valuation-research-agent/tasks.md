## 1. Agent Identity And Prompt Contract

- [x] 1.1 在 `src/agent.py` 中新增并导出 `OpenBuffett` 品牌常量、启动开场常量与研究报告追问相关常量，集中承载新的产品身份定义
- [x] 1.2 重写默认 system prompt，使其明确估值优先、ticker 先确认、打新门禁、事实分级、多周期估值判断、短期宏观与资金面约束、联网最新信息与来源分级约束、当前做多/做空风险提示与报告追问合同
- [x] 1.3 更新 `src/__init__.py`、`src/tool/__init__.py`、`src/tool/basic_tools.py`、`README.md` 与 `pyproject.toml` 的当前对外表面文案和元数据，移除现行运行面中的 `SmartIPO` 品牌露出而不改历史归档文件

## 2. TUI Opening And Branding Surface

- [x] 2.1 调整 `src/tui/app.py` 启动流程，在 `on_mount()` 后注入首条 assistant 开场消息，而不是等待用户先发起第一轮对话
- [x] 2.2 让 TUI 消费 `src/agent.py` 导出的开场常量，避免在界面层保留独立的硬编码欢迎文案
- [x] 2.3 将 TUI 标题、输入框 placeholder、系统消息标题与运行状态文案统一替换为 `OpenBuffett` 品牌表述

## 3. Research Workflow Guardrails

- [x] 3.1 调整默认研究行为，使非 ticker 输入先进入候选代码推断与用户确认阶段，确认前不得继续正式估值或打新分析
- [x] 3.2 调整默认估值研究输出，确保完整分析覆盖结论先行、证据等级、可比公司、1个月/6个月/1年/3年/5年估值视角，以及短期宏观与资金面驱动和当前时间点风险提示
- [x] 3.3 调整默认打新研究输出，确保其仅在未上市且可申购/待申购场景触发，并在结尾主动询问是否生成当前工作路径下的中文 Markdown 研究报告

## 4. Regression And Verification

- [x] 4.1 更新 `test/test_tooling.py` 等 prompt 相关测试，断言新的品牌身份、能力优先级、ticker 确认门禁、联网最新信息与来源分级约束、报告追问语义
- [x] 4.2 更新 `test/test_tui_app.py` 等 TUI 测试，覆盖启动即出现开场消息、`OpenBuffett` 品牌文案与新的状态提示
- [x] 4.3 为 ticker 确认、已上市公司打新门禁回退、研究完成后报告追问等关键行为补充回归测试或可执行验证用例
- [x] 4.4 运行与本次变更直接相关的测试集合，记录仍需人工确认的网络数据边界或运行时行为
