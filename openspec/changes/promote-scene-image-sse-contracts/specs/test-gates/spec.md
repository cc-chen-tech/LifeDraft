## ADDED Requirements

### Requirement: Maintained gates cover scene-image SSE contracts
The maintained backend test and coverage workflows SHALL include the scene-image SSE contract suite that verifies ready and failed payload fields, authentication, and game ownership through the application HTTP boundary.

#### Scenario: Client-visible scene-image payload regression
- **WHEN** a scene-image SSE ready or failed event omits a frontend-required field
- **THEN** the maintained backend gate MUST fail before release-only validation

#### Scenario: Scene-image event access-control regression
- **WHEN** an unauthenticated request or another user's request can read scene-image events
- **THEN** the maintained backend gate MUST fail before release-only validation

### Requirement: Maintained workflow selections remain equivalent
The maintained backend test workflow and maintained coverage workflow SHALL select the scene-image SSE contract suite exactly once and in the same order.

#### Scenario: Workflow selection review
- **WHEN** the scene-image SSE suite is added to a maintained workflow
- **THEN** both workflows MUST contain the same path-list entry
