## ADDED Requirements

### Requirement: StoryService provider-free recovery coverage
The maintained backend suite SHALL cover StoryService's public compression delegation and custom-choice recovery behavior without external providers or mock frameworks.

#### Scenario: State extraction delegates current context
- **WHEN** compression or world-update methods receive story state inputs
- **THEN** the configured provider receives the story, choice, language, and state inputs and its result is returned unchanged

#### Scenario: Custom choice strips prompt-injection framing
- **WHEN** a player supplies a custom choice containing unsafe instruction framing
- **THEN** the provider receives sanitized user content and the successful effects contract has all resource keys

#### Scenario: Custom choice provider remains invalid
- **WHEN** two result-generation attempts return invalid payloads or raise errors
- **THEN** StoryService returns its localized deterministic fallback result

### Requirement: Maintained test list parity
The coverage and backend-test workflows SHALL list the StoryService recovery module in the same order.

#### Scenario: Maintained workflows enumerate tests
- **WHEN** CI builds its backend coverage and backend-test command lists
- **THEN** both lists include the StoryService recovery module exactly once at the same position
