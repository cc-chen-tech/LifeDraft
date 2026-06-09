## ADDED Requirements

### Requirement: Netease recommendations enforce negative cues after search
The system SHALL remove incompatible NetEase tracks after search when their title, artist, album, or known category contradicts the structured music brief.

#### Scenario: Generic no-vocal cues reject reported vocal-pop failures
- **GIVEN** a music brief for warm workplace or business-dialogue background music includes negative cues such as `人声`, `歌词`, `情歌`, or `流行人声`
- **WHEN** NetEase results include known vocal-pop or meme tracks such as `小幸运`, `断了的弦`, `坤坤错过`, or `起坤了只因你太美`
- **THEN** those tracks MUST be removed before recommendations are returned
- **AND** compatible instrumental or background tracks MUST remain eligible

#### Scenario: Cover and version variants are de-duplicated
- **GIVEN** NetEase results include several ids whose title normalizes to the same base song title
- **WHEN** the recommendation pool is selected for playback
- **THEN** only one normalized title MAY be returned
- **AND** duplicate covers, speed edits, or parenthetical variants MUST NOT fill the queue
