## Implementation

- [x] Reproduce `handleChoiceComplete` calling `setStoryText` from a complete payload after streaming has already handled story text.
- [x] Add regression coverage for complete payloads with `event_description`.
- [x] Remove complete-callback story text mutation while preserving fallback and recovery text replacement.
- [x] Preserve complete-only SSE fallback at the choice hook layer when no story chunks arrive.
- [x] Run focused choice completion tests.
- [x] Run relevant frontend preflight tests.
- [x] Run OpenSpec strict validation.
