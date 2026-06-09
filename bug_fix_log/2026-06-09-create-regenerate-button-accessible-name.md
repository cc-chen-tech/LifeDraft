# Fix: Create Flow Regenerate Icon Button Accessible Name

Date: 2026-06-09

## Problem

Production browser QA on `story101.live` found that the create-flow feedback regenerate control on non-portrait setting steps appeared as an unnamed icon-only button in the browser accessibility snapshot.

Evidence:

- `docs/qa-evidence/2026-06-09-heartbeat-0737-production/08a-gender-ref-ambiguous.png`
- `docs/story101-production-qa-heartbeat-2026-06-09-0737.md`

The control could still be clicked visually, but automation and assistive technologies had no stable button name to target.

## Root Cause

`frontend/src/app/create/page.tsx` rendered the inline regenerate `Button` with only a `RefreshCw` icon and no text, `aria-label`, or `title`.

## Regression Test

Added:

```text
frontend/src/__tests__/pages/CreatePage.test.tsx
CreatePage > Accessibility > gives the inline setting regenerate icon button an accessible name
```

The test renders the age step with generated content and requires a button named `重新生成年龄阶段`.

## Fix

Added `aria-label` and `title` to the inline regenerate button using the current step label:

```tsx
aria-label={`重新生成${STEP_LABELS[currentStepKey]}`}
title={`重新生成${STEP_LABELS[currentStepKey]}`}
```

## Verification

Command:

```bash
cd frontend && npx jest src/__tests__/pages/CreatePage.test.tsx -t "inline setting regenerate icon button" --runInBand
```

Result:

- `1 passed`

## Remaining Risk

Other icon-only controls should continue to be audited, especially generated scene refresh controls and dialog close controls.
