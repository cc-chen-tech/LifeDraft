## ADDED Requirements

### Requirement: Style validation produces structured deterministic evidence
The maintained backend gate SHALL verify that a configured style produces
structure, pacing, language, and technique evidence with normalized scores.

#### Scenario: Configured story matches all dimensions
- **WHEN** a story includes configured structure, hook, rhetoric, and technique
  indicators
- **THEN** validation SHALL return all dimension scores and a passing result

### Requirement: Missing required hook is observable
The maintained backend gate SHALL verify that a configured hook absent from an
ending produces a pacing failure with a human-readable reason.

#### Scenario: Missing hook fails pacing
- **WHEN** a style requires a suspense hook and the story ending has none
- **THEN** pacing validation SHALL return false and its expected-hook evidence

### Requirement: Style validation degrades predictably
The maintained backend gate SHALL verify no-style fallback, zero weight scoring,
and harness callback adaptation.

#### Scenario: No style is configured
- **WHEN** validation runs without a style manifest
- **THEN** it SHALL report a passing skipped result and default dimension scores
