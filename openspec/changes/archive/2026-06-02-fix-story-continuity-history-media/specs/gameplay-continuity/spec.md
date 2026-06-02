## ADDED Requirements

### Requirement: Story streaming retries replace the active attempt
The system SHALL prevent duplicate story display when an event or choice stream is retried, regenerated, or consistency-corrected.

#### Scenario: Retry marker during story generation
- **WHEN** the backend emits a retry status during story generation
- **THEN** the frontend MUST clear the active streamed story attempt before appending replacement chunks

#### Scenario: Normal stream continuation
- **WHEN** the backend streams chunks without a retry status
- **THEN** the frontend MUST append chunks exactly once in received order

#### Scenario: Reconnection to completed event
- **WHEN** the frontend reconnects to an event that already has a completed current event and options
- **THEN** the frontend MUST show the persisted story and options without duplicating previously displayed text

### Requirement: Options answer the current story decision point
The system SHALL generate options that directly respond to the final decision point of the displayed story.

#### Scenario: Generic options rejected
- **WHEN** generated options are generic actions unrelated to the final story situation
- **THEN** the backend MUST retry option generation or return story-specific fallback options

#### Scenario: Relationship target validation
- **WHEN** an option includes relationship effects
- **THEN** the relationship target MUST be an available person, a family member, or a character explicitly present in the story text

#### Scenario: Option set coherence
- **WHEN** options are shown to the player
- **THEN** all options MUST be alternative responses to the same current decision point, not unrelated future actions

### Requirement: Narrative generation preserves continuity constraints
The system SHALL maintain continuity for storylines, character locations, and career/position progression across rounds.

#### Scenario: Character location mismatch
- **WHEN** a character has a known location in the world model
- **THEN** generated story MUST NOT place that character in a conflicting location without travel or transition explanation

#### Scenario: Career progression mismatch
- **WHEN** a character has a known career or position record
- **THEN** generated story MUST NOT suddenly change that role or rank without an explicit story transition

#### Scenario: Ongoing storyline reference
- **WHEN** a pending storyline exists
- **THEN** generated story MUST either continue, defer, or avoid contradicting that storyline

### Requirement: Generated Chinese story text uses consistent punctuation
The system SHALL produce polished Chinese narrative text without mixed Chinese/English punctuation artifacts.

#### Scenario: Chinese narrative output
- **WHEN** the game language is Chinese
- **THEN** generated story and continuation text MUST prefer Chinese punctuation for Chinese prose and dialogue

#### Scenario: Mixed punctuation cleanup
- **WHEN** generated Chinese text contains obvious English punctuation artifacts around Chinese dialogue or sentences
- **THEN** the system MUST normalize or regenerate the affected text before display where feasible

### Requirement: Story openings vary across rounds
The system SHALL avoid repetitive openings, props, and scene structures across recent rounds.

#### Scenario: Repeated opening pattern
- **WHEN** recent stories repeatedly use the same opening structure or atmospheric motif
- **THEN** subsequent generation MUST bias away from those phrases and structures

#### Scenario: Core item reuse
- **WHEN** a plot-critical item or location reappears
- **THEN** the story MAY reuse it but MUST vary the framing and avoid copy-like scene setup

### Requirement: Opening story displays generated text before game start
The system SHALL display generated opening story text on `/story/opening` before allowing the player to enter gameplay.

#### Scenario: Backend streams event-typed story chunks
- **WHEN** the opening story endpoint streams `event: story` records with JSON string payloads
- **THEN** the frontend MUST append those chunks to the visible opening story text

#### Scenario: Complete payload omits full story
- **WHEN** an opening story stream completes after story chunks but the complete payload has no `full_story`
- **THEN** the frontend MUST preserve and store the accumulated streamed text instead of replacing it with an empty string

### Requirement: Recovered gameplay state includes story text with options
The system SHALL never show current options without the story text those options answer.

#### Scenario: Active event recovered from server
- **WHEN** `/api/games/active` or `/api/games/{id}/state` returns a current event with options and event text
- **THEN** the frontend MUST set both `currentEvent` and `storyText` from the recovered event when local story text is empty

#### Scenario: Regeneration returns replacement options
- **WHEN** regeneration completes with options
- **THEN** the frontend MUST keep or replace the visible story text consistently with those options and MUST NOT leave an empty story with non-empty options

### Requirement: Story editing controls do not block gameplay choices
The bottom story assistant SHALL NOT intercept clicks for visible gameplay choice controls.

#### Scenario: Assistant open near custom choice
- **WHEN** the story assistant is expanded and the custom choice input is visible
- **THEN** the user MUST be able to close the assistant using an accessible control and submit the custom choice without pointer interception

### Requirement: Narrative text is polished before display
Generated Chinese narrative SHALL be display-ready before it reaches the player.

#### Scenario: Internal implementation language leaks
- **WHEN** generated text contains implementation/meta phrases such as `世界模型`, `约束`, or self-referential generation notes
- **THEN** the backend MUST reject, retry, or sanitize the text before persisting or streaming it

#### Scenario: Person perspective consistency
- **WHEN** a story event is generated in Chinese
- **THEN** the event and its continuation MUST use one consistent narrative perspective unless a deliberate quoted dialogue requires otherwise

#### Scenario: Over-fragmented paragraphs
- **WHEN** generated story text contains excessive one-sentence paragraphs
- **THEN** the backend SHOULD normalize paragraph grouping to a readable narrative cadence before display
