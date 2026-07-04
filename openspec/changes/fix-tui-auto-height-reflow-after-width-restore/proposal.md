## Why

当前 SmartIPO TUI 在终端先横向缩窄、再恢复原宽后，宽度虽然回到了正确尺寸，但 `status-banner`、`queue-tray` 这类 `height: auto` 区域的高度没有同步紧凑回收，界面会残留被窄宽度阶段撑高的空白。这个问题说明当前统一 repaint 路径只保证了宽度重排，没有保证内容更新后的 auto 高度重新测量，因此需要单独补齐。

## What Changes

- 修复 TUI 在横向宽度恢复后的 auto 高度回收问题，确保 `status-banner`、timeline 邻接区域、`queue-tray` 和输入区回到与初始宽度一致的紧凑垂直布局。
- 调整 mount / resize 共享的 repaint 生命周期，让依赖最终内容测量的 `height: auto` 组件在内容更新后经历完整的二次 layout，而不是停留在窄宽度阶段的高度缓存上。
- 为横向缩窄再恢复的回归测试补充高度维度断言与稳定截图断言，防止只恢复宽度、不恢复高度的视觉回归再次出现。

## Capabilities

### New Capabilities
- `tui-auto-height-reflow-restoration`: 定义 TUI 在终端宽度恢复后，所有 auto 高度关键区域必须回到与初始稳定界面一致的紧凑高度。
- `tui-post-content-layout-reflow`: 定义 mount 与 resize 共享的 repaint 路径在写入最终内容后必须重新触发布局测量，避免 auto 高度停留在过时尺寸。

### Modified Capabilities
- None.

## Impact

- 受影响代码主要位于 `src/tui/app.py` 的统一 repaint 调度、局部内容刷新顺序和可能的布局二次测量逻辑。
- 需要更新 `test/test_tui_app.py`，让横向 resize 回归测试覆盖高度回收而不只是宽度恢复与截图一致性。
- 不引入新依赖，不改变 EasyHarness 事件语义、聊天消息表现或主题锁定范围。
