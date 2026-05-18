## ADDED Requirements

### Requirement: Private ID Login Payload Is Contract-Compatible

The login UI SHALL submit the saved private credential using the field accepted by the backend authentication API.

#### Scenario: User submits one-time private ID
- **Given** a user has a private ID displayed after registration
- **When** the user submits that value in the login dialog
- **Then** the frontend SHALL send `private_id` or the backend SHALL accept the submitted alias
- **And** a valid private ID SHALL authenticate without a validation-field error.

### Requirement: Login Errors Are Specific

The login UI SHALL distinguish request validation, invalid credential, and transient server/network errors.

#### Scenario: Backend returns validation details
- **Given** the backend rejects login because the payload field is missing
- **When** the login dialog receives that response
- **Then** it SHALL show a field/contract-specific error
- **And** it SHALL NOT show only `Request failed`.
