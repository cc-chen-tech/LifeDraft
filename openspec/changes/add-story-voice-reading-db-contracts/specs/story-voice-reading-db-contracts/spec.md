## ADDED Requirements

### Requirement: Story voice reading state is maintained through real persistence

The maintained backend suite SHALL validate story voice reading settings,
validated reading context, browser fallback jobs, deterministic audio assets,
asset reuse, and recovered job response fields against the real database.

#### Scenario: Browser fallback persists a recoverable job

- **WHEN** a valid reading request uses the browser speech provider
- **THEN** the service returns browser playback fields, creates no audio asset,
  and recovers the same job as browser playback

#### Scenario: Deterministic audio is created and reused for its owner

- **WHEN** an owner requests the same valid text, voice, and speed twice with
  the deterministic provider
- **THEN** the first response persists an audio asset and the later response
  reuses that asset with stable media fields

#### Scenario: Invalid identity and hash do not create reading state

- **WHEN** a reading context lacks required round identity or has a mismatched
  text hash
- **THEN** validation rejects it with the corresponding structured error code
