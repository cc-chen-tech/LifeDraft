## ADDED Requirements

### Requirement: Maintained gate validates round system orchestration
The maintained backend selection SHALL exercise round-service initialization, current-event delegation, and safe helper behavior through `RoundSystemMixin`.

#### Scenario: Round system is first accessed
- **WHEN** a game-loop consumer accesses round services
- **THEN** the maintained contract MUST require lazy initialization to create the expected service components
