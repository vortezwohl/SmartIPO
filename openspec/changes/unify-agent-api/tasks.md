## 1. 公开 API 收敛

- [x] 1.1 把当前会话型 `AgentSessionLoop` 收敛并重命名为唯一公开 `Agent`
- [x] 1.2 删除 `AgentLoop.run_once(...)` 与 `_SingleTurnSessionRunner`，清理只为双接口并存服务的代码路径
- [x] 1.3 调整 `src/core/__init__.py` 的导出，只保留统一后的 `Agent` 公开名字

## 2. 调用方与运行时对齐

- [x] 2.1 调整 `src/tui/app.py` 与其他调用点导入，统一改为依赖新的 `Agent`
- [x] 2.2 评估并收敛 `StrandsRuntime` 的单轮 helper，确保运行时主路径围绕 session runner 展开

## 3. 验证与清理

- [x] 3.1 更新聚焦测试，全部改为依赖统一后的 `Agent` 和 session runner 契约
- [x] 3.2 运行测试确认 API 收敛后行为不变，且 workbench 仍保留会话历史、多工具连续调用与事件流输出
