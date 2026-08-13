## MODIFIED Requirements

### Requirement: Narrative generation preserves continuity constraints
The system SHALL maintain continuity for storylines, character locations, career progression, and the previous day's accepted choice across daily stories.

#### Scenario: Character location mismatch
- **WHEN** a character has a known location in the world model
- **THEN** generated story MUST NOT place that character in a conflicting location without travel or transition explanation

#### Scenario: Previous day choice exists
- **WHEN** the next daily story is generated after a committed choice
- **THEN** it MUST incorporate that choice and its applied effects without requiring a choice-result continuation generation

### Requirement: Opening story displays generated text before game start
The system SHALL treat the first generated daily event as the playable opening story and SHALL route the player directly into daily gameplay with its options.

#### Scenario: First day generation completes
- **WHEN** character creation requests the opening story for a daily game
- **THEN** the generated story MUST be persisted as day one with options and displayed by `/play`

#### Scenario: Legacy opening route is used
- **WHEN** a daily game opens the legacy opening route
- **THEN** the frontend MUST resume or generate day one and redirect to daily gameplay without generating a second opening

### Requirement: Recovered gameplay state includes story text with options
The system SHALL never show current options without the daily story text and version metadata those options answer.

#### Scenario: Active daily event recovered from server
- **WHEN** a state response returns a current daily event
- **THEN** the frontend MUST restore its story, options, event id, revision, and story date together

#### Scenario: Generation fails after a committed choice
- **WHEN** a choice has advanced the date but the next daily generation fails
- **THEN** refresh MUST restore the advanced empty day and permit generation retry without replaying the choice

## ADDED Requirements

### Requirement: Daily generation happens once per day
The system SHALL generate one complete daily story and its options before the choice and SHALL NOT generate narrative continuation after the choice.

#### Scenario: Generated option is selected
- **WHEN** a player selects a generated option
- **THEN** choice processing MUST use the option's existing effects and MUST NOT call the story-continuation provider

#### Scenario: Choice settles before next generation
- **WHEN** settlement succeeds and the game is not over
- **THEN** the frontend MUST briefly expose structured effects and automatically start the next day's generation

### Requirement: Rewrite and regenerate replace coherent candidates
The system SHALL replace a current day's event only after a candidate story and matching option set both validate.

#### Scenario: Rewrite succeeds
- **WHEN** a current daily story is rewritten
- **THEN** its prose, options, and revision MUST be replaced together without advancing the date

#### Scenario: Replacement option generation fails
- **WHEN** rewrite or regenerate cannot produce valid matching options
- **THEN** the original current event and media MUST remain authoritative

### Requirement: Daily mode disables custom choices and weekly pauses
Daily gameplay SHALL expose only generated options and SHALL not enter custom-choice, next-round confirmation, or weekly-summary phases.

#### Scenario: Custom choice endpoint is called
- **WHEN** a daily game receives a custom-choice request
- **THEN** the API MUST return the `custom_choice_disabled` error without changing game state

#### Scenario: Seventh day commits
- **WHEN** the seventh day of a daily week is selected
- **THEN** deterministic weekly decay MAY apply, but no weekly-summary prose, bonus, or page MUST block the next day
