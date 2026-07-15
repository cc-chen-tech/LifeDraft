## ADDED Requirements

### Requirement: Relationship effects derive deterministic character deltas
The maintained backend suite SHALL verify that positive and negative
relationship changes derive affinity, trust, respect, and mood deltas, and
that detailed character effects can override derived values.

#### Scenario: Positive and detailed effects
- **WHEN** an option contains positive relationship and detailed character
  effects
- **THEN** the calculated result contains derived positive deltas and explicit
  detailed overrides.

#### Scenario: Negative relationship effect
- **WHEN** an option reduces a relationship
- **THEN** the calculated trust, respect, and mood deltas are negative.

### Requirement: Decision context and fallback behavior are deterministic
The maintained backend suite SHALL verify context rendering, invalid index
rejection, and localized fallback result generation without a provider.

#### Scenario: Known and missing interaction participants
- **WHEN** interaction context is requested for known, missing, or no names
- **THEN** only known character context is rendered and empty inputs return
  empty context.

#### Scenario: Result provider is unavailable
- **WHEN** a local result provider raises while processing a valid decision
- **THEN** processing succeeds and returns localized deterministic fallback
  text with the applied effects.

### Requirement: Maintained workflow parity includes decision contracts
Both backend workflow lists SHALL include the decision effect fallback contract
once in the same order.

#### Scenario: Workflow list comparison
- **WHEN** maintained workflow test paths are parsed in order
- **THEN** the two lists are equal and include the decision suite once.
