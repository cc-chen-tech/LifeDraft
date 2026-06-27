## ADDED Requirements

### Requirement: Choice completion does not duplicate streamed story text

The client SHALL treat the choice SSE story stream as the normal owner of
visible choice continuation text. The shared choice completion state handler
SHALL NOT append or replace visible story text from `story_continuation` or
`event_description`.

#### Scenario: Complete payload follows streamed continuation
- **Given** a player choice stream has already appended continuation text through `onStory`
- **When** the complete callback receives `story_continuation`
- **Then** the shared completion state handler SHALL NOT call `setStoryText`
- **And** the client SHALL still enter the result phase.

#### Scenario: Retry complete payload follows replacement stream
- **Given** a choice stream retry restored the base story and streamed replacement continuation text
- **When** the complete callback receives `story_continuation`
- **Then** the client SHALL NOT append the continuation again.

#### Scenario: Fallback recovery owns non-stream text replacement
- **Given** a choice stream did not complete and the client recovers via sync fallback or round history
- **When** the fallback or recovery path receives persisted continuation text
- **Then** that fallback or recovery path MAY replace visible story text with the recovered continuation.

#### Scenario: Complete-only stream has no story chunks
- **Given** a choice SSE stream completes without any `onStory` chunks
- **When** the complete payload includes `event_description` or `story_continuation`
- **Then** the choice hook MAY use that complete payload once as a fallback continuation
- **And** the shared completion state handler SHALL still avoid owning visible story text mutation.
