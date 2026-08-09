## ADDED Requirements

### Requirement: Maintained gate verifies image executor lifecycle
The maintained backend test selection SHALL run the image thread-pool lifecycle contract in both backend workflows.

#### Scenario: Image executor is shut down
- **WHEN** image executor shutdown is requested and the next caller obtains an executor
- **THEN** the maintained contract MUST require a new usable `ThreadPoolExecutor` instance

#### Scenario: Image executor shutdown is repeated
- **WHEN** shutdown is requested more than once
- **THEN** the maintained contract MUST require the calls to complete without an exception
