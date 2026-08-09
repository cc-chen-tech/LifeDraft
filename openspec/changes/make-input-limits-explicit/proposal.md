## Why

Several public request models accept unbounded user text while prompt sanitization silently slices oversized values. That changes user meaning, makes frontend and backend rules drift, and produces unclear failures only after expensive generation starts.

## What Changes

- Define one shared backend contract for new writes: names 50 characters; life vision, feedback, and custom action 500 characters; story dialogue and rewrite instructions 2,000 characters; replacement segments 12,000 characters; full story and voice text 32,000 characters; character-setting JSON 256 KiB.
- Reject oversized new requests with structured HTTP 422 details containing the field name, configured limit, and measured length instead of truncating values.
- Make prompt sanitization fail explicitly when user-controlled text is oversized.
- Expose the same limits in frontend inputs with native limits, remaining-character or over-limit feedback, and generated OpenAPI/TypeScript contracts.
- Preserve all existing saved data unchanged; this change applies only at new request boundaries.

## Impact

- Backend: shared input-limit definitions, Pydantic request schemas, request-validation error shape, and prompt sanitizer behavior.
- Frontend: shared generated contract constants and user-visible counters/errors on affected inputs.
- Tests: boundary-value, structured 422, no-silent-truncation, OpenAPI/TypeScript parity, and focused UI contracts.
- Rollout: stacked after `unify-option-display-budgets`; no saved-data migration, summary/memory change, or production flag enablement.
