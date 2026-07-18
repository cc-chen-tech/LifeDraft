## ADDED Requirements

### Requirement: Audio element failure recovery remains actionable
The rendered music player SHALL mark a failed playable track as skipped, show
failure feedback, and attempt the next unskipped recommendation after its
scheduled recovery delay.

#### Scenario: Current track emits a browser audio error
- **GIVEN** a rendered player with two playable recommended tracks
- **WHEN** the current track's Audio element emits an error event
- **THEN** the failed track is reported as skipped
- **AND** the next track becomes the current playback target after the retry
  delay.

### Requirement: Autoplay rejection does not strand playback UI
The rendered music player SHALL clear transient song-switching state when an
Audio `play()` promise rejects, without treating the recommendation service as
unavailable.

#### Scenario: Browser rejects play attempt
- **GIVEN** a rendered player with a playable recommended track
- **WHEN** its Audio element rejects `play()`
- **THEN** the switching indicator is removed
- **AND** no recommendation-service-unavailable message is shown.
