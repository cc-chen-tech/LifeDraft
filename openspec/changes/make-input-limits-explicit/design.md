## Context

Story2 currently has a mixture of Pydantic `max_length` declarations, unbounded request strings, frontend inputs without counters, and a prompt sanitizer that truncates long values. The same semantic field can therefore have different behavior depending on which route receives it.

## Goals / Non-Goals

**Goals:** centralize new-request limits; count text as Unicode characters; measure structured settings as compact UTF-8 JSON bytes; emit actionable 422 errors; make frontend and OpenAPI contracts agree; never silently alter submitted text.

**Non-goals:** migrating or truncating stored saves; constraining internal generated context with these user-input limits; changing narrative generation budgets; redesigning summaries or long-term memory.

## Decisions

### One public input-limit registry

Add named constants and metadata in one backend module. Pydantic models reference those constants, OpenAPI emits their `maxLength` values, and the frontend contract-generation step produces matching TypeScript constants.

### Structured length errors

Text validators report Unicode code-point length. The FastAPI validation handler normalizes length violations to include `field`, `limit`, and `actual_length` while retaining the standard 422 location and error type. Other validation errors keep their existing shape.

### JSON is measured in bytes

Character-setting payloads are serialized as compact UTF-8 JSON and rejected above 262,144 bytes. The validator does not mutate, normalize, or partially retain the object.

### UI prevents accidental overrun but server remains authoritative

Affected editable controls receive native `maxLength` where appropriate plus a visible remaining count near the limit. Controls that can receive programmatic oversized values show an explicit over-limit state and prevent submission. The backend still validates every request.

### Saved data is outside this boundary

Response schemas, database hydration, and legacy save restoration remain permissive. Only request models used for new writes adopt the limits.

## Risks / Trade-offs

- Rejecting previously accepted oversized requests is an intentional API behavior change; structured details make remediation deterministic.
- Native `maxLength` prevents normal typing beyond the limit, so tests also cover pasted/programmatic values and backend rejection.
- Character-setting JSON size depends on UTF-8 encoding, unlike text fields; the error explicitly reports bytes.

## Rollout

Land as a stacked Draft PR, validate contract generation and deterministic UI tests, and avoid any database migration. Production enablement follows the parent narrative/option stack.
