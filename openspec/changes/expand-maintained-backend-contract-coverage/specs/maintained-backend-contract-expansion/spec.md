## ADDED Requirements

### Requirement: Fallback events preserve canonical context
The backend SHALL generate fallback round events whose text and relationship
effects preserve available player name, era, occupation, and key-person data
without requiring an AI provider.

#### Scenario: Context exists for a fallback event
- **WHEN** a round event fallback is generated from canonical player settings
- **THEN** the generated event MUST expose those fields and the key-person
  option relationship effect

### Requirement: Gameplay event safeguards are deterministic
The backend SHALL enforce SSE connection limits, terminal saved-view blocking,
and Last-Event-ID validation through local route helper behavior.

#### Scenario: A saved terminal view exists
- **WHEN** a gameplay event request is made before a result, summary, or ending
  view is acknowledged
- **THEN** the route helper MUST reject event generation with its documented
  conflict response

### Requirement: Entity extraction normalizes malformed model output
The backend SHALL return only valid new or existing item and landmark entries,
normalizing invalid enum values and rejecting malformed payloads locally.

#### Scenario: Extraction output contains invalid values
- **WHEN** an extraction parser receives malformed JSON, unsupported fields,
  or unknown update targets
- **THEN** it MUST produce only the documented valid normalized entries

### Requirement: Local music reuse checks metadata without provider state
The backend SHALL score compatible local music metadata and honor explicit
negative-cue conflicts without requiring a music provider or database.

#### Scenario: A local asset conflicts with negative cues
- **WHEN** a candidate asset contains a requested negative cue without a
  corresponding explicit negation
- **THEN** the eligibility helper MUST reject that candidate
