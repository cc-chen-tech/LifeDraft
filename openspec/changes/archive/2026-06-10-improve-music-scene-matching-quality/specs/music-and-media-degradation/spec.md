## ADDED Requirements

### Requirement: Low-Confidence Music Degrades To Safe Background Playback
Weak story-to-music matches SHALL degrade to safe background music or pending music state rather than surfacing clearly mismatched tracks.

#### Scenario: Candidate pool is playable but mismatched
- **WHEN** the music service has playable candidates but all candidates are rejected by scene-fit or negative-cue checks
- **THEN** the system SHALL return safe instrumental/background fallback recommendations or no music candidate
- **AND** story choices and continuation controls SHALL remain usable.

#### Scenario: Prompt quality is too low for AI generation
- **WHEN** the system cannot build a bounded scene-specific MiniMax prompt with required negative instructions
- **THEN** it SHALL avoid starting a paid generation call for that scene
- **AND** it SHALL keep the NetEase or safe fallback playback path available.
