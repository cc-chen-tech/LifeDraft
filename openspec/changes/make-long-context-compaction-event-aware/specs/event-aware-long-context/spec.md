## ADDED Requirements

### Requirement: Snapshots cover only complete source events

The system SHALL serialize snapshot entries as complete events and SHALL record every covered event ID explicitly. `end_event_id` SHALL equal the final complete event actually stored, and the source digest SHALL cover exactly those events.

#### Scenario: The next event does not fit

- **WHEN** a contiguous event prefix contains one more event than the snapshot target can hold
- **THEN** the snapshot SHALL end at the previous complete event and the unfit event SHALL remain in raw history

### Requirement: Snapshot schema v2 is backward compatible

The system SHALL preserve all schema v1 fields and add `covered_event_ids`. It SHALL load v1 and v2 saves without a database migration and SHALL lazily rebuild derived v1 data from unchanged raw history.

#### Scenario: A v1 save continues generation

- **WHEN** a valid v1 snapshot and its raw events are restored
- **THEN** the system SHALL preserve the raw events, rebuild a valid v2 snapshot when compaction is needed, and continue generating context

### Requirement: Long context preserves prioritized information

The system SHALL allocate input space in this order: current request, character authority, ledger facts, recent events, and old history. It SHALL drop or compact lower-priority complete units before higher-priority information.

#### Scenario: Optional context exceeds the remaining budget

- **WHEN** required current request, authority, and ledger facts fit but optional history does not
- **THEN** the required information SHALL remain and optional units SHALL be admitted only while complete

#### Scenario: Required context exceeds the absolute limit

- **WHEN** required information alone exceeds the configured absolute input limit
- **THEN** the system SHALL return an explicit technical budget error without silently slicing it

### Requirement: Large saves retain truthful coverage

The system SHALL build a 600-event synthetic save below the 800,000-token absolute input limit while preserving an exact mapping from each claimed snapshot event to one complete entry.

#### Scenario: Six hundred events are compacted

- **WHEN** 600 ordered events are rendered with production context settings
- **THEN** the result SHALL remain below 800,000 tokens and no snapshot SHALL claim a partial or missing event
