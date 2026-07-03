## Context

当前仓库已经具备两块稳定基础：

- `src/ext/fmp.py` 是完整的 FMP 薄客户端，当前包含 38 个公开查询方法，覆盖 IPO 日历、披露、招股书、财报、估值、可比公司、内部人交易和宏观参数等研究数据。
- `src/agent.py` 是默认 EasyHarness composition 入口，TUI 通过它构造默认 agent；当前默认工具面只有官方 fileglide toolset 和 Seedream 业务工具。

这意味着数据边界已经有了，但 agent 不会用。用户现在要求的是把 `FmpClient` 的全部公开接口包装成“规范且标准”的 EasyHarness 工具，并让 TUI 默认 agent 拿到它们。

这里有一个关键约束必须先说清：EasyHarness 工具会从 Python 函数签名生成输入 schema，且明确禁止 `*args` / `**kwargs`。而 `FmpClient` 的很多方法都保留了 `**params` 透传能力。因此这次设计的真正难点不是 HTTP，而是如何在不丢失 FMP 灵活性的前提下，把 variadic 参数面压成标准工具合同。

## Goals / Non-Goals

**Goals:**
- 新增一个最小的 FMP tool wrapper 模块，只负责 EasyHarness 工具声明，不复制 `FmpClient` 的 HTTP、鉴权和参数清洗逻辑。
- 为 `FmpClient` 的 38 个公开方法提供一一对应的业务工具，工具名稳定、可预测、便于模型选择。
- 让默认 `build_default_tools(...)` / `build_default_agent(...)` 自动装配 FMP 工具，TUI 无需新增专用注入层。
- 为 FMP 工具建立统一 `ToolOutput` 约定，兼顾模型后续推理和 TUI 时间线展示。
- 把验证范围控制在最小闭环：工具数量/命名、代表性委托调用、失败透传、默认 agent 装配。

**Non-Goals:**
- 不改造 `src/ext/fmp.py` 为复杂领域服务，不在工具层增加 IPO 评分、估值判断、缓存、重试、限流或报告生成。
- 不新增专门的 research agent、tool registry、provider bridge 或插件系统。
- 不为每个 FMP endpoint 建 dataclass 结果对象；底层仍保持原始 JSON 优先。
- 不在本轮重做 TUI 展示协议；TUI 继续只消费 EasyHarness 原生事件和 `ToolOutput`。

## Decisions

### 1. 新增单一 `src/tool/fmp_tools.py`，复用 `src/ext/fmp.py`

决策：新建一个单文件 `src/tool/fmp_tools.py`，作为 FMP 业务工具声明层；工具内部直接调用现有 `FmpClient` / `create_fmp_client()`，不把 HTTP 逻辑搬进工具层。

理由：`ext` 和 `tool` 的职责已经很清楚。`src/ext/fmp.py` 负责外部 API 边界，`src/tool/*.py` 负责 EasyHarness 工具合同。把二者继续分开，比“把 client 直接改成 tool”更简单也更稳。

备选方案：直接在 `src/ext/fmp.py` 给方法套工具装饰器。拒绝，因为这会把外部客户端和 agent 工具合同绑死在一起，削弱 `ext` 作为普通 Python 边界的复用价值。

### 2. 工具名统一采用 `fmp_<method_name>`，保持一一映射

决策：每个公开方法生成一个稳定工具名，规则为 `fmp_` 前缀加原方法名，例如：

- `get_profile` -> `fmp_get_profile`
- `get_ipos_calendar` -> `fmp_get_ipos_calendar`
- `search_insider_trades` -> `fmp_search_insider_trades`

理由：最省事也最不含糊。它既避免和未来其他数据源的 `get_profile`、`get_quote` 撞名，也让工具名与底层方法保持机械映射，后续维护和测试都容易。

备选方案：再做一轮语义重命名，例如 `fmp_profile`、`fmp_quote`。拒绝，因为收益不大，反而增加记忆成本和映射表复杂度。

### 3. 用“静态注册表 + 少量签名家族工厂”生成 38 个工具，而不是手写 38 个 wrapper

决策：在 `src/tool/fmp_tools.py` 中维护一个声明式注册表，记录每个方法的：

- `method_name`
- `tool_name`
- `purpose`
- `when_to_use`
- `returns`
- `common_failures`
- 对应的签名家族类型

然后只实现少量共享 wrapper 工厂，覆盖 5 类签名：

- `extra_params` 型：如 `get_latest_insider_trades`
- `from_date` / `to_date` / `extra_params` 型：如 `get_ipos_calendar`
- `symbol` / `extra_params` 型：如 `get_profile`
- `symbol` / `year` / `period` / `extra_params` 型：如 `get_financial_report_json`
- `symbol` / `year` / `quarter` / `extra_params` 型：如 `get_earnings_transcripts`

理由：EasyHarness 需要真实函数签名，不能直接拿 `**params` 动态兜底；但 38 个方法的签名模式其实很少。用“少量固定签名 + 注册表”能避免 38 份样板代码，同时保持工具 schema 仍然是标准、静态、可验证的。

备选方案 1：手写 38 个 `@tool` 函数。放弃，太重复，后续改元数据或输出格式会很痛。

备选方案 2：纯反射自动生成工具。放弃，因为 `purpose`、`when_to_use`、`common_failures` 和签名选择都需要人工约束，单靠 docstring 自动推不稳。

