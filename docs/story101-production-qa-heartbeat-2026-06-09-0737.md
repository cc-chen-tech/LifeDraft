# Story101 Production QA Heartbeat - 2026-06-09 07:37 UTC

## Scope

- Production: `https://story101.live`
- Deployed commit verified on local `main`, remote `origin/main`, and ECS `/opt/story2`: `a20a0e5cf5505d037ce1c14248df716ca5442ee7`
- Evidence: `docs/qa-evidence/2026-06-09-heartbeat-0737-production/`
- Browser flow: existing authenticated production session, new game creation from home page, opening story, week 1 start/midweek/weekend progression.

## Release State

- Open PRs:
  - `#58` `[codex] Complete modern setting authority OpenSpec verification`: draft, `UNSTABLE`, not merged.
  - `#54` `[codex] Fix 2026-06-08 story quality and music recovery`: draft, `DIRTY`, not merged.
- GitHub Actions on `main` still fail before useful logs are available. `gh run view --log-failed` returns `log not found`, so this remains a runner/platform blocker rather than a code-log failure.
- ECS production was already manually deployed to `a20a0e5c`; backend was healthy and public `https://story101.live/api/health` returned `{"status":"ok"}`.

## Production Validation

### Confirmed Fixed

- P1 opening story transient timeout: fixed in production.
  - Evidence: `13-game-created-or-error.png`, `15-opening-after-wait-busy.png`
  - Console evidence showed `[SSE] Complete event received`, `Generation complete, length: 1079`.
  - No `故事生成失败: Generation timeout` appeared in this run.

### Functional Coverage Completed

- Home page buttons visible: continue game, new game, load save, presets, logout.
- New game creation:
  - basic name and life vision input
  - AI-generated age, gender, world, portrait/appearance
  - feedback/regenerate on gender step
  - start game
- Opening story:
  - streamed story text
  - generated illustration controls appeared
  - start-life button created game `105`
- Week 1 gameplay:
  - initial event choices generated
  - collection panel opened and listed recognized characters
  - history panel opened and correctly replaced collection panel
  - settings menu opened; narrative quality menu exposed fast/expert/master
  - story read-aloud triggered and voice selector allowed all three voices
  - summary panel opened
  - music player expanded; play/next/MiniMax entry interactions responded
  - week 1 start, midweek, and weekend generation paths were exercised

## Defects And Follow-Up

### P1 - Round Progression Is Too Slow And Gives Weak Progress Feedback

- Repro:
  1. Create a new game.
  2. Start opening story and then enter week 1.
  3. Submit choices through start, midweek, and weekend.
- Evidence:
  - `13-game-created-or-error.png`
  - `15-opening-after-wait-busy.png`
  - `27a-week2-wait-current.png`
  - `29a-midweek-current.png`
  - `33a-weekend-current.png`
  - `34-weekend-after-busy.png`
- Observed:
  - Opening story eventually completed, but took long enough for browser wait commands to hit a busy/unresponsive state.
  - Multiple week-stage generations exceeded 30-60 seconds.
  - The UI often only showed generic generation/recovery controls, without estimated progress or clear final-state transition.
- Root-cause hypothesis:
  - Story generation remains long-form and stage prompts can produce thousands of characters before options are available.
  - Client wait/progress conditions are tied to generic text rather than structured phase data.
- Status: unfixed.

### P2 - Modern Year Setting Drifted From 2026 To 2024

- Repro:
  1. Enter life vision: "在2026年的上海创业..."
  2. Let AI generate world and opening story.
- Evidence:
  - `09-world-options.png`
  - `13-game-created-or-error.png`
  - `15-opening-after-wait-busy.png`
- Observed:
  - Generated world and opening story repeatedly used `2024`, despite explicit `2026` input.
- Root-cause hypothesis:
  - Setting generation prompts still carry a default modern-era anchor or do not extract/enforce explicit user year constraints.
- Status: unfixed. Related to draft PR `#58`; not merged because it is draft/unstable.

### P2 - Inline Regenerate Icon Button Had No Accessible Name

- Repro:
  1. Open create flow on an AI-generated non-portrait step.
  2. Inspect interactive snapshot or query by button role/name.
- Evidence:
  - `08a-gender-ref-ambiguous.png`
  - Existing production snapshot exposed the refresh button as unnamed `button`.
- Root-cause hypothesis:
  - `frontend/src/app/create/page.tsx` rendered an icon-only `Button` without `aria-label` or `title`.
- Status: fixed locally in this heartbeat.

### P2 - Music Queue Logs Are Confusing And Sometimes Return 422

- Repro:
  1. Expand music player during week 1.
  2. Play/skip/click MiniMax track entry.
- Evidence:
  - `24-music-panel.png`
  - `25-music-interactions.png`
  - Console showed `Received 0/0 song URLs from backend`, `Preloaded next song`, and `Failed to load resource: the server responded with a status of 422`.
- Root-cause hypothesis:
  - Music URL fetch and MiniMax queue state are not clearly separated in client logs, and one backend request path rejects incomplete or stale payloads.
- Status: unfixed.

### P2 - DialogContent Accessibility Warning

- Repro:
  1. Open collection/history/summary related dialogs during play.
  2. Inspect console.
- Evidence:
  - Console warning: `Missing Description or aria-describedby={undefined} for {DialogContent}`.
- Root-cause hypothesis:
  - Some Radix dialog content lacks `DialogDescription` or explicit `aria-describedby`.
- Status: unfixed.

## Local Fix In This Heartbeat

- Added an accessible name to the create-flow inline regenerate icon button:
  - `aria-label="重新生成{步骤名}"`
  - `title="重新生成{步骤名}"`
- Added regression test:
  - `frontend/src/__tests__/pages/CreatePage.test.tsx`
  - `CreatePage › Accessibility › gives the inline setting regenerate icon button an accessible name`

## Verification

```bash
cd frontend && npx jest src/__tests__/pages/CreatePage.test.tsx -t "inline setting regenerate icon button" --runInBand
```

Result: passed.

## Next Priority

1. P1: reduce generation wait or provide structured progress/timeout recovery per stage.
2. P2: enforce explicit user year constraints across setting generation and opening story.
3. P2: trace the MiniMax/music 422 request and add clearer queue-state tests.
4. P2: add missing `DialogDescription` or `aria-describedby` for dialogs.
