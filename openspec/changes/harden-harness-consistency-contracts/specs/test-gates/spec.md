## ADDED Requirements

### Requirement: Maintained harness contracts are symmetric
The maintained backend coverage workflow and maintained backend test workflow SHALL list the verified temporal and harness-consistency contract suites in the same order.

#### Scenario: Workflow selection is compared
- **WHEN** the maintained backend test selections are extracted from both workflows
- **THEN** their ordered test-file lists MUST be identical

### Requirement: Maintained coverage floor follows repeated evidence
The maintained backend coverage floor SHALL only be raised after two runs of the exact expanded maintained selection meet the proposed whole-percent threshold.

#### Scenario: Expanded maintained gate is measured
- **WHEN** the verified harness contract suites are added to the maintained selection
- **THEN** the coverage floor MUST remain at or below the repeated measured whole-percent result
