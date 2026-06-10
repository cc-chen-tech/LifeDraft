## ADDED Requirements

### Requirement: Deterministic historical summary selection contracts

When selecting historical summaries, the system SHALL only score summaries from earlier weeks,
respect deprecation rules for past history, and preserve deterministic fallback behavior when no
eligible summaries are found.

#### Scenario: Future summaries are never used
- **WHEN** player state `week` is greater than all candidate `weekly_summaries` and `yearly_summaries`
- **THEN** the selector SHALL ignore summaries with non-positive distance and only return from earlier weeks.

#### Scenario: Low-relevance summaries are skipped
- **WHEN** all candidate summaries have zero keyword hits or scores below acceptance threshold
- **THEN** the selector SHALL return `None` for that category.

#### Scenario: Random fallback uses time-decayed probability
- **WHEN** no summary is eligible and `random.random` is deterministic
- **THEN** selections SHALL follow the configured decayed probability path without accessing future data.

### Requirement: Gameplay overdue storyline contracts

When narrative storylines are stale, high-importance lines SHALL be escalated to `overdue` when
the configured waiting period is exceeded.

#### Scenario: Time-sensitive high storyline becomes overdue after 3 weeks
- **WHEN** a high-importance storyline contains a time keyword and is dormant for 3 weeks or more
- **THEN** the system SHALL set `overdue=True` and set `overdue_since_week` to the current week.

#### Scenario: Non-time-sensitive high storyline escalates later
- **WHEN** a high-importance storyline is dormant for 5 weeks or more and has no time keyword
- **THEN** the system SHALL set `overdue=True`.

### Requirement: SSE prefetch and retry contracts

`_prefetch_options` SHALL terminate safely on early-return conditions and clear `session.is_prefetching`
state in all branches.

#### Scenario: No duplicate prefetch when cache exists
- **WHEN** cached options are already present
- **THEN** no new option generation SHALL be triggered and prefetch flags SHALL be finalized.

#### Scenario: Retry status clears SSE cache
- **WHEN** status callback reports `phase=retry`
- **THEN** session cache SHALL be cleared exactly once.

### Requirement: Session service illustration health contracts

Session recovery checks SHALL treat missing image files as actionable and not silently pass.

#### Scenario: Missing character images are disabled only when explicitly missing
- **WHEN** a character image exists in DB but `image_storage.image_exists` returns `False`
- **THEN** session service SHALL mark corresponding image records as inactive and trigger background regeneration.

#### Scenario: Missing scene images are flagged for regeneration
- **WHEN** a scene image record exists but file storage check fails
- **THEN** the scene SHALL be marked as missing so downstream flows can regenerate it.

### Requirement: Era extraction contracts remain backward-compatible

`_extract_era_from_settings` SHALL normalize era values across string and structured formats.

#### Scenario: Era normalization with dict and description
- **WHEN** era input is a dict containing `era_name` or `era_description`
- **THEN** the extracted era SHALL prefer `era_name`, otherwise use first segment of `era_description`.

#### Scenario: Long eras are truncated consistently
- **WHEN** era input is a string longer than 30 characters
- **THEN** the service SHALL return a truncated era preserving the first 30 characters.
