## ADDED Requirements

### Requirement: Ready generated music assets have stable local-library persistence contracts
The maintained backend suite SHALL verify that a ready local generated-music asset can be indexed, updated without duplication, and reused through a disposable real SQLite session without contacting a provider.

#### Scenario: Existing ready asset is re-indexed after metadata changes
- **WHEN** an indexed ready asset is updated and indexed again
- **THEN** the service SHALL retain one library entry and persist the refreshed searchable metadata.

#### Scenario: Valid library match is reused safely
- **WHEN** a compatible indexed asset has playable local audio
- **THEN** the service SHALL return a reusable track without source prompt data and record the reuse metadata.

### Requirement: Local music match decisions expose deterministic rejection reasons
The maintained backend suite SHALL verify that incompatible provider settings and negative-cue conflicts produce a miss with their corresponding rejection reason.

#### Scenario: Incompatible candidate is rejected
- **WHEN** a ready indexed asset does not match requested generation settings or conflicts with requested negative cues
- **THEN** the decision SHALL be a miss containing the applicable rejection reason codes.

### Requirement: Maintained workflows run local music persistence contracts
Both maintained backend workflow test lists SHALL include the provider-free local music persistence contract module in the same order.

#### Scenario: Workflow parity is preserved
- **WHEN** backend coverage and backend test workflows are compared
- **THEN** the local music persistence contract path SHALL appear in both lists at the same position.
