## ADDED Requirements

### Requirement: MiniMax narration degrades without credentials
The maintained backend suite SHALL verify that a MiniMax provider without a credential returns browser-speech metadata rather than attempting backend audio.

#### Scenario: Missing credential
- **WHEN** the provider has neither an API key nor local audio enabled
- **THEN** synthesis SHALL return browser-speech playback metadata.

### Requirement: Local MiniMax narration has deterministic reusable assets
The maintained backend suite SHALL verify that explicit local-audio configuration produces a WAV asset and reuses it for an identical request.

#### Scenario: Local synthesis cache
- **WHEN** the same local-audio request is synthesized twice
- **THEN** both results SHALL reference the same WAV asset without external transport.

### Requirement: Maintained workflows run MiniMax fallback contracts
Both maintained backend workflow lists SHALL include the MiniMax fallback contract module in matching order.

#### Scenario: Workflow parity
- **WHEN** workflow test lists are compared
- **THEN** the MiniMax fallback contract path SHALL appear in both lists at the same position.
