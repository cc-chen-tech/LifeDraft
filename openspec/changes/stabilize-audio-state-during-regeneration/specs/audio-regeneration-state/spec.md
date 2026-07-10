## ADDED Requirements

### Requirement: Selected voice remains stable
The selected voice color MUST persist through the voice settings producer/consumer contract and SHALL not be overwritten by a stale settings response after a newer user selection.

#### Scenario: User chooses clear neutral
- **WHEN** the user selects `clear_neutral` and the setting is saved
- **THEN** remounting the controls SHALL restore `clear_neutral`
- **AND** a delayed earlier response SHALL not replace it with `warm_female`

### Requirement: Regeneration cancels stale current-story audio
Entering a current-story loading, generating, or choosing phase MUST stop any current-story narration and clear its media target.

#### Scenario: Old story was playing
- **WHEN** regeneration starts while the old story is playing
- **THEN** reading state SHALL become idle
- **AND** the old reading context and audio URL SHALL be cleared
- **AND** ducked music SHALL follow the normal restoration path

### Requirement: Incomplete replacement text is not published to media services
TTS and generated-music consumers MUST receive current-story text only after the story reaches a completed media phase.

#### Scenario: Replacement stream is partial
- **WHEN** replacement text is streaming in a busy phase
- **THEN** the voice auto-read target SHALL be not ready
- **AND** the music active story target SHALL be null

#### Scenario: Replacement stream completes
- **WHEN** final replacement text reaches options, result, or summary
- **THEN** both consumers SHALL receive the same final text

### Requirement: Real persistence and browser interaction are verified
The repository gates MUST verify settings persistence and visible regeneration state without mocks or skips.

#### Scenario: Real settings round trip
- **WHEN** `clear_neutral` is saved and read through the real voice settings repository
- **THEN** the returned selected voice color SHALL remain `clear_neutral`

#### Scenario: Browser starts regeneration
- **WHEN** the E2E fixture starts regeneration from an active reading state
- **THEN** the visible diagnostics SHALL show idle narration and no active music story target

### Requirement: All required test layers execute
Static analysis, import validation, contract tests, real DB tests, and browser tests MUST be registered in `test.sh`.

#### Scenario: Full verification
- **WHEN** test layers run with `.env`
- **THEN** audio regeneration coverage SHALL execute without mocks or skips
