## ADDED Requirements

### Requirement: Expanded sound controls use one unified sound group

The global sound controls SHALL present scene music and story narration as peer controls from one "声音" entry point. Expanded detailed controls SHALL use a single "音乐和朗读" group rather than a nested standalone sound region.

#### Scenario: Music and narration are available together
- **Given** the current story has music context and an active reading context
- **When** the user expands the global sound controls
- **Then** the UI SHALL expose one global sound region named "声音"
- **And** the expanded content SHALL expose one group named "音乐和朗读"
- **And** that group SHALL contain a scene music section
- **And** that group SHALL contain a story narration section
- **And** the UI SHALL NOT expose nested regions named "声音控制" or "声音面板"
- **And** the embedded scene music controls SHALL not render their own outer card shell
- **And** the embedded story narration controls SHALL not render as a separate region, bordered card, or separate top-divided control strip.

#### Scenario: Expanded sound panel uses a lightweight mixer layout
- **Given** scene music and story narration are both available
- **When** the user expands the global sound controls
- **Then** the expanded surface SHALL use one sound mixer layout
- **And** the mixer SHALL expose one compact sound overview row with the current music state, current narration state, and auto-read mode
- **And** the scene music and story narration sections SHALL be visually grouped as sibling channel rows
- **And** the scene music and story narration channel labels SHALL be semantic section headings
- **And** the expanded UI SHALL NOT repeat the collapsed bar title as an extra "声音控制" header
- **And** the expanded UI SHALL NOT introduce another "声音面板" landmark around the channel rows
- **And** embedded channel labels SHALL use the concise labels "音乐" and "朗读"
- **And** the channel rows SHALL use lightweight dividers instead of nested card borders or nested card backgrounds
- **And** the panel SHALL NOT present music and narration as separate standalone toolbars.

#### Scenario: Embedded narration controls are grouped
- **Given** story narration controls are shown inside the expanded sound panel
- **When** the user inspects the narration section
- **Then** the primary narration action and optional stop action SHALL be grouped together
- **And** voice selection plus auto-read SHALL be grouped as settings
- **And** changing these controls SHALL continue to use the existing narration state machine and persisted settings.

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
