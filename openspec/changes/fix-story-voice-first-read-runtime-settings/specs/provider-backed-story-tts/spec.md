## ADDED Requirements

### Requirement: First story read resolves runtime provider before synthesis request

The frontend SHALL resolve story voice runtime settings before the first
manual or automatic story read when provider state is not yet known.

#### Scenario: Browser fallback production starts without backend read roundtrip
- **Given** the client has not loaded `/voice-reading/settings`
- **And** production settings report `tts_provider` as `browser`
- **And** `backend_audio_enabled` is `false`
- **When** the user starts story reading
- **Then** the client SHALL start browser speech synthesis without first
  calling `/voice-reading/read`.

#### Scenario: Explicit provider override keeps test behavior deterministic
- **Given** a deterministic E2E provider override is present
- **When** story reading starts
- **Then** the client MAY use the override path without waiting for production
  runtime settings.
