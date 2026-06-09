## ADDED Requirements

### Requirement: Inline Rewrite Completion Syncs Current Event

Inline story rewrite completion SHALL make the rewritten story authoritative for both visible story text and the active current event.

#### Scenario: Rewrite completes from the play page
- **WHEN** the player submits the inline rewrite sheet
- **AND** the rewrite SSE stream completes with a rewritten story
- **THEN** the play page MUST update the visible story text
- **AND** the active current event story MUST be replaced with the rewritten story
- **AND** existing current event options MUST be preserved
