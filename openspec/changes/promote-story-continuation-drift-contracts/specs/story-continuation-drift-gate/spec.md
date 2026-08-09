## ADDED Requirements

### Requirement: Story continuation drift contracts run in maintained tests
The maintained suite SHALL verify that modern story drift is rejected and
retried while explicitly ancient settings retain valid chapter-title behavior.

#### Scenario: Modern continuation drifts
- **WHEN** a modern continuation contains invented cast or genre drift
- **THEN** the contract MUST require a corrected retry before accepting output
