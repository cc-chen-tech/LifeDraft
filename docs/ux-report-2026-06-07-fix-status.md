# UX Report 2026-06-07 Fix Status

Date: 2026-06-08
Branch: `codex/deep-ux-p0-fixes`
PR: #51

This note tracks follow-up fixes for `docs/ux-report-2026-06-07.md`.

## Closed In This Follow-Up

- Entity collection UI path now auto-collects recognized story entities when the collection is empty.
  - Unit coverage: `frontend/src/__tests__/stores/useCollectionStore.test.ts`
  - Browser coverage: `frontend/e2e/no-mock-regression.spec.ts`
- Persona drift detection now retries a round event when the generated story ignores all configured key people and fabricates a new named cast.
  - Backend coverage: `tests/test_gate_gameplay_behavior_no_mock.py`
- Modern debt/crisis music intent now prefers financial suspense/instrumental search terms and filters love-pop or `type beat` terms from top search queries.
  - Contract coverage: `tests/test_story_music_recommendation_contract.py`
- Music player queue advance now wraps or advances persisted playlists instead of getting stuck on the same track.
  - Store coverage: `frontend/src/__tests__/stores/useMusicStore.musicQueuePolicy.test.ts`
- Modern/2020s story prompts now require `第N周·周一/周中/周末` style timeline titles instead of classical `第X回 + 七字对仗标题`.
  - Prompt coverage: `tests/test_player_name_in_prompts_contract.py`, `tests/test_era_anachronism_contract.py`
- Wealth display now uses the configured currency symbol before the amount, for example `财富: ¥50,000`.
  - Component coverage: `frontend/src/__tests__/components/game/StatusBar.test.tsx`
- Summary/settings mismatch has focused guards: summary quick action must not trigger regeneration, and settings must not open the chat panel.
  - Coverage: `frontend/src/__tests__/components/ChatBar.test.tsx`, `frontend/e2e/quality-level.spec.ts`

## Verification

- Focused backend prompt/music/persona tests: 18 passed.
- Focused frontend unit tests: 74 passed.
- `./test.sh e2e`: core 301 passed, AI music queue 1 passed, story voice 8 passed, MiniMax story audio generation 4 passed.

## Still Not Claimed As Production-Complete

- Remote GitHub checks are blocked by GitHub billing/spending-limit status, not by retrievable job logs.
- Production MiniMax validation still depends on correctly setting MiniMax secrets in the deployed environment and redeploying.
- A real long manual playthrough to week 4 should be rerun after deployment, because local deterministic E2E is not a substitute for live model/runtime behavior.
