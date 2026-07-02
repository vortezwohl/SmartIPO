## ADDED Requirements

### Requirement: UI layers do not define tool protocol semantics
TUI, WebUI, and other presentation layers SHALL consume tool events and render user-facing state, but they SHALL NOT define or explain tool protocol semantics such as parameter meaning, result contract structure, or retry contract rules.

#### Scenario: UI renders runtime events without redefining protocol
- **WHEN** a UI surface receives tool lifecycle events and tool result payloads from the runtime
- **THEN** it SHALL render status, preview, detail, and localized user-facing text without introducing its own tool protocol definitions

### Requirement: Application composition owns default agent assembly
Default system prompts, default tool sets, default model selection, and default session or agent assembly SHALL live in an application composition layer rather than inside a concrete UI package.

#### Scenario: UI receives a precomposed agent entrypoint
- **WHEN** the TUI or a future WebUI starts a default SmartIPO agent session
- **THEN** it SHALL obtain that session or agent from a composition entrypoint instead of constructing the full default stack inside the UI module

### Requirement: Core timeline semantics remain cross-UI
The conversation timeline state model and runtime event schema SHALL remain UI-agnostic so that multiple UI surfaces can reuse the same semantic state transitions.

#### Scenario: Two UI surfaces share the same timeline reducer
- **WHEN** TUI and WebUI consume the same runtime event stream
- **THEN** both UI surfaces SHALL be able to reuse the same core timeline semantics without copying or forking the reducer logic
