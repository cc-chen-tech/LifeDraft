## ADDED Requirements

### Requirement: Expanded sound controls use one unified panel

The expanded global sound controls SHALL present scene music and story narration as peer controls inside one sound panel.

#### Scenario: Music and narration are available together
- **Given** the current story has music context and an active reading context
- **When** the user expands the global sound controls
- **Then** the UI SHALL expose one expanded sound panel
- **And** that panel SHALL contain a scene music section
- **And** that panel SHALL contain a story narration section
- **And** the panel SHALL be the only expanded sound region
- **And** the embedded scene music controls SHALL not render their own outer card shell
- **And** the embedded story narration controls SHALL not render as a separate region, bordered card, or separate top-divided control strip.

### Requirement: Collapsed sound controls stay simple

The collapsed global sound controls SHALL expose a single primary sound action plus an expand or collapse action.

#### Scenario: Current story can play music and be narrated
- **Given** the current story has music context and an active reading context
- **When** the global sound controls are collapsed
- **Then** the collapsed control bar SHALL expose a music play or pause action
- **And** the collapsed control bar SHALL NOT expose a separate narration action
- **And** the expand action SHALL remain available for detailed voice, auto-read, and music settings.

#### Scenario: Narration audio is ready but not playing
- **Given** backend narration audio has been generated
- **And** playback has not started yet
- **When** the story narration controls are shown
- **Then** the primary narration action SHALL be "play"
- **And** the controls SHALL NOT show a stop action until narration is loading, playing, or paused.
