## ADDED Requirements

### Requirement: Expanded sound controls use one unified sound group

The global sound controls SHALL present scene music and story narration as peer controls from one "声音" entry point. Expanded detailed controls SHALL use a single "音乐和朗读" group rather than a nested standalone sound region.

#### Scenario: Music and narration are available together
- **Given** the current story has music context and an active reading context
- **When** the user expands the global sound controls
- **Then** the UI SHALL expose one global sound region named "声音"
- **And** the expanded content SHALL expose one group named "音乐和朗读"
- **And** the collapsed mini bar SHALL be replaced by the expanded panel header while the group is open
- **And** the expanded panel header SHALL expose an action named "收起声音"
- **And** that group SHALL contain a peer channel group named "背景音乐"
- **And** that group SHALL contain a peer channel group named "故事朗读"
- **And** the UI SHALL NOT expose nested regions named "声音控制" or "声音面板"
- **And** the embedded scene music controls SHALL not render their own outer card shell, recommendation list, or mood chips
- **And** the embedded story narration controls SHALL not render as a separate region, bordered card, or separate top-divided control strip.

#### Scenario: Expanded sound panel uses a lightweight mixer layout
- **Given** scene music and story narration are both available
- **When** the user expands the global sound controls
- **Then** the expanded surface SHALL use one sound mixer layout
- **And** the mixer SHALL expose one compact sound overview row with the current music state and current narration state
- **And** the scene music and story narration sections SHALL be visually grouped as compact sibling mixer channel rows
- **And** the scene music and story narration channel labels SHALL be exposed as semantic channel group names
- **And** the expanded UI SHALL NOT repeat the collapsed bar title as an extra "声音控制" header
- **And** the expanded UI SHALL NOT introduce another "声音面板" landmark around the channel rows
- **And** embedded channel labels SHALL use the explicit labels "背景音乐" and "故事朗读"
- **And** duplicate child module headings such as "音乐" and "朗读" SHALL NOT appear inside the channel bodies
- **And** the channel groups SHALL use one shared vertical channel list instead of a two-column grid or stacked standalone modules
- **And** the panel SHALL NOT present music and narration as separate standalone toolbars.
- **And** music and narration status text SHALL appear in the shared overview only, not be duplicated as per-channel status badges.
- **And** auto-read mode SHALL be controlled only by the narration channel switch, not repeated in the shared overview.

#### Scenario: Embedded narration controls are grouped
- **Given** story narration controls are shown inside the expanded sound panel
- **When** the user inspects the narration section
- **Then** the primary narration action and optional stop action SHALL be grouped together
- **And** voice selection plus auto-read SHALL be grouped as settings
- **And** changing these controls SHALL continue to use the existing narration state machine and persisted settings.

### Requirement: Collapsed sound controls stay simple

The collapsed global sound controls SHALL act as one sound-panel entry point while preserving a single direct music play/pause action when playable music is already available. Detailed music controls, narration playback, voice selection, and auto-read settings SHALL live in the expanded sound panel.

#### Scenario: Current story can play music and be narrated
- **Given** the current story has music context and an active reading context
- **When** the global sound controls are collapsed
- **Then** the collapsed control bar SHALL expose an action named "展开声音"
- **And** the collapsed control bar SHALL show a compact channel summary for "背景音乐"
- **And** the collapsed control bar SHALL show a compact channel summary for "故事朗读"
- **And** the collapsed control bar SHALL expose at most one music play or pause action when a controllable audio element exists
- **And** when music exists but a controllable audio element has not initialized, that music action SHALL open the expanded sound group instead of pretending to start playback
- **And** the collapsed control bar SHALL NOT expose narration actions
- **And** selecting the collapsed sound action SHALL expand the unified "音乐和朗读" group
- **And** selecting the direct music action SHALL toggle music without opening the expanded group
- **And** detailed voice, auto-read, and music playback settings SHALL remain available inside the expanded group.

#### Scenario: Narration audio is ready but not playing
- **Given** backend narration audio has been generated
- **And** playback has not started yet
- **When** the story narration controls are shown
- **Then** the primary narration action SHALL be "play"
- **And** the controls SHALL NOT show a stop action until narration is loading, playing, or paused.

### Requirement: Music refresh errors do not contradict active playback

Music recommendation refresh failures SHALL not present a blocking unavailable state when the current music channel still has a playable song.

#### Scenario: Current music is playable while a new recommendation fails
- **Given** the music channel has a current playable song
- **And** a recommendation refresh reports an error
- **When** the sound panel renders the embedded music channel
- **Then** the UI SHALL continue to show the current playable song
- **And** the UI SHALL NOT show the blocking text "音乐服务暂不可用"
- **And** the UI SHALL show a non-blocking status that the new recommendation is unavailable and current music continues.
