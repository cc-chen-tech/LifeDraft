## ADDED Requirements

### Requirement: Gameplay Side Controls Have Stable Accessible Names

Icon-only gameplay controls SHALL expose stable accessible names so users, assistive technology, and browser-driven tests can target them reliably.

#### Scenario: Global music mini controls are collapsed
- **Given** the global music player mini bar is visible
- **When** the player is not expanded
- **Then** the play control SHALL expose whether it will play music or open the picker
- **And** the expand control SHALL expose that it expands the music player.
