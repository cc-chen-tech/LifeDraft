## MODIFIED Requirements

### Requirement: History review remains pinned to the selected round
The system SHALL keep history review pinned to the selected historical story day until the user explicitly returns to the current day.

#### Scenario: Select historical day while current story updates
- **WHEN** the user selects a historical day while current generation continues
- **THEN** the visible text and media MUST remain pinned to the selected day

#### Scenario: Return to current day
- **WHEN** the user activates return-to-current
- **THEN** the visible story and options MUST switch to the latest current daily state

### Requirement: History review is read-only
The system SHALL prevent gameplay choices and story-editing actions from mutating a completed historical day.

#### Scenario: Viewing historical day
- **WHEN** the user is viewing a completed day
- **THEN** choices, rewrite, and regenerate controls MUST be hidden or disabled

### Requirement: Historical scene images match the selected round
The system SHALL display scene images keyed by the selected daily `game_id`, `story_date`, and `day_index`, with legacy week/round lookup retained for unmigrated rows.

#### Scenario: Daily historical image exists
- **WHEN** the selected historical day has a daily scene image
- **THEN** that image MUST be displayed with the selected day's text

#### Scenario: Only a legacy image exists
- **WHEN** migrated history references an unmigrated legacy scene image
- **THEN** compatibility lookup MUST return the matching legacy image without assigning it to another day

### Requirement: Scene images are keyed by stage
Daily games SHALL use a single story-stage image for the current or historical day; legacy games MAY retain event/result stage images.

#### Scenario: Current daily story is visible
- **WHEN** the current day has a story image
- **THEN** the UI MUST display the daily story-stage image and MUST NOT request a separate choice-result image
