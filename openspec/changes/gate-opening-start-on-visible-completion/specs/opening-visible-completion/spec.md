## ADDED Requirements

### Requirement: Opening navigation waits for visible completion
The opening page SHALL make `开始我的人生` actionable only after the backend has delivered the final opening story and the typewriter surface has visibly rendered that complete text.

#### Scenario: Complete event arrives while typing continues
- **WHEN** the SSE complete event supplies a final story longer than the currently visible text
- **THEN** the start control SHALL remain unavailable
- **AND** it SHALL become available only after the complete final story is visible

#### Scenario: Existing completed opening story
- **WHEN** the page loads a previously persisted opening story without an active stream
- **THEN** the full story SHALL render immediately
- **AND** the start control SHALL be available after that render completes

### Requirement: Completion state is attempt scoped
The opening page MUST reset visible completion when a retry begins or the active story text is replaced.

#### Scenario: Retry after completion
- **WHEN** a completed opening is retried and the old story is cleared
- **THEN** the prior visible-completion signal SHALL NOT enable navigation for the retry

### Requirement: Browser gate covers the visible boundary
The project E2E gate SHALL execute a no-mock browser test that observes the start control across the final typewriter interval.

#### Scenario: E2E visible completion
- **WHEN** `test.sh e2e` streams a deterministic opening story
- **THEN** the test SHALL verify navigation is unavailable before the last character appears and available afterward
