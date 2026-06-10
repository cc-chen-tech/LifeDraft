## ADDED Requirements

### Requirement: Frontend sound queue dedupes reported title families

The frontend music store SHALL apply the same normalized title-family dedupe as
the backend playlist when it merges recommended songs into the local playback
queue.

#### Scenario: Optimistic queue merge receives duplicate NetEase title variants

- **WHEN** the frontend receives recommended songs such as `绅士`, `绅士 (Live)`,
  `红尘客栈`, and `红尘客栈 - 古风翻唱`
- **THEN** the local future queue MUST keep only the first item from each title
  family
- **AND** the current song MUST remain unchanged
- **AND** non-duplicate scene-matched songs MUST remain in the queue
