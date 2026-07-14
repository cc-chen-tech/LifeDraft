## ADDED Requirements

### Requirement: Maintained gate validates restored scene-image storage state
The maintained backend selection SHALL use a real database and local temporary storage to mark missing recent scene images while preserving valid images.

#### Scenario: Saved scene image file is missing
- **WHEN** session restoration inspects a persisted scene image whose local path is absent
- **THEN** the maintained contract MUST require its importance score to become `missing`
