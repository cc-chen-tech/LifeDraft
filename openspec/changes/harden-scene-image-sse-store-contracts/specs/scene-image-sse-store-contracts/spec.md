## ADDED Requirements

### Requirement: Ready scene-image events update the correct cached state
The frontend test suite SHALL verify that a ready scene-image SSE event updates
the matching event/result state and replaces an existing scene with the same
week, round, and stage.

#### Scenario: Ready event for an existing scene key
- **WHEN** the store receives a `scene_image_ready` event for a cached scene
- **THEN** it replaces that entry, clears its error, and exposes the new stage
  image

### Requirement: SSE failures and heartbeats have deterministic state effects
The frontend test suite SHALL verify terminal failure visibility and heartbeat
no-op behavior.

#### Scenario: Terminal failure event
- **WHEN** the store receives a `scene_image_failed` event
- **THEN** loading ends and the event message becomes the visible error

#### Scenario: Heartbeat event
- **WHEN** the store receives a heartbeat
- **THEN** scene image and error state are unchanged

### Requirement: SSE subscriptions clean up replaced connections
The frontend test suite SHALL verify subscription replacement and explicit
unsubscription close the corresponding EventSource objects.

#### Scenario: Re-subscribe and unsubscribe
- **WHEN** a game subscription is replaced and later unsubscribed
- **THEN** the prior connection is closed and the store ends without an active
  connection
