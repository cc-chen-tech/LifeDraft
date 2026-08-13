## ADDED Requirements

### Requirement: Story analysis parsing is maintained
The maintained backend workflows SHALL execute provider-free StoryAnalyzer parsing contracts.

#### Scenario: Model response lifecycle regression
- **WHEN** analysis output contains new, replacement, invalidated, and scheduled state records
- **THEN** parsing preserves valid state, provenance, and actionable time coordinates while filtering invalid records.