### 4. 透传参数统一收敛为结构化 `extra_params`

决策：所有需要承接 `FmpClient(..., **params)` 透传能力的工具，都显式提供一个可选 `extra_params: dict[str, Any] | None = None` 参数；工具层负责把它和一等参数合并后再调用底层 client。

理由：EasyHarness 明确不支持 `**kwargs`，这是 SDK 硬约束。要保留 FMP 的可扩展查询面，就必须把“可选透传字段”压成一个 JSON object 形状。`dict` 比字符串化 JSON 更自然，也更符合 tool-call 的结构化输入方式。

补充约束：
- `extra_params` 仅用于透传底层 FMP query 字段，不用于传递业务指令。
- 显式一等参数优先；若 `extra_params` 里出现同名字段，工具应以显式参数值覆盖。
- `extra_params` 不是必填项；常见场景依然走最小参数路径。

### 5. 统一返回 `ToolOutput`，原始结果放 `data`，摘要放 `preview/model_text/detail`

决策：所有 FMP 工具成功时都返回统一结构：

- `data`: 包含工具名、方法名、输入摘要和原始 FMP 结果；
- `model_text`: 供模型继续推理的简明文字摘要；
- `preview`: 供 TUI 时间线展示的一行概要；
- `detail`: 供本地 UI 查看的展开内容，可为格式化后的结果摘要文本。

理由：EasyHarness 已经把 `ToolOutput` 定义成模型和 UI 的共同出口。`data` 留原始 JSON，才能保持工具层仍是薄包装；`preview/model_text/detail` 提供人和模型都能直接消费的简短语义，避免时间线只看到一坨 JSON。

边界取舍：
- 工具层不对 FMP 返回做业务解释，只做最小摘要。
- 大结果仍然允许回传原始 JSON；这是薄包装的代价。若后续上下文膨胀真实成为问题，再单独收敛查询窗口或增加高层研究 helper。

### 6. FMP 工具集直接并入默认 business tools，TUI 不新增接线层

决策：`src/agent.py` 的默认装配改成：

- 保持 fileglide 工具照旧；
- 保持 Seedream 工具照旧；
- 追加 `build_fmp_tools()` 返回的 FMP 工具对象列表；
- 更新默认业务工具名常量和必要的 system prompt 提示。

理由：TUI 已经通过 `build_default_agent()` 获取默认 agent。既然用户要的是“注入到 tui 的 agent 手里”，最短路径就是改默认 composition，而不是再加一个 TUI 专用装配分支。

备选方案：给 TUI 单独做 `build_workbench_agent_with_fmp()`。拒绝，因为这会重新制造第二条默认 agent 路径。

### 7. 缺少 `FMP_API_KEY` 不阻塞 agent 启动，只在真实调用时失败

决策：默认 agent 构造阶段允许 FMP 工具存在但尚未成功访问 API；只有当用户或模型真正调用某个 FMP 工具时，才通过现有 `FmpClient` 行为显式暴露 “未找到 FMP API Key” 之类的失败。

理由：TUI 默认 agent 不能因为一个可选业务数据源没配 key 就整体不可用。当前 `FmpClient` 已经具备“调用前失败”的边界，直接复用最省事。

备选方案：在 `build_default_tools()` 阶段探测 key，没有就不注入 FMP 工具。拒绝，因为这样会让同一个 workbench 的工具面随环境隐式漂移，也降低可发现性。

## Risks / Trade-offs

- [38 个工具会扩大模型可选面] -> 用稳定前缀、紧凑 `when_to_use` 和统一摘要控制噪音；不再额外加“万能 FMP 工具”。
- [原始 JSON 直接回流模型，长结果可能占上下文] -> 首版接受这点；通过 `limit`、日期窗口和 `extra_params` 让调用方自己缩小结果面，需要时再补高层 helper。
- [`extra_params` 形状错误会导致工具校验失败] -> 这是预期行为；让 EasyHarness/Pydantic 直接给出结构化校验错误，比偷偷吞掉更可控。
- [当前工作区里 `src.tool.seedream_image` 的文件落点看起来不一致] -> 本变更不主动重构 Seedream；实现阶段若默认工具模块导入确实失败，先做最小路径修正，再挂 FMP 工具。
- [默认 agent 持有更多工具后，模型可能在模糊任务中过度调用 FMP] -> 通过 system prompt 明确 FMP 工具只用于美股 IPO / 估值 / 财报研究相关任务，不把它写成通用搜索替代品。

## Migration Plan

1. 新增 `src/tool/fmp_tools.py`，实现工具注册表、签名家族 wrapper、统一 `ToolOutput` 帮助函数和 `build_fmp_tools()`。
2. 更新 `src/tool/__init__.py` 与 `src/agent.py`，把 FMP 工具暴露到默认 business tools 和默认 agent。
3. 新增聚焦测试，验证工具数量/命名、代表性方法委托、失败透传和默认工具装配。
4. 如有必要，更新 README 或开发说明，明确默认 workbench 已可直接调用 FMP 工具。

## Open Questions

- 是否需要把 38 个工具全部默认放进 README 工具清单。当前建议不逐一罗列，只说明 FMP 工具已接入，具体能力以代码和测试为准。
- 是否要再提供更高层的“IPO 初筛”或“估值快照”聚合工具。当前建议不要，本轮先保持“一方法一工具”的薄包装。
