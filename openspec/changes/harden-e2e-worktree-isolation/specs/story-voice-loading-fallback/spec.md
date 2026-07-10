## ADDED Requirements

### Requirement: Browser fallback metadata is prepared during backend loading
The story voice client SHALL expose browser fallback mode and the selected story text immediately when browser speech is available, while keeping playback in the loading state until a provider result is known.

#### Scenario: Backend voice request is still pending
- **WHEN** a user starts story reading in a browser with speech synthesis support and the backend response has not arrived
- **THEN** playback mode MUST be `browser_speech`, current speech text MUST equal the selected story text, spoken text length MUST be non-zero, and reading state MUST remain `loading`

#### Scenario: Backend audio becomes ready
- **WHEN** a pending request returns a playable provider audio asset
- **THEN** the client MUST replace the prepared fallback metadata with audio mode and MUST NOT have started browser speech

#### Scenario: Backend request cannot provide audio
- **WHEN** a pending request returns browser fallback or fails with an authentication or transport error
- **THEN** the existing browser-speech path MUST start from the prepared story text without waiting for another backend round trip

#### Scenario: Browser provider is explicitly selected
- **WHEN** the caller explicitly selects the browser provider
- **THEN** the client MUST dispatch the real backend recording request, start browser speech without awaiting its response, and MUST NOT start speech again when that response settles
