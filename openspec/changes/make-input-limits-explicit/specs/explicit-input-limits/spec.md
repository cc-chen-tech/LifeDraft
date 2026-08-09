## ADDED Requirements

### Requirement: New text writes have explicit shared limits

The system SHALL accept names up to 50 Unicode characters; life vision, feedback, and custom action up to 500; story dialogue and rewrite instructions up to 2,000; replacement segments up to 12,000; and full story and voice text up to 32,000.

#### Scenario: Exact boundary is submitted

- **WHEN** a new request contains a text field exactly at its documented limit
- **THEN** the API accepts the field unchanged

#### Scenario: Text exceeds its boundary

- **WHEN** a new request contains one additional Unicode character beyond its limit
- **THEN** the API returns HTTP 422 with the field name, limit, and actual length

### Requirement: Character-setting writes have an explicit byte limit

The system SHALL reject new character-setting JSON payloads whose compact UTF-8 representation exceeds 262,144 bytes and SHALL NOT alter existing stored settings.

#### Scenario: Multibyte setting exceeds the byte limit

- **WHEN** a new character-setting object serializes above 262,144 UTF-8 bytes
- **THEN** the API returns HTTP 422 with byte unit, limit, and actual byte length

### Requirement: Oversized input is never silently truncated

The system SHALL either accept a complete user value or reject it explicitly before prompt construction; it SHALL NOT use slicing to change oversized user-controlled text.

#### Scenario: Prompt sanitizer receives oversized user text

- **WHEN** user-controlled text exceeds its configured limit
- **THEN** sanitization raises a typed length error containing the limit and actual length and preserves the original value

### Requirement: Client and server expose the same limits

The frontend SHALL derive named input limits from the API contract, show remaining or over-limit feedback for editable fields, and prevent submission of known oversized values.

#### Scenario: Generated contract is checked

- **WHEN** the OpenAPI and generated TypeScript contracts are compared
- **THEN** every named limit has the same numeric value

### Requirement: Legacy saved data remains readable

The system SHALL apply the limits to new request writes only and SHALL NOT migrate, truncate, or reject existing saved data during restore.

#### Scenario: Legacy save contains oversized text

- **WHEN** an existing save with text above a new request limit is loaded
- **THEN** the complete stored value remains available
