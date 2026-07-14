## ADDED Requirements

### Requirement: Pipeline aggregation contracts are maintained
The maintained backend gate SHALL exercise validation-pipeline scoring, priority routing, fast validation, profile filtering, and exception degradation using the existing no-double public contract suite.

#### Scenario: A critical validator fails
- **WHEN** a registered critical validator returns a failed result
- **THEN** the pipeline MUST return a failed result with a critical failure and weighted score deduction

#### Scenario: A validator raises
- **WHEN** a registered validator raises an exception
- **THEN** the pipeline MUST return a non-blocking structured degraded check
