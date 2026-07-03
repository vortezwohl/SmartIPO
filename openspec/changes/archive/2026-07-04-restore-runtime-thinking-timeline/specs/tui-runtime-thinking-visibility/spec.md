## ADDED Requirements

### Requirement: Runtime thinking text MUST surface through the assistant conversation surface
When EasyHarness emits real `thinking` text for an active turn, SmartIPO TUI MUST expose that text in the visible conversation timeline instead of keeping it as an internal activity-only state.

#### Scenario: Runtime thinking delta becomes visible conversation content
- **WHEN** the active turn receives `thinking started` followed by one or more `thinking delta` events with non-empty `text`
- **THEN** the visible timeline MUST show the accumulated thinking text through the assistant conversation surface
- **AND** later `thinking delta` events MUST extend the same visible thinking content
- **AND** the UI MUST NOT leave that content as a bare `Thinking ...` placeholder line

#### Scenario: Runtime thinking completed remains visible after the phase ends
- **WHEN** the active turn receives a `thinking completed` event with non-empty final text
- **THEN** the completed thinking content MUST remain in the timeline as visible history for that turn
- **AND** the TUI MUST NOT delete that history merely because the thinking phase has ended

### Requirement: Provisional waiting MUST stay distinct from real runtime thinking
SmartIPO TUI MUST distinguish a local provisional waiting indicator from real runtime thinking content so that only empty waiting markers are disposable.

#### Scenario: First real thinking text upgrades the provisional waiting state
- **WHEN** a local provisional `Thinking ...` waiting indicator is visible and the first real `thinking delta` with non-empty text arrives
- **THEN** the TUI MUST stop treating that state as disposable waiting-only UI
- **AND** the visible output MUST switch to persistent thinking content for the active turn

#### Scenario: Waiting-only indicator can disappear when no runtime thinking text ever arrived
- **WHEN** a turn displayed a provisional `Thinking ...` indicator but never received any non-empty runtime `thinking` text before tool or assistant output began
- **THEN** the waiting-only indicator MUST be removable from visible history
- **AND** the TUI MUST NOT preserve that empty waiting marker as a completed conversation message
