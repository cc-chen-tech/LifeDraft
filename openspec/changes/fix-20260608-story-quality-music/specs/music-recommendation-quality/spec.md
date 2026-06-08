## ADDED Requirements

### Requirement: Music recommendations honor negative cues at returned-song layer
The music recommendation service SHALL filter playable returned songs using the final `music_brief.negative_cues`, not only use those cues while building search queries.

#### Scenario: Negative cue song is excluded
- **WHEN** a music brief includes negative cues such as `等你下课`, `小幸运`, `断了的弦`, `type beat`, or `蔡徐坤`
- **AND** the music provider returns playable songs matching those cues
- **THEN** those songs SHALL be excluded from the recommendation result.

#### Scenario: Cue variants are normalized
- **WHEN** a returned song differs only by whitespace, punctuation, casing, remix suffix, or live/version suffix from a negative cue
- **THEN** it SHALL still be treated as a negative-cue match.

### Requirement: Music recommendations dedupe by song identity
The music recommendation service SHALL dedupe returned playable songs by provider ID and normalized song identity.

#### Scenario: Same song repeated under multiple IDs
- **WHEN** the provider returns seven playable entries named `断了的弦` with different IDs
- **THEN** the final recommendation SHALL contain at most one normalized `断了的弦` entry.

#### Scenario: Weak workplace mismatch is excluded
- **WHEN** the story brief is modern workplace, product management, debt, or suspense background music
- **AND** a returned playable song is vocal-pop, meme music, romantic school pop, unrelated anime OP, or a prompt-leak result
- **THEN** the song SHALL be excluded unless it has clear score/background/workplace metadata.

### Requirement: Generated music degrades without blocking recommendation
The AI generated music endpoint SHALL be bounded and SHALL return structured JSON on provider failure.

#### Scenario: MiniMax provider times out
- **WHEN** MiniMax music generation exceeds the configured request timeout
- **THEN** `/api/music/generate` SHALL return a JSON response indicating generated music is unavailable
- **AND** it SHALL not return 502 HTML, empty response, or block story choice recovery.

#### Scenario: MiniMax provider rejects audio settings
- **WHEN** MiniMax rejects a bitrate, sample rate, or format setting
- **THEN** the API SHALL return structured JSON containing the provider error category
- **AND** the story and NetEase recommendation flow SHALL remain usable.
