## 1. FMP 客户端市场数据扩展

- [x] 1.1 在 `src/ext/fmp.py` 新增完整历史价格、历史市值和公司筛选方法，并补齐对应中文说明。
- [x] 1.2 复查新增方法与现有 `_get()` / `_get_symbol_resource()` 边界的契合方式，确保不把额外 HTTP 逻辑搬进公开方法。

## 2. FMP 工具合同扩展

- [x] 2.1 在 `src/tool/fmp_tools.py` 补充历史序列型工具所需的签名家族识别与 wrapper，实现显式日期区间参数合同。
- [x] 2.2 确认新增 client 方法会自动进入 `FMP_TOOL_NAMES` 与 `build_fmp_tools()` 返回集合，且公司筛选工具继续使用结构化 `extra_params`。

## 3. 回归验证

- [x] 3.1 扩展 `test/test_fmp_client.py`，验证新增市场数据端点的 URL 路径、查询参数拼接和错误透传。
- [x] 3.2 扩展 `test/test_fmp_tools.py`，验证新增历史序列工具和公司筛选工具的参数委托与 EasyHarness 失败语义。
- [x] 3.3 运行与 FMP 相关的定向测试，确认默认 FMP 工具集合与新增能力形成最小可靠闭环。
