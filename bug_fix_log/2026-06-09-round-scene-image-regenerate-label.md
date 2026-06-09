# Round Scene Image Regenerate Label

Date: 2026-06-09

## Problem

Production QA on `https://story101.live/play` found the current-round scene image action displayed as `重生成`.
The same screen also has the story-level `重新生成` action, so the shortened label was both a typo and ambiguous for users and browser automation.

Evidence:

- `agent-browser get text` on the current-round image action returned `重生成`.
- Screenshot: `/tmp/story101-week1-complete-20260609-1947.png`.

## Root Cause

`frontend/src/components/game/RoundSceneImage.tsx` hard-coded the action label as `重生成`.
The component test suite also asserted the same typo, so the regression was encoded as expected behavior.

## Regression Test

Updated `frontend/src/__tests__/components/RoundSceneImage.test.tsx` to query the button by the accessible name `重新生成插画`.
The updated test failed before the component change because the accessible button name was still `重生成`.

## Fix

Changed the visible button text to `重新生成插画`, which makes the action grammatically correct and distinct from the story-level `重新生成` button.

## Verification

- Pending after code change:
  - `cd frontend && npx jest src/__tests__/components/RoundSceneImage.test.tsx --runInBand`
  - `npm --prefix frontend run test:types`
  - `git diff --check`
