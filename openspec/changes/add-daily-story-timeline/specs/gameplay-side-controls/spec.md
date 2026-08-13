## ADDED Requirements

### Requirement: Daily controls expose only daily actions
Daily gameplay controls SHALL expose save, rewrite-current-day, and regenerate-current-day actions without custom choice or next-round controls.

#### Scenario: Daily options are visible
- **WHEN** a current daily story and generated options are available
- **THEN** the player MUST be able to select an option, rewrite the current story, or regenerate the current day

#### Scenario: Choice has committed
- **WHEN** a daily choice settlement completes
- **THEN** the frontend MUST automatically request the next day rather than display a manual continuation control
