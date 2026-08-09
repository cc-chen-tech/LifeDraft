## ADDED Requirements

### Requirement: Target length drift does not erase usable prose

The round generator SHALL retain complete, non-empty prose that passes local
consistency even when target-length or paragraph-shape diagnostics are present.

#### Scenario: Expert prose exceeds the target range

- **WHEN** an expert round produces complete prose of 1329, 1710, or 2315 Unicode
  characters
- **THEN** the completed event contains that prose and exactly three options
- **AND** the behavior holds with the constraint Harness enabled or disabled

#### Scenario: A bounded shape repair still drifts

- **WHEN** the initial prose is usable and its shape repair still reports only
  length or paragraph diagnostics
- **THEN** the latest usable prose remains eligible for the completed event
- **AND** no length diagnostic clears the recovery candidate

### Requirement: Exhaustion recovers prose and contextual options

The generator SHALL recover the latest usable prose if a later provider call,
deadline, validation repair, or option generation step is exhausted.

#### Scenario: Provider fails after usable prose

- **WHEN** a usable story has been produced and a later repair call fails
- **THEN** the generator returns the latest usable story
- **AND** it supplies exactly three contextual fallback options

### Requirement: Consistency repair inherits its request budget

Consistency repair SHALL use the active quality-level output-token budget.

#### Scenario: Expert consistency rewrite

- **WHEN** an expert story triggers a consistency rewrite
- **THEN** that provider call uses the expert output-token budget
- **AND** it does not use a fixed 8192-token override
