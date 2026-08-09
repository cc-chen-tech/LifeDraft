## ADDED Requirements

### Requirement: Every narrative provider call consumes one shared allowance
The system SHALL create at most one `GenerationCallTracker` per top-level narrative request and SHALL consume the appropriate prose, validation, or option allowance immediately before every provider call in that request.

#### Scenario: Quality call ceilings
- **WHEN** fast, expert, and master requests execute their generation, validation, and option paths
- **THEN** total provider calls SHALL NOT exceed 2, 5, and 7 respectively
- **AND** nested repair services SHALL use the existing tracker instead of creating new allowances.

#### Scenario: Allowance exhausted before optional repair
- **WHEN** a validation, rewrite repair, or continuation call would exceed its category allowance
- **THEN** the provider SHALL NOT be called
- **AND** the latest complete narrative candidate SHALL remain available.

### Requirement: Narrative requests enforce one total deadline
The call tracker SHALL enforce the quality-level total deadline using monotonic elapsed time before every provider call.

#### Scenario: Deadline expires during recovery
- **WHEN** a request deadline expires after complete prose exists but before validation or recovery finishes
- **THEN** no further provider call SHALL start
- **AND** the system SHALL return the latest complete prose for downstream option handling.

### Requirement: Truncation recovery is bounded and non-recursive
Truncation continuation SHALL consume the original request's prose allowance and SHALL NOT recursively enter another truncation-recovery sequence.

#### Scenario: Continuation response is also truncated
- **WHEN** a recovery continuation response reports another truncation
- **THEN** it SHALL NOT create a fresh tracker or recursively invoke recovery
- **AND** any additional continuation SHALL occur only inside the original bounded recovery loop and remaining prose allowance.
