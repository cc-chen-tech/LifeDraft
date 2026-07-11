## Why

Production QA found that smart recognition omits clearly named new people, returns summaries cut from the middle of sentences, and leaves the add action spinning for more than a minute after the write. These failures make collection results incomplete and make a successful save look stuck.

## What Changes

- Admit clearly named people found in story prose even when relationship metadata has not been updated yet, while retaining false-positive filtering and existing-entity exclusion.
- Build recognition context from complete sentence boundaries and keep the named entity inside the bounded summary.
- Complete the add interaction as soon as the durable add response succeeds, then refresh collection details without keeping the add dialog blocked.
- Add immutable no-mock static, import, contract, real DB, and browser tests to `test.sh`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `collection-recognition-gating`: Recognize clear prose-only people and return sentence-complete entity contexts without admitting known false positives.
- `collection-stability`: Separate durable add completion from the slower collection-detail refresh so the UI gives prompt, accurate feedback.

## Impact

Affected areas are the entity recognition service, collection API/store contracts, collection dialog browser flow, real game-state persistence, and all five repository test layers. No endpoint path or request payload is removed.
