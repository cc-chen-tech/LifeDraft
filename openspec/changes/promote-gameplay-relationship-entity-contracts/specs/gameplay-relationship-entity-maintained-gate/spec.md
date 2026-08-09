## ADDED Requirements

### Requirement: Gameplay state authority contracts are maintained
The maintained backend workflows SHALL execute the entity-recognition task, character-introduction, and relationship-service contracts.

#### Scenario: Gameplay state regression
- **WHEN** a lifecycle, introduction queue, compatibility, or event-trigger invariant regresses
- **THEN** both maintained backend workflows fail before release.

### Requirement: Promoted gameplay suites remain isolated
The promoted gameplay contracts SHALL execute entirely in-process with concrete state, without external providers, browser execution, or mock APIs.

#### Scenario: Isolated execution
- **WHEN** CI invokes the maintained backend suite with test environment variables
- **THEN** all promoted gameplay contracts complete deterministically.

### Requirement: Maintained workflow parity includes gameplay suites
The coverage and backend-test workflows SHALL list the promoted gameplay suites in identical order.

#### Scenario: Ordered extraction
- **WHEN** test paths are extracted from both maintained workflow commands
- **THEN** the resulting ordered lists are identical.
