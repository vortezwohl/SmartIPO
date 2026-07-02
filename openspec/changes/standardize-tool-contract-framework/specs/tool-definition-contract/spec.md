## ADDED Requirements

### Requirement: Structured tool definitions
The tool framework SHALL require every tool to be defined through a structured definition contract instead of a freeform provider description string alone.

#### Scenario: Provider description is generated from structured fields
- **WHEN** a tool is registered with identity, documentation sections, input schema, and handler metadata
- **THEN** the framework SHALL generate the provider-facing description from the structured documentation contract

#### Scenario: Missing documentation sections are rejected
- **WHEN** a tool omits a required documentation section such as purpose, parameters, returns, or common failures
- **THEN** the framework SHALL reject the tool definition during validation

### Requirement: Tool contract output uses English
The tool framework SHALL require provider-facing descriptions, documented parameter names, documented return field names, and documented error identifiers in the tool contract layer to be authored in English.

#### Scenario: Non-English contract content is rejected
- **WHEN** a tool definition contains non-English contract content in provider-facing description sections or documented result/error identifiers
- **THEN** the framework SHALL fail validation before the tool can be exposed to the runtime

### Requirement: Schema and documentation stay aligned
The tool framework SHALL validate that every public input field exposed through the tool schema has a matching structured parameter description in the tool contract.

#### Scenario: Schema field has no contract documentation
- **WHEN** a tool schema exposes a public field that is not documented in the structured parameter section
- **THEN** the framework SHALL reject the tool definition during catalog validation

#### Scenario: Documented field is not present in schema
- **WHEN** a tool contract documents a public input field that is not exposed by the tool schema
- **THEN** the framework SHALL reject the tool definition during catalog validation
