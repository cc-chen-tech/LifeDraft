## ADDED Requirements

### Requirement: Playlist queue state is maintained

The maintained backend suite SHALL validate title-family deduplication,
generated-track placement, persisted playback synchronization, advancement, and
wraparound without contacting a music provider.

#### Scenario: Recommendation refresh preserves the current song

- **WHEN** a current song exists and recommendations include duplicate IDs or
  equivalent title variants
- **THEN** the current song remains unchanged and the replacement queue contains
  only distinct upcoming title families

#### Scenario: Generated music is played next without interruption

- **WHEN** a generated track is added to a playlist with a current song
- **THEN** it becomes the first upcoming item and duplicate generated entries
  are removed

#### Scenario: Persisted playback advances and wraps predictably

- **WHEN** playback state is synchronized and the playlist advances through its
  queue
- **THEN** position and controls persist, current moves to played history, and
  an exhausted queue wraps through played songs
