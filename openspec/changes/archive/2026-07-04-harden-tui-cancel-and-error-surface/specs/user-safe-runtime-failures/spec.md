## ADDED Requirements

### Requirement: Primary timeline failure messages MUST be user-safe summaries
SmartIPO TUI MUST summarize runtime and tool failures for the primary conversation timeline. The default visible failure message MUST be concise, readable, and oriented toward end users rather than raw debugging output.

#### Scenario: Tool failure shows concise summary
- **WHEN** a tool fails and the underlying event payload includes both a short error string and richer diagnostic detail
- **THEN** the primary timeline MUST show a concise failure summary
- **AND** the summary MUST NOT require the user to read stack frames or internal library paths

#### Scenario: Runtime failure shows concise summary
- **WHEN** the active turn ends with a non-cancelled runtime failure
- **THEN** the timeline MUST display a compact failure message for the user
- **AND** the visible message MUST avoid dumping the raw exception stack into the main chat flow

### Requirement: Raw diagnostics MUST remain available outside the default timeline surface
SmartIPO MUST preserve complete failure diagnostics for agent reasoning, internal debugging, and tests even when the primary timeline hides them from the user-facing conversation view.

#### Scenario: Tool traceback is retained but not rendered by default
- **WHEN** a failed tool event carries traceback-level diagnostic detail
- **THEN** the TUI or runtime state MUST retain that raw diagnostic detail in internal metadata or equivalent non-primary storage
- **AND** the primary timeline MUST NOT render that traceback by default

#### Scenario: Failure tests can still inspect full diagnostics
- **WHEN** automated tests or internal debugging paths need the original diagnostic payload
- **THEN** the system MUST provide access to the retained raw failure detail
- **AND** that access MUST NOT depend on re-enabling raw traceback rendering in the main timeline

### Requirement: Failure rendering MUST distinguish user stop from real errors
SmartIPO TUI MUST keep user-initiated cancellation separate from genuine runtime or tool failures. A stopped turn MUST NOT be summarized as an error, and an actual error MUST NOT masquerade as a user stop.

#### Scenario: User stop is not shown as failure
- **WHEN** the active turn ends because the user issued `/stop`
- **THEN** the timeline MUST render a stop marker rather than a failure summary
- **AND** the UI MUST NOT describe that outcome as an error

#### Scenario: Real tool error remains visible as an error
- **WHEN** a tool or runtime path truly fails without user cancellation
- **THEN** the timeline MUST still make the error outcome visible
- **AND** it MUST do so with a concise error summary instead of a stop marker
