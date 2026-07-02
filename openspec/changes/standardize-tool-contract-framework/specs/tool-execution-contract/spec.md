## ADDED Requirements

### Requirement: Tool results separate model and UI channels
The tool runtime SHALL preserve distinct result channels for model-facing text, UI-facing preview/detail text, and structured raw data.

#### Scenario: Model receives full model-facing text
- **WHEN** a tool completes with structured result data and model-facing text
- **THEN** the runtime SHALL return the model-facing text to the model instead of collapsing the result to a short preview summary

#### Scenario: UI receives preview and detail separately
- **WHEN** a tool completes with preview and detail result channels
- **THEN** the UI-facing event payload SHALL expose preview text and detail text as separate fields

### Requirement: Tool failures use a structured error contract
The tool runtime SHALL normalize tool failures into a structured error contract with a stable English error code, a model-facing error message, optional retry guidance, and raw diagnostic text.

#### Scenario: Recoverable failure returns retry guidance
- **WHEN** a tool fails in a recoverable way such as a path contract violation or a missing target
- **THEN** the runtime SHALL return a stable error code, a model-facing error message, and a retry hint that tells the model how to retry

#### Scenario: Raw diagnostics remain available
- **WHEN** a tool failure is emitted to the runtime event stream
- **THEN** the event payload SHALL preserve the raw diagnostic text separately from the model-facing error message

### Requirement: Reusable tool policies are framework-level components
The tool framework SHALL support reusable policy and formatter components that can be attached to multiple tools without introducing UI-layer dependencies.

#### Scenario: Shared path policy is reused by multiple tools
- **WHEN** two or more tools rely on the same scoped path normalization rules
- **THEN** the framework SHALL allow them to share one common policy component instead of duplicating path handling logic in each tool

#### Scenario: Shared formatter stays UI-agnostic
- **WHEN** a shared result formatter is used by a tool
- **THEN** the formatter SHALL not depend on TUI, WebUI, or any concrete presentation component
