## Why

Several failures that previously surfaced late in Playwright were not browser-only bugs. API route drift, removed endpoint assumptions, response-shape mismatches, and basic test-layer wiring can be detected faster and more deterministically before a browser starts.

## What Changes

- Add backend route-table contract coverage for the API endpoints currently exercised by browser API-contract tests.
- Add negative contract coverage for deprecated endpoints that must stay absent.
- Wire the route contract into the pre-E2E test layers so drift fails before Playwright.
- Keep E2E focused on browser-visible integration, not first-line route discovery.

## Impact

- Tests: new no-mock contract coverage and `test.sh` layer wiring.
- CI: earlier failures for route drift and deprecated endpoint regressions.
- No production behavior changes.
