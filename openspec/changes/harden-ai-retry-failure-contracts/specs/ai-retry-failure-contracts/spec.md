## ADDED Requirements

### Requirement: AI retry behavior exposes deterministic recovery semantics
The maintained backend suite SHALL verify that retrying an AI provider injects the
previous failure into later requests, reduces temperature as configured, disables
streaming after the first attempt, and reports the terminal error when exhausted.

#### Scenario: Provider timeout then successful retry
- **WHEN** a provider times out on its first call and succeeds on its second call
- **THEN** the second prompt includes the first failure explanation
- **AND** the second request uses the decayed temperature without a stream callback

#### Scenario: Malformed JSON then valid JSON
- **WHEN** a JSON retry receives malformed content followed by valid JSON
- **THEN** the retry requests valid JSON with feedback and returns the parsed object

#### Scenario: All retry attempts fail
- **WHEN** every provider call fails
- **THEN** the retry layer raises a terminal error containing the last failure
