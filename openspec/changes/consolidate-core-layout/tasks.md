## 1. 运行时核心文件迁移

- [x] 1.1 新增 `src/core/agent.py`，承载当前公开 `Agent` 与相关会话数据结构
- [x] 1.2 把 `src/base/llm.py` 与 `src/base/text2text.py` 迁移到 `src/core/`，并保留现有抽象与单实现关系
- [x] 1.3 调整 `src/core/__init__.py`，统一从新的 `src/core/` 布局导出运行时核心能力

## 2. 冗余与旧路径清理

- [x] 2.1 更新 `src/service/`、`src/tui/` 与测试中的导入，彻底移除 `src.base.*` 与 `src.core.agent_loop` 路径依赖
- [x] 2.2 删除 `src/base/agent.py`，清理与 `model_hub.py` 职责重叠的死装配层
- [x] 2.3 删除 `src/base/` 整个目录与 `src/core/agent_loop.py`，不保留兼容转发壳

## 3. 验证与残留检查

- [x] 3.1 更新聚焦测试，确保统一后的 `src/core/` 布局仍覆盖主脑模型装配、会话 Agent、fileglide I/O 与 TUI smoke test
- [x] 3.2 运行测试与全文搜索，确认行为不变且仓库中不再残留旧导入路径或后向兼容冗余
