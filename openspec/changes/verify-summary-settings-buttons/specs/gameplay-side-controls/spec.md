## ADDED Requirements

### Requirement: Header Settings Opens Only Settings Controls

The gameplay header settings control SHALL open settings-related menu controls and SHALL NOT open the story assistant.

#### Scenario: User clicks settings

- **WHEN** the player clicks the header `设置` button
- **THEN** the UI MUST show settings menu entries such as `叙事质量` and `叙事风格`
- **AND** the UI MUST NOT show the story assistant input placeholder `向剧情助手提问`.

### Requirement: Summary Opens Dedicated Summary Panel

Summary controls SHALL open a dedicated summary panel and SHALL NOT route through the story assistant chat surface.

#### Scenario: User clicks collapsed summary action

- **WHEN** the player clicks the collapsed `人生总结` action
- **THEN** the UI MUST show the dedicated life-summary panel
- **AND** the story assistant chat panel MUST remain closed.
