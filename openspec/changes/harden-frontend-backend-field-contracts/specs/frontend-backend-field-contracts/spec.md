## ADDED Requirements

### Requirement: Critical REST fields stay aligned
The system SHALL verify that critical REST response fields are present in backend schemas, generated OpenAPI artifacts, hand-written frontend TypeScript contracts, and frontend API wrapper annotations for high-risk gameplay surfaces.

#### Scenario: Game state contract is checked before browser E2E
- **WHEN** maintained/preflight contract tests run
- **THEN** the game state response contract includes `game_id`, `player_state`, `progress`, `round_info`, `current_event`, `constraint_level`, `narrative_style_id`, and `narrative_style_name` across backend schema, OpenAPI schema, and frontend type declarations

#### Scenario: Choice sync contract rejects stale field names
- **WHEN** maintained/preflight contract tests inspect the frontend API wrapper
- **THEN** the choice-sync response annotation MUST use backend field names such as `story_continuation` and `effects_applied`, and MUST NOT expose stale names such as `result` or `story` as the primary contract

#### Scenario: Character setting variants remain permissive but documented
- **WHEN** maintained/preflight contract tests inspect character setting response handling
- **THEN** era setting fields such as `year`, `era_description`, and `world_context` are covered, and the frontend contract MUST NOT claim a single stale `era_name`-style shape

### Requirement: Frontend mocks match critical backend payloads
The system SHALL validate reusable frontend mock payloads and high-use test fixtures for critical backend fields that browser-agent regressions depend on.

#### Scenario: Mock game state includes required backend fields
- **WHEN** contract tests scan frontend mocks and high-use API tests
- **THEN** mocked game state payloads include required fields such as `constraint_level` and narrative style fields where the backend contract exposes them

#### Scenario: Mock scene images include rendering refresh fields
- **WHEN** contract tests scan scene image mocks
- **THEN** mocked round scene image payloads include `week` and `stage` in addition to `round_number`, `image_url`, and `scene_description`

### Requirement: SSE payload fields are explicitly contracted
The system SHALL verify browser-consumed SSE event payloads with dedicated contract tests because OpenAPI does not fully model streamed event bodies.

#### Scenario: Scene image SSE payloads include refresh keys
- **WHEN** scene image SSE emits ready or failed events
- **THEN** ready events include `type`, `game_id`, `round_number`, `week`, `stage`, `image_url`, `scene_description`, and `timestamp`, and failed events include `type`, `game_id`, `round_number`, `week`, `stage`, `error`, and `timestamp`

#### Scenario: Gameplay SSE payloads keep parser-facing keys stable
- **WHEN** gameplay SSE helper payloads are generated or parsed
- **THEN** parser-facing event types such as `status`, `story`, `complete`, and `error` retain their expected JSON keys

### Requirement: Field contracts run in maintained gates
The system SHALL run the frontend/backend field contract test file in local and CI maintained gates before full browser E2E.

#### Scenario: Local preflight includes field contracts
- **WHEN** `./test.sh preflight` or `./test.sh contract` runs
- **THEN** the field-contract test file and this OpenSpec change validation are included before browser E2E

#### Scenario: CI maintained backend gate includes field contracts
- **WHEN** backend maintained CI or coverage jobs run
- **THEN** the field-contract test file is part of the curated pytest list so field drift blocks the maintained gate
