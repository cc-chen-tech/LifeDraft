# Google Font Build Network Dependency

Date: 2026-06-09
Severity: P1
Status: Fixed locally, pending full-suite verification and deployment

## Evidence

- Command: `./test.sh all`
- Passed before failure: preflight, mypy, imports, contract, and real DB layers.
- Failure point: Layer 5 E2E setup, during `npm run build`.
- Error: Turbopack could not fetch `Noto Sans SC` assets from `fonts.gstatic.com`, then failed to resolve `@vercel/turbopack-next/internal/font/google/font`.
- Impact: full local validation and production-like E2E runs could fail for network availability rather than application code.

## Root Cause

- `frontend/src/app/layout.tsx` imported `Noto_Sans_SC` and `Noto_Serif_SC` from `next/font/google`.
- Next/Turbopack tried to fetch Google font files during build.
- The local runner timed out on several font URLs, turning an external font-network dependency into a hard build failure.

## Fix

- Removed `next/font/google` usage from `frontend/src/app/layout.tsx`.
- Defined `--font-sans-sc`, `--font-serif-sc`, and `--font-geist-mono` as local system font stacks in `frontend/src/app/globals.css`.
- Added preflight coverage in `tests/test_gate_preflight_no_mock.py` to prevent reintroducing `next/font/google` in the root layout.

## Regression Tests

- `tests/test_gate_preflight_no_mock.py::test_frontend_layout_does_not_depend_on_google_font_network`

## Verification

- `pytest -q tests/test_gate_preflight_no_mock.py::test_frontend_layout_does_not_depend_on_google_font_network`
  - Result: 1 passed
- `npm --prefix frontend run test:types`
  - Result: passed
- `npm --prefix frontend run build`
  - Result: passed

## Follow-Up

- If a branded font becomes necessary, vendor it as a repo-local `next/font/local` asset instead of using a network-fetched Google font.
