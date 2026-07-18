## ADDED Requirements

### Requirement: Story TTS provider behavior is maintained

The maintained backend suite SHALL verify story TTS provider metadata, playback
mode, deterministic audio shape, safe file tokens, explicit provider selection,
and unavailable-backend fallback without contacting an external service.

#### Scenario: Browser and deterministic providers synthesize reading output

- **WHEN** browser and deterministic providers receive a reading payload
- **THEN** their provider identity, playback mode, storage path, media type, and
  duration remain stable

#### Scenario: Deterministic WAV generation produces a playable asset

- **WHEN** deterministic story audio bytes are generated
- **THEN** the result is a fixed-length mono, 16-bit, 16 kHz WAV container

#### Scenario: Provider selection and file boundaries stay safe

- **WHEN** an explicit provider name is unknown, a backend is unavailable, or a
  generated-file path attempts to escape its asset directory
- **THEN** selection falls back safely and file access returns no asset
