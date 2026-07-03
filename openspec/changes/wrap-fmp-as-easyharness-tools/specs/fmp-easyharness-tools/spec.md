## ADDED Requirements

### Requirement: FMP 客户端公开查询方法必须暴露为标准 EasyHarness 工具
系统 MUST 将 `src/ext/fmp.py` 中 `FmpClient` 的每个公开查询方法暴露为一个 `easyharness.tool` 业务工具。每个工具 MUST 与一个且仅一个客户端方法对应，并使用稳定的 `fmp_` 前缀公开命名。系统 MUST NOT 把 `_get`、`_get_symbol_resource`、`_with_date_range`、`_resolve_*` 或 `create_fmp_client()` 这类 helper / factory 暴露为工具。

#### Scenario: 构造 FMP 工具集合
- **WHEN** 系统构造默认 FMP 工具集合
- **THEN** 返回结果 MUST 包含与 `FmpClient` 全部公开查询方法一一对应的工具对象
- **AND** 每个工具对象 MUST 具有以 `fmp_` 开头的稳定工具名

#### Scenario: 私有 helper 不得外露
- **WHEN** 调用方检查 FMP 工具清单
- **THEN** 工具集合 MUST NOT 包含底层 HTTP helper、环境变量解析 helper 或 client 工厂函数

### Requirement: FMP 工具参数合同必须是显式签名，不得使用 variadic 参数
由于 EasyHarness 工具不支持 `*args` 或 `**kwargs`，系统 MUST 为每个 FMP 工具声明固定、可验证的函数签名。对于底层 `FmpClient` 的透传查询参数，系统 MUST 使用结构化 `extra_params` 字段承接，而不是在工具函数上暴露 `**kwargs`。

#### Scenario: 调用方需要传递附加查询字段
- **WHEN** 调用方希望为某个 FMP 工具传递 `limit`、`page`、`period` 或其他底层 FMP query 字段
- **THEN** 工具 MUST 允许通过结构化 `extra_params` 输入这些附加字段
- **AND** 工具 MUST 将这些字段无损并入对应的 `FmpClient` 方法调用

#### Scenario: 工具 schema 生成
- **WHEN** EasyHarness 从 FMP 工具函数签名构造输入 schema
- **THEN** 系统 MUST 提供完整的参数文档和类型注解
- **AND** 工具函数 MUST NOT 包含 `*args` 或 `**kwargs`

### Requirement: FMP 工具必须保持薄包装并返回统一 ToolOutput
系统 MUST 将 FMP 工具实现为对底层 `FmpClient` 方法的薄包装。工具层 MUST NOT 在调用阶段附加 IPO 评分、估值结论、排序规则或复杂领域映射。每次成功调用 MUST 返回 `ToolOutput`，其中原始 FMP 结果 MUST 作为结构化数据回传，且同时提供适合模型和 UI 消费的摘要字段。

#### Scenario: 调用代表性 symbol 型工具
- **WHEN** 调用方执行某个按 `symbol` 查询的 FMP 工具
- **THEN** 系统 MUST 把显式参数与透传参数合并后委托给对应的 `FmpClient` 方法
- **AND** 返回值 MUST 是包含原始结果和简明摘要的 `ToolOutput`

#### Scenario: 调用代表性日期区间工具
- **WHEN** 调用方执行某个使用 `from_date` / `to_date` 的 FMP 工具
- **THEN** 系统 MUST 将日期参数映射到对应的 `FmpClient` 日期区间方法
- **AND** 工具层 MUST NOT 重写底层 FMP 返回结果的业务语义

### Requirement: FMP 工具失败必须按 EasyHarness 失败语义显式暴露
当底层 FMP API Key 缺失、参数不合法或 HTTP 请求失败时，系统 MUST 让错误通过 EasyHarness 工具失败语义对外暴露。系统 MUST NOT 把失败静默转换成空结果、默认结果或伪造成功摘要。

#### Scenario: 缺少 FMP API Key
- **WHEN** 调用方执行任一 FMP 工具且当前未配置有效 `FMP_API_KEY`
- **THEN** 该工具调用 MUST 失败
- **AND** 失败原因 MUST 明确说明缺少 FMP API Key

#### Scenario: FMP 返回非 2xx 响应
- **WHEN** 底层 `FmpClient` 请求抛出 HTTP 异常
- **THEN** EasyHarness 工具事件流 MUST 报告失败
- **AND** 系统 MUST NOT 把这次调用伪装成成功完成
