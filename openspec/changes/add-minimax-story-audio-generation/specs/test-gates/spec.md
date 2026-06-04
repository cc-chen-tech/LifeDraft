## ADDED Requirements

### Requirement: MiniMax story audio generation has layered no-mock gates
The system SHALL require test-first coverage for MiniMax story narration and generated music across static analysis, imports, contracts, real DB integration, and browser E2E, and these tests SHALL run through `test.sh`.

#### Scenario: MiniMax provider gates are wired before implementation is complete
- **WHEN** MiniMax story audio generation implementation is claimed complete
- **THEN** `test.sh preflight` MUST validate the OpenSpec change and secret scanning rules
- **AND** `test.sh mypy` MUST include strict type targets for new MiniMax provider and orchestration modules
- **AND** `test.sh imports` MUST include delayed import validation for MiniMax TTS and music providers
- **AND** `test.sh contract` MUST include MiniMax request/response and frontend consumer field contracts
- **AND** `test.sh db` MUST include real database save-read tests for generated narration and music metadata
- **AND** `test.sh e2e` MUST include browser verification for provider audio reading state and generated music queue insertion.

#### Scenario: MiniMax tests use real local IO boundaries
- **WHEN** MiniMax provider tests exercise external-provider behavior
- **THEN** they MUST use real local HTTP or WebSocket test servers or real database sessions as appropriate
- **AND** they MUST NOT monkeypatch provider behavior, mock network calls, skip tests, or mark expected failures.
