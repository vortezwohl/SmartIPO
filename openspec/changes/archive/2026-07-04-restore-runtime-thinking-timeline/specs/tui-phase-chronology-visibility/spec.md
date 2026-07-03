## ADDED Requirements

### Requirement: Tool activity MUST preserve prior visible thinking history
SmartIPO TUI MUST preserve real thinking history that has already become visible for a turn when later tool activity begins or completes.

#### Scenario: Tool phase follows visible thinking instead of replacing it
- **WHEN** a turn has already surfaced visible runtime thinking content and a tool `started` event arrives for that same turn
- **THEN** the timeline MUST keep the earlier thinking content visible
- **AND** the tool activity MUST appear after that thinking history in chronological order

#### Scenario: Tool completion keeps the earlier thinking history intact
- **WHEN** a tool completes after visible runtime thinking content was already shown for the same turn
- **THEN** the timeline MUST still contain the earlier thinking history
- **AND** the completed tool summary MUST be rendered as a later phase of the same turn rather than overwriting the thinking content

### Requirement: Final assistant reply MUST append after prior turn phases
Once a turn has produced visible thinking history or tool history, the final assistant reply MUST enter the timeline as a later message for that turn instead of reusing and overwriting an earlier phase entry.

#### Scenario: Assistant reply follows thinking and tool chronology
- **WHEN** a turn has visible thinking history, then tool activity, and later receives assistant output
- **THEN** the final assistant reply MUST be appended after the prior visible phases in timeline order
- **AND** the earlier thinking and tool history MUST remain visible

#### Scenario: Assistant reply follows visible thinking without a tool phase
- **WHEN** a turn has visible runtime thinking history and then directly receives assistant output without any tool event
- **THEN** the final assistant reply MUST appear after the visible thinking history
- **AND** the assistant reply MUST NOT overwrite or collapse the earlier thinking content into the same history entry
