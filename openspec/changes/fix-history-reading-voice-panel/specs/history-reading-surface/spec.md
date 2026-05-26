## ADDED Requirements

### Requirement: History text is read in an unobstructed surface
The system SHALL display selected historical story text in a dedicated readable surface that is not covered by current-round actions, drawers, voice controls, or scene-image panels.

#### Scenario: Select historical round from sidebar
- **WHEN** the user selects a historical round from the history sidebar
- **THEN** the historical story text MUST remain visible in the main reading area
- **AND** current-round action controls MUST NOT cover the historical story text

#### Scenario: Historical image exists
- **WHEN** the selected historical round has a scene image
- **THEN** the image controls MUST render after the historical story text rather than before or on top of it

### Requirement: History mode exits only by explicit return
The system SHALL keep the selected historical round pinned until the user explicitly returns to the current story.

#### Scenario: Close history sidebar while reading historical story
- **WHEN** the history sidebar closes after a historical round has been selected
- **THEN** the main reading area MUST continue to show the selected historical story

#### Scenario: Return to current story
- **WHEN** the user activates the return-to-current control
- **THEN** the main reading area MUST switch back to the latest current story and restore current-round options when available
