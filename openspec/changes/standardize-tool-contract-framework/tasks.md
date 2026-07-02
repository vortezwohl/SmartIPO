## 1. 建立基础 contract 与目录结构

- [x] 1.1 新增公共 tool framework 模块，用于承载 structured doc、result contract、error contract、policy 接口与 validator
- [x] 1.2 重构 `src/tool/contracts.py`，让 `ToolSpec`、`ToolResult` 兼容结构化 contract，同时保留必要的 legacy 兼容入口
- [x] 1.3 实现 provider-facing description renderer，统一从 structured tool doc 生成英文 description

## 2. 建立 catalog validation 与执行骨架

- [x] 2.1 实现 tool catalog validator，校验 schema 与 parameter docs 对齐、required sections 完整、tool 名称与 provider 名称无冲突
- [x] 2.2 为 contract 层补充 English-only 校验规则，覆盖 description sections、documented return fields 与 error identifiers
- [x] 2.3 实现统一的 tool execution helpers，使 result mapping、error mapping 与 policy 接入不再散落在 concrete tools 中

## 3. 抽离并沉淀可复用 policy

- [x] 3.1 从 fileglide 中抽离 scoped path normalization policy，覆盖 `root`、`start`、`target` 的归一化和冲突诊断
- [x] 3.2 从 fileglide 中抽离 readonly traversal policy，统一浅探索默认值与权限恢复建议
- [x] 3.3 从 fileglide 中抽离通用 result formatter 与 error mapper，使 model-facing text、preview、detail、raw diagnostics 的生成路径明确

## 4. 调整 runtime 适配统一 result/error contract

- [x] 4.1 重构 `src/core/strands_runtime.py`，让 runtime 优先消费结构化 `ToolResult` 与 `ToolError`
- [x] 4.2 保留 runtime 对 legacy tool result 的兼容兜底，避免迁移期间一次性破坏所有工具
- [x] 4.3 统一 tool lifecycle event payload，使 UI 可稳定消费 preview、detail、error code、raw error 与 retry hints

## 5. 迁移现有工具到统一框架

- [x] 5.1 迁移 `fileglide` tools 到 structured tool definition contract，并删除私有 description 拼接和分散 contract 逻辑
- [x] 5.2 迁移 `Seedream` tool 到同一 contract，消除自由文本 description 与临时 metadata 语义
- [x] 5.3 检查默认 tool registry，确保新旧工具都通过 catalog validation 后再暴露给 runtime

## 6. 切分 composition 与 UI 边界

- [x] 6.1 新增 application composition 入口，承载默认 system prompt、默认 tool set、默认 model 与默认 agent/session 组装
- [x] 6.2 从 `src/tui/app.py` 移除默认 agent 组装职责，让 TUI 只接收已装配好的 session/agent
- [x] 6.3 确认 `src/core/timeline.py` 继续作为 cross-UI timeline semantics 层，不引入 TUI 或 future WebUI 依赖

## 7. 验证与收尾

- [x] 7.1 为 structured tool docs、catalog validation、English-only rules 增加测试
- [x] 7.2 为 runtime result/error serialization 与 legacy compatibility 增加测试
- [x] 7.3 为 fileglide migration、Seedream migration 与 TUI/composition boundary 增加测试
- [x] 7.4 运行现有自动化验证并修正回归，确保 change 在当前仓库中可落地
