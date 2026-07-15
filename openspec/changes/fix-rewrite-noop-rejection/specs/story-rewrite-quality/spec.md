## ADDED Requirements

### Requirement: Successful rewrites have player-visible changes

The system SHALL reject a rewrite result that is equal to the submitted full story after
normalizing non-semantic whitespace.

#### Scenario: Provider returns the original story verbatim

- **GIVEN** a player submits a rewrite instruction for a nonempty story
- **WHEN** the provider returns that same story
- **THEN** the rewrite service raises `StoryRewriteFailure`
- **AND** the original story is not persisted as a rewritten result

#### Scenario: Provider changes only non-semantic whitespace

- **GIVEN** a player submits a rewrite instruction for a nonempty story
- **WHEN** the provider returns the same prose with only surrounding or blank-line whitespace changes
- **THEN** the rewrite service raises `StoryRewriteFailure`

### Requirement: No-op rewrites do not complete successfully over SSE

The streaming rewrite route SHALL emit an error rather than a successful complete event when
the rewrite service rejects a no-op result.

#### Scenario: Streamed rewrite returns an unchanged story

- **GIVEN** the rewrite generator reports a no-op rewrite failure
- **WHEN** the server streams the rewrite response
- **THEN** the response contains an error event
- **AND** it does not persist or emit the unchanged story as a successful result
