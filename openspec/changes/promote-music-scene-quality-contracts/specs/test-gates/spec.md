## ADDED Requirements

### Requirement: Maintained gates cover story-to-music scene quality
The maintained backend test and coverage workflows SHALL include deterministic story-to-music scene contracts for scene classification, candidate ranking, unsafe cue rejection, prompt constraints, and era-aware context.

#### Scenario: Inappropriate candidate regression
- **WHEN** music ranking favors a candidate conflicting with a story's negative cues or scene fit
- **THEN** the maintained backend gate MUST fail before release-only validation

#### Scenario: Era context regression
- **WHEN** a recommendation request or service loses character-era context
- **THEN** the maintained backend gate MUST fail before release-only validation

### Requirement: Maintained workflow selections remain equivalent
The maintained backend test workflow and maintained coverage workflow SHALL select music scene-quality and era-recommendation contracts exactly once and in the same order.

#### Scenario: Workflow selection review
- **WHEN** music quality suites are added to a maintained workflow
- **THEN** both workflows MUST contain the same ordered paths
