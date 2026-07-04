## Context

当前 `AgentWorkbenchApp` 已经把 mount 与 resize 汇总到统一的 repaint 入口，但现有顺序是先执行 `refresh(layout=True, repaint=True)`，再通过 `_refresh_view()` 更新 `status-banner`、timeline 与 `queue-tray` 的内容。这个顺序可以修复横向宽度崩坏问题，却不能保证 `height: auto` 组件在内容恢复到宽宽度版本后重新测量高度，因此会出现宽度已恢复、垂直空白仍保留的状态。

受影响的关键区域包括：
- `#status-banner`：`height: auto`
- `#queue-tray`：`height: auto`
- `#timeline-view`：内容高度变化会影响相邻容器的剩余空间分配

本次变更不重新设计 TUI 布局结构，也不改变消息语义、主题锁定、队列行为或 thinking 历史样式。目标仅限于让横向缩窄再恢复后的高度测量与初始稳定界面保持一致。

## Goals / Non-Goals

**Goals:**
- 让终端横向缩窄后再恢复原宽时，所有 auto 高度关键区域回到与初始稳定界面一致的紧凑高度。
- 调整统一 repaint 生命周期，使内容更新完成后必然触发一次可依赖的布局重测，而不是只复用宽度 repaint。
- 为回归测试增加高度维度断言与恢复后截图一致性断言，覆盖“宽度回来了但高度没回去”的问题。

**Non-Goals:**
- 不改动整体 TUI 组件树，不引入新的容器层级或新的主题系统。
- 不处理与本次问题无关的输入焦点、滚动策略、消息格式或系统命令行为。
- 不扩展到纵向高度变化策略；本次仅覆盖横向宽度恢复后的高度回收。

## Decisions

### 1. 把统一 repaint 路径改为“先更新内容，再重测布局”

决策：统一 repaint 路径应保证依赖内容测量的组件在最终内容写入后经历一次明确的 layout pass。实现上应把“更新 `status-banner` / timeline / queue-tray 内容”和“最终 layout + repaint”拆成前后两个阶段，而不是先 layout 后写内容。

原因：
- `height: auto` 组件的高度取决于最终文本换行与 renderable 实际尺寸。
- 先 layout 再 update 只能修宽度，不保证高度从窄宽度阶段收回。
- 这次问题本质是生命周期顺序问题，不是单个组件样式问题。

备选方案：
- 仅在 `queue-tray` 或 `status-banner` 上单独补一次 `refresh(layout=True)`。
  不采用，因为高度残留并不只属于一个组件，局部补丁容易再次分叉生命周期。

### 2. 以父容器级别的二次布局重测作为收口点

决策：二次布局重测应落在 `#body` 或等价的统一父级，而不是让每个子组件分别决定是否重排。

原因：
- `status-banner`、timeline、`queue-tray`、输入区之间存在垂直空间竞争，单独刷新一个组件不一定能正确回收兄弟区域占位。
- 父容器级别的 layout pass 更符合“整体纵向收紧”的真实需求。

备选方案：
- 对每个 `Static` / `Input` 分别调用刷新。
  不采用，因为维护成本高，而且容易遗漏未来新增的 auto 高度区域。

### 3. 把滚动跟随与焦点恢复放在最终布局稳定之后

决策：`scroll_end`、follow-scroll 和输入框 focus 等依赖最终尺寸的动作，必须继续放在最终布局完成之后调度。

原因：
- 如果这些动作提前发生，可能再次触发不稳定的中间帧，破坏首轮或恢复后的稳定截图。
- 之前首帧一致性问题已经证明，任何依赖最终几何状态的动作都必须在稳定布局之后。

备选方案：
- 保持当前 `scroll_end` 时机不变，只额外补一次高度修正。
  不采用，因为这会让新旧时序混杂，后续排查困难。

## Risks / Trade-offs

- [Risk] 二次布局重测可能增加一次额外刷新，导致 resize 期间多一拍重绘。 → Mitigation：仅在统一 repaint 路径内集中执行，避免多组件重复触发。
- [Risk] 如果布局重测位置选得过大，可能引入不必要的闪烁。 → Mitigation：优先以 `#body` 为最小整体容器，而不是整个 `Screen`。
- [Risk] 高度恢复测试如果只检查截图，仍可能遗漏具体尺寸回归。 → Mitigation：同时保留截图断言和关键组件高度断言。

## Migration Plan

1. 调整统一 repaint 路径的顺序，使内容更新与最终 layout pass 不再倒置。
2. 为关键 auto 高度区域增加恢复后高度断言，确认横向缩窄再恢复能回到初始高度。
3. 运行聚焦 TUI 回归测试，验证宽度、高度和稳定截图三者都一致。

回滚策略：
- 如二次 layout pass 带来新的闪烁或滚动副作用，可先回滚为当前统一 repaint 实现，再单独定位高度测量与 follow-scroll 的相互影响。

## Open Questions

- 最终的二次布局重测落在 `#body` 还是整个 `App` 更稳，需要实现阶段通过实际截图与尺寸断言确认。
- 是否需要为 `queue-tray.display` 状态切换单独补一个“显示状态变化后再布局”的轻量 helper，可在实现时根据测试现象决定。
