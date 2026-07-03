## ADDED Requirements

### Requirement: Runtime thinking history MUST use a distinct assistant-thinking prefix
When SmartIPO TUI surfaces real runtime thinking text as preserved history, it MUST label that history with a prefix that distinguishes it from final assistant replies.

#### Scenario: Thinking history uses the assistant-thinking prefix
- **WHEN** an active turn receives non-empty runtime `thinking delta` or `thinking completed` text and that text becomes visible history
- **THEN** the visible timeline MUST render that history with the prefix `Assistant (Thinking) > `
- **AND** the TUI MUST NOT label that history with the normal final-reply prefix `Assistant > `

#### Scenario: Final assistant reply keeps the normal assistant prefix
- **WHEN** a turn later receives final assistant output after visible thinking history already exists
- **THEN** the final assistant reply MUST still render with the prefix `Assistant > `
- **AND** the earlier thinking history MUST keep the prefix `Assistant (Thinking) > `

### Requirement: Runtime thinking history MUST render with lower visual emphasis than final replies
SmartIPO TUI MUST render preserved thinking history with a darker visual treatment than normal assistant replies so users can distinguish reasoning text from final output at a glance.

#### Scenario: Thinking history uses darker prefix and body colors
- **WHEN** visible runtime thinking history is rendered in the timeline
- **THEN** the thinking-history prefix color MUST be darker than the normal assistant prefix color
- **AND** the thinking-history body text color MUST be darker than the normal assistant body text color

#### Scenario: Thinking history remains readable on the current dark background
- **WHEN** the thinking-history message is shown in the timeline
- **THEN** the darker treatment MUST still keep the text readable on the existing dark theme
- **AND** the TUI MUST NOT reduce the message to a hidden, disabled, or nearly invisible state

### Requirement: Waiting-only thinking MUST remain visually distinct from preserved thinking history
The temporary local `Thinking ...` waiting indicator MUST remain a separate visual state from preserved runtime thinking history.

#### Scenario: Waiting-only placeholder keeps the temporary thinking style
- **WHEN** a turn is only showing the local waiting indicator before any non-empty runtime thinking text arrives
- **THEN** the timeline MUST continue rendering that state as `Thinking ...`
- **AND** the TUI MUST NOT upgrade that placeholder to `Assistant (Thinking) > ` until real runtime thinking text exists

#### Scenario: First real thinking text upgrades waiting to preserved thinking history
- **WHEN** a local `Thinking ...` waiting placeholder is visible and the first non-empty runtime thinking text arrives
- **THEN** the TUI MUST replace the waiting-only visual treatment with the preserved thinking-history treatment
- **AND** the visible history MUST use `Assistant (Thinking) > ` with the darker thinking-history style
