## 1. 元数据合同建模

- [x] 1.1 盘点默认工具面，明确项目自有工具与官方外部工具的元数据治理边界。
- [x] 1.2 为项目自有工具定义统一的元数据质量标准，覆盖 `purpose`、`when_to_use`、`parameters`、`returns` 与 `common_failures`。

## 2. FMP 工具元数据重构

- [x] 2.1 在 `src/tool/fmp_tools.py` 引入 FMP 元数据单一事实源，替换当前基于 docstring 首行和统一模板的文案生成方式。
- [x] 2.2 为 FMP 工具建立类别模板，并对关键高价值工具补充定制 `when_to_use`、`returns` 与 `extra_params` 示例。
- [x] 2.3 在现有 family 架构中统一补充参数约束说明，例如显式参数覆盖规则、日期映射与 symbol 标准化语义。

## 3. 基础工具与风格统一

- [x] 3.1 复查 `src/tool/basic_tools.py` 的元数据准确性，并统一项目自有工具的语言与表达风格。
- [x] 3.2 明确对官方 `fileglide` 工具只做兼容性审查，不引入项目侧重包装层。

## 4. Runtime 质量门禁

- [x] 4.1 新增针对 `build_default_tools(...)` 产物的 runtime metadata tests，直接校验 `tool_spec` 暴露结果。
- [x] 4.2 为关键 FMP 工具增加最小质量断言，防止 `when_to_use`、`returns` 与 `extra_params` 说明退化回不可区分模板。
- [x] 4.3 运行默认工具集合相关测试，确认元数据合同与质量门禁形成最小可靠闭环。
