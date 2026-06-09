## ADDED Requirements

### Requirement: Expanded sound controls use one unified panel

The expanded global sound controls SHALL present scene music and story narration as peer controls inside one sound panel.

#### Scenario: Music and narration are available together
- **Given** the current story has music context and an active reading context
- **When** the user expands the global sound controls
- **Then** the UI SHALL expose one expanded sound panel
- **And** that panel SHALL contain a scene music section
- **And** that panel SHALL contain a story narration section
- **And** the embedded story narration controls SHALL not render as a separate bordered card or separate top-divided control strip.

#### Scenario: Expanded sound panel uses a mixer layout
- **Given** scene music and story narration are both available
- **When** the user expands the global sound controls
- **Then** the expanded surface SHALL use a single card-based sound mixer layout
- **And** the scene music and story narration sections SHALL be visually grouped as sibling cards
- **And** the panel SHALL NOT present music and narration as a `divide-y` stack of standalone toolbars.

#### Scenario: Embedded narration controls are grouped
- **Given** story narration controls are shown inside the expanded sound panel
- **When** the user inspects the narration section
- **Then** the primary narration action and optional stop action SHALL be grouped together
- **And** voice selection plus auto-read SHALL be grouped as settings
- **And** changing these controls SHALL continue to use the existing narration state machine and persisted settings.

### Requirement: Collapsed sound controls expose music and narration actions

The collapsed global sound controls SHALL expose scene music and story narration as sibling actions when both contexts are available.

#### Scenario: Current story can play music and be narrated
- **Given** the current story has music context and an active reading context
- **When** the global sound controls are collapsed
- **Then** the collapsed control bar SHALL expose a music play or pause action
- **And** it SHALL expose a narration action without requiring the user to expand the panel first
- **And** activating the narration action SHALL start, pause, resume, retry, or reveal ready narration according to the current reading state
- **And** the expand action SHALL remain available for detailed voice and music settings.

#### Scenario: Narration audio is ready but not playing
- **Given** backend narration audio has been generated
- **And** playback has not started yet
- **When** the story narration controls are shown
- **Then** the primary narration action SHALL be "play"
- **And** the controls SHALL NOT show a stop action until narration is loading, playing, or paused.
