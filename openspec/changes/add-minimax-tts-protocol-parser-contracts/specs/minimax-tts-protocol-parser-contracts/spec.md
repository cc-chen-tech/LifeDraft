## ADDED Requirements

### Requirement: MiniMax TTS protocol parsing is maintained
The maintained backend suite SHALL verify accepted nested audio/status/file URL
response shapes and provider base-response failures.

#### Scenario: Nested provider response is parsed
- **WHEN** audio or completion information is supplied in a nested data object
- **THEN** the parser returns the audio/completion result

### Requirement: MiniMax TTS file safety is maintained
The maintained backend suite SHALL verify that tar audio extraction returns an
audio member when present and protocol endpoints require HTTP(S).

#### Scenario: Tar audio and invalid scheme
- **WHEN** a tar response includes an audio file and a non-HTTP URL is checked
- **THEN** audio bytes are returned and the invalid URL is rejected
