## ADDED Requirements

### Requirement: Overdue storyline maintenance coverage
The maintained backend suite SHALL cover NarrativeManager's deterministic overdue-storyline escalation rules.

#### Scenario: Urgent and ordinary high-priority storylines reach their thresholds
- **WHEN** high-priority storylines have been unmentioned for their applicable urgent or ordinary threshold
- **THEN** they are marked overdue once with the current week recorded

#### Scenario: Ineligible storylines are preserved
- **WHEN** a storyline is already overdue, medium priority, or below its threshold
- **THEN** escalation leaves it unchanged and does not count it again

### Requirement: Habit lifecycle maintenance coverage
The maintained backend suite SHALL cover NarrativeManager habit weakening, removal, and replacement transitions.

#### Scenario: Existing habits weaken or disappear
- **WHEN** a moderate or emerging habit receives a weaken update
- **THEN** it is downgraded or removed and records the current observation week when retained

#### Scenario: Habits are explicitly removed or changed
- **WHEN** a matching habit receives remove or change updates
- **THEN** it is deleted or replaced with validated state; a missing changed habit becomes a normalized new record

### Requirement: Maintained workflow parity
The backend coverage and backend-test workflows SHALL enumerate the narrative maintenance module identically.

#### Scenario: CI derives the maintained test lists
- **WHEN** both backend workflow test commands are parsed
- **THEN** the narrative maintenance module occurs exactly once at the same position
