## ADDED Requirements

### Requirement: TUI 恢复原宽后 auto 高度区域必须回到初始紧凑高度
SmartIPO TUI MUST 保证终端窗口在横向缩窄后再恢复到原始宽度时，`status-banner`、`queue-tray` 以及其他依赖内容测量的 auto 高度关键区域回到与首次稳定界面一致的紧凑高度，不得保留窄宽度阶段被撑大的垂直空白。

#### Scenario: status banner 在恢复宽度后回到初始高度
- **WHEN** 用户把终端从初始宽度缩窄，再恢复到原始宽度
- **THEN** `status-banner` 的最终高度 MUST 与初始稳定状态一致

#### Scenario: queue tray 在恢复宽度后回到初始高度
- **WHEN** 队列托盘在窄宽度阶段因内容换行导致高度增长，随后终端宽度恢复
- **THEN** `queue-tray` 的最终高度 MUST 回收到与恢复前原始宽度一致的稳定高度

#### Scenario: 恢复后的整体界面与初始稳定截图等价
- **WHEN** 用户把终端横向缩窄后再恢复到原始宽度
- **THEN** 关键区域的边框、背景和垂直间距 MUST 与初始稳定界面等价

