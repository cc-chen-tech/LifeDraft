## ADDED Requirements

### Requirement: Opening Generation Timeout Is Recoverable

When opening story generation times out after a game has been created, the system SHALL persist a recoverable error state for that game rather than leaving the player on a permanent loading screen.

#### Scenario: Retry times out after character creation
- **Given** a game exists for a newly created character
- **When** opening generation fails with a timeout
- **Then** `/play` SHALL render an actionable recovery state with retry or resume controls
- **And** it SHALL NOT render only `故事生成中...` without story text, options, or recovery controls.

### Requirement: Refresh Restores Current Generation State

The play page SHALL restore the latest persisted generation state after browser refresh or direct navigation to `/play`.

#### Scenario: User refreshes during a partial generation
- **Given** story text has been persisted but choices are still pending
- **When** the user reloads `/play`
- **Then** the persisted story text SHALL remain visible
- **And** the UI SHALL show that choices are pending or retryable.

### Requirement: Recovery Controls Remain Until Ready

Recovery controls SHALL remain visible until playable story content is restored.

#### Scenario: Resume action does not complete immediately
- **Given** the page shows a `恢复当前进度` control
- **When** the user clicks it and recovery is still pending
- **Then** the UI SHALL keep an actionable recovery or retry control visible
- **And** it SHALL NOT replace the page with only `故事生成中...`.

#### Scenario: Persisted story has no playable options
- **Given** the play page has restored story text from a previous or partial generation
- **And** the current phase is still loading, generating, or choosing
- **And** no choices or continue action are available
- **Then** the UI SHALL keep an actionable recovery control visible alongside the story text
- **And** it SHALL NOT require a browser refresh before the player can retry recovery.
