## ADDED Requirements

### Requirement: TUI 必须尊重宿主终端原生底板
SmartIPO TUI MUST 把宿主终端的默认背景视为应用底板。系统 MUST NOT 通过整屏或主容器级背景色覆盖终端原生底色。

#### Scenario: 大容器不覆盖终端底色
- **WHEN** TUI 渲染 `Screen`、主容器或主消息区等大面积基础区域
- **THEN** 系统 MUST 让这些区域继续使用宿主终端原生底色
- **AND** SmartIPO 主题色 MUST 仅用于边框、焦点或局部强调元素

### Requirement: 主题强调必须是轻量而非铺底
SmartIPO TUI MUST 使用浅绿色作为边框、焦点和轻强调色，而不是用大面积主题底色铺满界面。

#### Scenario: 强调色用于局部元素
- **WHEN** 系统渲染边框、输入焦点或局部消息泡泡
- **THEN** 这些元素 MAY 使用浅绿色强调
- **AND** 主要正文文字 MUST 保持可读的高对比显示

