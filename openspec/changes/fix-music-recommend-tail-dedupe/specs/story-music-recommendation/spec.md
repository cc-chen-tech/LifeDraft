## ADDED Requirements

### Requirement: Negative-cue title families are filtered

The system SHALL remove NetEase search results whose title, artist, album, or known title family contradicts the structured music brief negative cues.

#### Scenario: Reported vocal-pop title families are rejected

- **WHEN** a gameplay background music brief requests no vocals or includes negative cues such as `人声`, `歌词`, `情歌`, or `流行人声`
- **THEN** search results from reported vocal-pop title families such as `绅士`, `红尘客栈`, `非你莫属`, and `给我一首歌的时间` MUST NOT enter the verified recommendation pool

#### Scenario: Anime opening metadata is rejected for no-vocal background briefs

- **WHEN** a gameplay background music brief requests no vocals or no lyrics
- **AND** search results contain Anime/ACG/J-pop opening metadata such as `TV动画 OP`, `Anime Opening`, or `J-POP`
- **THEN** those vocal-opening results MUST NOT enter the verified recommendation pool
- **AND** explicit instrumental metadata such as `无歌词`, `No Lyrics`, or `Instrumental` MUST remain eligible when it otherwise matches the scene.

### Requirement: Recommended playlists dedupe by title family

The system SHALL dedupe music recommendations by both provider id and normalized title family before persisting the current/future queue.

#### Scenario: Same title family has different provider ids

- **WHEN** the music playlist receives multiple recommendation items from the same normalized title family but with different ids
- **THEN** only the first non-current item from that title family MAY remain in the queue
- **AND** the current song MUST NOT be replaced by a refresh

### Requirement: Search recommendations do not expose generated-track placeholders

The system SHALL reject search-backed music results that look like internal AI-generated track placeholders while still allowing real generated tracks to enter playback.

#### Scenario: NetEase returns a generated-track placeholder title

- **WHEN** NetEase search returns a result named like `AI MiniMax ...` or album/artist metadata like `AI Generated`
- **THEN** that search-backed result MUST NOT enter the recommended song list or verified recommendation pool
- **AND** a track with the same title and source `ai_generated` MUST remain eligible for playback insertion
