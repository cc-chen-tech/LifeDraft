## ADDED Requirements

### Requirement: Stale generation never traps the user

The system SHALL recover or expire an in-progress generation state so the player is never left with no story, no options, and no action after refresh.

#### Scenario: Completed event exists after refresh

- **WHEN** the frontend restores an active game while local UI phase is generating
- **AND** the backend active game contains a current event with story text and options
- **THEN** the frontend MUST show the story and options
- **AND** it MUST clear the transient generating phase.

#### Scenario: Saved current event survives service initialization

- **WHEN** a saved game is loaded from `current_event_data`
- **AND** round services are initialized after the load
- **THEN** the backend MUST keep the loaded current event available to `/event`
- **AND** `/event` MUST return the existing story/options instead of starting a new generation.

#### Scenario: Generation remains in progress too long

- **WHEN** story or choice generation exceeds the configured long-running threshold
- **THEN** the UI MUST show a clear long-running generation message
- **AND** it MUST provide a retry or continue/recover action.

#### Scenario: No completed event can be recovered

- **WHEN** generation state is stale and no completed story/options exist
- **THEN** the system MUST expire the stale state into a retryable error
- **AND** it MUST NOT keep restoring an endless generating UI after refresh.

#### Scenario: Continue action cannot wait forever on state sync

- **WHEN** the player continues after a round or weekly summary
- **AND** player-state synchronization hangs or takes too long
- **THEN** the frontend MUST still start the next event generation through its normal SSE path
- **AND** it MUST guard against duplicate generation if synchronization later resolves.

#### Scenario: Stream completes without a playable event

- **WHEN** an event stream completes without options
- **OR** it completes with options but no recoverable story body
- **THEN** the frontend MUST enter a retryable error state
- **AND** it MUST NOT leave the player in the generating phase.

### Requirement: Opening page uses the same effective character source as recovery flow

The opening story page SHALL use resolved character data (store data or injected recovery/test data) consistently for validation and request payloads.

#### Scenario: Store is incomplete but resolved data is available

- **WHEN** `/story/opening` receives resolved character data from injected/recovered source
- **AND** local store fields are temporarily empty during hydration/recovery
- **THEN** opening story generation MUST use the resolved data for request payload
- **AND** the page MUST NOT show the "缺少角色数据" error.

### Requirement: Scene illustration background generation uses a valid service path

The scene illustration background trigger SHALL call an existing image generation service API and SHALL NOT fail with an AttributeError after returning 202.

#### Scenario: Missing scene image starts background generation

- **WHEN** the frontend requests a missing round scene image
- **AND** the backend starts asynchronous scene generation
- **THEN** the background task MUST call a service method that exists
- **AND** it MUST persist or return the scene through the standard scene image generation path.

#### Scenario: Result scene uses the completed round

- **WHEN** a choice result advances `current_round` to the next round
- **AND** the UI is still displaying the just-completed round result
- **THEN** the frontend MUST request the result scene for the completed round
- **AND** it MUST NOT request the next round's result scene before that round has story text.

#### Scenario: Ancient scene analysis rejects modern visual elements

- **WHEN** a scene image is generated for an ancient/pre-modern story
- **THEN** the scene analyzer prompt MUST include visual era red-line constraints
- **AND** any analyzer output containing modern visual elements such as down jackets, electric heaters, highways, or modern restaurants MUST be rejected before image generation.

#### Scenario: Scene image requests wait for generated story text

- **WHEN** a new round has just started and its story text is still loading or generating
- **THEN** the frontend MUST NOT request the current round scene image yet
- **AND** once story/options are available it MUST request the event-stage scene image for that round.

#### Scenario: Duplicate scene generation races

- **WHEN** SSE completion and frontend scene fetching trigger the same scene image generation concurrently
- **THEN** the image persistence layer MUST treat the unique scene constraint conflict as idempotent
- **AND** it MUST roll back, reuse the existing scene record, and avoid logging an unexpected error traceback.

### Requirement: Music service degradation keeps gameplay usable

The music recommendation flow SHALL degrade clearly when the upstream music service is unavailable.

#### Scenario: Upstream music search returns 503

- **WHEN** the music search upstream returns HTTP 503
- **THEN** the backend MUST return an empty recommendation without logging an error traceback
- **AND** the frontend MUST show a clear unavailable-state message
- **AND** the player MUST be able to continue the story.

### Requirement: Choice continuations preserve narrative person

Choice result generation SHALL use the same third-person narrative contract as event generation.

#### Scenario: Chinese choice result prompt

- **WHEN** a Chinese choice continuation prompt is generated for a third-person story
- **THEN** it MUST require third-person narration using the protagonist name or `他/她`
- **AND** it MUST NOT require second-person narration with narrative `你`.

#### Scenario: Choice continuation starts after the choice

- **WHEN** a choice continuation prompt includes the current story and the selected option
- **THEN** it MUST instruct the model to continue from after the selected choice
- **AND** it MUST forbid re-narrating scenes, travel, dialogue, or revelations already shown in the current story.

#### Scenario: English choice result prompt

- **WHEN** an English choice continuation prompt is generated for a third-person story
- **THEN** it MUST require third-person narration
- **AND** it MUST NOT require second-person narration.
