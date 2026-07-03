## ADDED Requirements

### Requirement: `/stop` MUST request real runtime cancellation
SmartIPO TUI MUST treat `/stop` as a real runtime cancellation request. When a turn is active, the TUI MUST call the EasyHarness agent cancellation path for that active invocation and MUST NOT treat the turn as finished merely because the local UI worker received a cancel request.

#### Scenario: Active reply is stopped through the runtime
- **WHEN** the user executes `/stop` while a turn is actively streaming
- **THEN** the TUI MUST request cancellation from the active EasyHarness agent invocation
- **AND** the TUI MUST keep the turn in a stopping state until a real terminal stream outcome arrives

#### Scenario: Idle stop remains a no-op
- **WHEN** the user executes `/stop` while there is no active turn
- **THEN** the TUI MUST NOT call runtime cancellation
- **AND** the TUI MUST report that there is no active reply to stop

### Requirement: Cancelled turns MUST settle from runtime terminal events
SmartIPO TUI MUST treat `AgentEvent.status == "cancelled"` as a first-class terminal status. A cancelled turn MUST settle from the runtime event stream rather than from speculative local teardown.

#### Scenario: Assistant partial output survives cancellation
- **WHEN** the assistant has already streamed partial text and the active turn later reaches a cancelled terminal state
- **THEN** the already streamed assistant text MUST remain in the visible timeline
- **AND** the turn MUST close without clearing or overwriting that partial text

#### Scenario: Cancelled tool is not rendered as failed
- **WHEN** a tool has started and the turn is then cancelled before normal completion
- **THEN** the tool timeline item MUST settle into a cancelled or stopped terminal state
- **AND** the TUI MUST NOT relabel that tool run as a generic failure

#### Scenario: Late events from the stopped turn are ignored after settlement
- **WHEN** a turn has already been settled after cancellation and delayed events from that old turn arrive later
- **THEN** those delayed events MUST NOT mutate the active timeline or queue state of subsequent turns

### Requirement: User-initiated stop MUST leave a low-emphasis timeline marker
SmartIPO TUI MUST record a persistent timeline event when a reply is stopped by the user. That event MUST use English text and MUST render with low visual emphasis comparable to the temporary thinking activity.

#### Scenario: Timeline keeps a stopped marker after cancellation
- **WHEN** a running turn is successfully cancelled because the user issued `/stop`
- **THEN** the visible timeline MUST retain a persistent English stop marker such as `Reply stopped.`
- **AND** that marker MUST remain in the timeline after the turn has settled

#### Scenario: Stop marker does not replace assistant content
- **WHEN** a turn already has visible assistant or tool history before being stopped
- **THEN** the stop marker MUST be appended as a separate timeline fact
- **AND** it MUST NOT replace or erase previously rendered conversation content
