## ADDED Requirements

### Requirement: Maintained gate validates comprehensive round choice transitions
The maintained backend selection SHALL validate real choice effects, result view persistence, resource bounds, wealth transaction behavior, invalid input handling, and custom choices through `RoundChoiceProcessor`.

#### Scenario: Choice exhausts a resource
- **WHEN** a choice would reduce a bounded resource below its allowed value
- **THEN** the maintained contract MUST require the applied effect and warning metadata to reflect the actual bounded transition
