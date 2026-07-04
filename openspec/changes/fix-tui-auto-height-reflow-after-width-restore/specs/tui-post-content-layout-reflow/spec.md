## ADDED Requirements

### Requirement: 统一 repaint 路径必须在内容更新后重新执行布局测量
SmartIPO TUI MUST 让 mount 与 resize 共用的统一 repaint 路径在写入 `status-banner`、timeline、`queue-tray` 等最终内容后，再执行一次可依赖的布局测量与重绘，使 auto 高度组件基于最终内容而不是过时宽度状态完成尺寸收敛。

#### Scenario: resize 后的内容更新不会停留在旧高度测量
- **WHEN** 终端宽度变化导致关键区域内容换行发生变化
- **THEN** 系统 MUST 在最终内容更新后重新执行布局测量

#### Scenario: mount 与 resize 共享同一高度收敛生命周期
- **WHEN** 应用首次挂载或终端发生横向 resize
- **THEN** 系统 MUST 复用同一条支持 auto 高度收敛的 repaint 生命周期

#### Scenario: 最终几何状态稳定后才执行依赖尺寸的后续动作
- **WHEN** 系统需要执行滚动跟随、滚动到底或焦点恢复等依赖最终几何状态的动作
- **THEN** 这些动作 MUST 发生在内容更新后的最终布局稳定之后

