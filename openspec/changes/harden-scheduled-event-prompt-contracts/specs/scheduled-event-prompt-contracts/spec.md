## ADDED Requirements

### Requirement: Scheduled event prompts preserve persisted commitments
The maintained backend suite SHALL verify that a scheduled event prompt includes commitment details, involved people, current timeline, and character constraints for both supported languages.

#### Scenario: Multiple scheduled commitments
- **WHEN** multiple persisted commitments are due in the current round
- **THEN** the prompt SHALL preserve their descriptions and relevant cast identity.

### Requirement: Maintained workflows run scheduled event prompt contracts
Both maintained backend workflow lists SHALL include the scheduled event prompt contract path in matching order.

#### Scenario: Workflow parity
- **WHEN** workflow test lists are compared
- **THEN** the contract path SHALL occur in both lists at the same position.
