## ADDED Requirements

### Requirement: Inline Rewrite Shows Streaming Progress

Inline rewrite controls SHALL surface rewrite progress from the SSE stream instead of showing a static loading message for the entire operation.

#### Scenario: Rewrite stream sends status messages

- **WHEN** the player submits the inline rewrite sheet
- **AND** the rewrite SSE stream sends status messages such as `正在理解改写要求` or `正在生成改写文本`
- **THEN** the UI MUST show the latest progress message
- **AND** the rewrite sheet MUST expose that message through an `aria-live` progress region.

#### Scenario: Rewrite stream reconnects

- **WHEN** the rewrite SSE request reconnects after a transient failure
- **THEN** the UI MUST show a retry progress message with the current retry attempt and maximum attempts.
