## MODIFIED Requirements

### Requirement: Gameplay Side Controls Have Stable Accessible Names

Icon-only gameplay controls SHALL expose stable accessible names so users, assistive technology, and browser-driven tests can target them reliably.

#### Scenario: Global music mini controls are collapsed

- **Given** the global music player mini bar is visible
- **When** the player is not expanded
- **Then** the play control SHALL expose whether it will play music or open the picker
- **And** the expand control SHALL expose that it expands the music player.

### Requirement: Life Summary Uses A Dedicated Summary Surface

The gameplay "人生总结" control SHALL generate and display a life summary in a summary-specific UI surface and SHALL NOT open the story assistant chat panel as a side effect.

#### Scenario: Collapsed life summary quick action

- **Given** the chat bar is collapsed
- **When** the user clicks "人生总结"
- **Then** the summary API SHALL be requested for the current game
- **And** a dedicated life summary panel SHALL be visible
- **And** the story assistant panel SHALL NOT be visible
- **And** the story assistant input SHALL NOT be visible.

#### Scenario: Life summary request fails

- **Given** the chat bar is collapsed
- **When** the user clicks "人生总结" and the summary API fails
- **Then** the dedicated life summary panel SHALL remain visible
- **And** the panel SHALL show a summary-specific error message
- **And** the story assistant panel SHALL NOT be visible.
