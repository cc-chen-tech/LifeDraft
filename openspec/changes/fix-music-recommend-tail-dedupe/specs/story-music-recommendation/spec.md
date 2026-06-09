## ADDED Requirements

### Requirement: Negative-cue title families are filtered

The system SHALL remove NetEase search results whose title, artist, album, or known title family contradicts the structured music brief negative cues.

#### Scenario: Reported vocal-pop title families are rejected

- **WHEN** a gameplay background music brief requests no vocals or includes negative cues such as `人声`, `歌词`, `情歌`, or `流行人声`
- **THEN** search results from reported vocal-pop title families such as `绅士`, `红尘客栈`, `非你莫属`, and `给我一首歌的时间` MUST NOT enter the verified recommendation pool

### Requirement: Recommended playlists dedupe by title family

The system SHALL dedupe music recommendations by both provider id and normalized title family before persisting the current/future queue.

#### Scenario: Same title family has different provider ids

- **WHEN** the music playlist receives multiple recommendation items from the same normalized title family but with different ids
- **THEN** only the first non-current item from that title family MAY remain in the queue
- **AND** the current song MUST NOT be replaced by a refresh
