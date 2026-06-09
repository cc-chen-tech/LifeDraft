# Story101 Production QA Heartbeat - 2026-06-09 08:41 UTC

## Scope

- Repository: `cc-chen-tech/LifeDraft`
- Production: `https://story101.live`
- Local workspace: `/Users/luicy/story2`
- Production commit verified on ECS: `94435ac9c59e7fe8b6c9e13916b9becab0748671`
- Browser session game id: `105`
- Evidence folder: `docs/qa-evidence/2026-06-09-heartbeat-0841-production/`

## Release State

- Open PRs:
  - `#58` `[codex] Complete modern setting authority OpenSpec verification`: draft, not merged.
  - `#54` `[codex] Fix 2026-06-08 story quality and music recovery`: draft, not merged.
- Local and remote `main` both point at `94435ac9c59e7fe8b6c9e13916b9becab0748671`.
- ECS `/opt/story2` points at the same commit.
- ECS backend health: `{"status":"ok","active_sessions":1}`.
- Public health: `https://story101.live/api/health` returns `ok`.
- Public homepage: HTTP 200, ETag `"641409ne7ebld"`.
- GitHub Actions for `94435ac9` still fail before useful runner logs. Sampled workflows `Backend Tests`, `Frontend Tests`, and `Deploy Production` all returned `log not found`.

## Gameplay Progress

Started from the existing production QA game at Week 1 weekend and continued through:

- Week 1 weekend completion.
- Week 2 Monday event and choice.
- Week 2 midweek event and choice.
- Week 2 weekend completion.
- Week 3 Monday event and choice result.

The session has not yet reached Week 4. Current visible state is Week 3, with an `进入周中` button available.

## Evidence Captured

- `01-current.png`: starting state at Week 1 weekend.
- `02-weekend-result.png` and `02-weekend-result-innerText.txt`: Week 1 completion.
- `03-week2-options.png` and `03-week2-options-innerText.txt`: Week 2 opening options and text.
- `04-history-open.png` and `04-history-open-innerText.txt`: history panel.
- `05-collection-open.png`: collection panel.
- `06-smart-recognition.png` and `07-smart-recognition-result.png`: smart recognition flow.
- `08-friends-open.png` and `09-after-friends-return-blank.png`: friends panel and stale-client blank screen.
- `10-after-reload-recovered.png`: hard reload recovery.
- `11-settings-open.png`: settings menu.
- `12-tts-voice-auto.png`: TTS voice and auto-read attempt.
- `13-week2-choice-result.png` and `13-week2-choice-result-innerText.txt`: Week 2 choice result with TTS.
- `14-week2-mid-options.png`, `15-week2-mid-result.png`, `16-week2-weekend-options.png`, `17-week2-complete.png`, `17-week2-summary.txt`, `18-week3-options.png`: progression evidence through Week 3.

## Findings

### P0/P1: Stale Production Client Can Blank After Deploy

Reproduction:

1. Continue an already-open `/play` session that was loaded before the latest manual ECS deploy.
2. Open `好友`.
3. Click `返回`.

Observed:

- The page became blank.
- Console logged missing Next chunks:
  - `Failed to load resource: the server responded with a status of 404`
  - `Refused to execute script from 'https://story101.live/_next/static/chunks/f3d179a919da6a16.js' because its MIME type ('text/plain') is not executable`
  - `Refused to apply style from 'https://story101.live/_next/static/chunks/ea3c7ae397292aad.css' because its MIME type ('text/plain') is not a supported stylesheet MIME type`
- Hard reload recovered the same game state.

Severity:

- P0 if it affects active users during each deploy.
- P1 if limited to long-lived pre-deploy tabs.

Root-cause hypothesis:

- ECS deployment replaces old Next static assets without retaining previous build chunks. Existing browser clients then lazy-load stale chunk names after deployment and crash/blank.

Status:

- Unfixed.

Recommended fix:

- Add stale-chunk error recovery in the frontend, plus a deployment/static-asset retention strategy or a client build-version refresh prompt.

### P1: Generation Stages Lack Progress Feedback

Reproduction:

1. Submit any story choice from Week 1 weekend through Week 3.
2. Observe the UI for the next 40-70 seconds.

Observed:

- The UI repeatedly shows only toolbar buttons.
- Sometimes `朗读故事` controls disappear briefly and later reappear.
- `恢复当前进度` appears near completion, but there is no clear explanation of the current generation step, estimated wait, or heartbeat status.

Severity:

- P1. It no longer hard-times-out, but it still feels frozen during normal production waits.

Status:

- Unfixed.

### P1: Modern 2026 Scenario Still Summarizes as 2024

Evidence:

- `17-week2-summary.txt`: `2024年1月第2周`.
- `02-weekend-result-innerText.txt`: `2024年1月第1周`.
- History panel also shows `(2024年1月第1周)`.

Observed:

- The story content follows the requested modern AI startup path, but summaries/history date labels drift to 2024.

Severity:

- P1. It damages narrative consistency and user trust.

Status:

- Unfixed.

### P1/P2: Music Queue and MiniMax Music Remain Partially Broken

Observed:

- Console repeatedly logs `MusicPlayer Received 0/0 song URLs from backend`.
- Console logs `422 Unprocessable Entity`.
- UI sometimes says `正在生成原创场景音乐，完成后加入下一首`.
- Player sometimes shows `0:00 / 0:00`.
- Recommendation count remains low: `推荐歌曲 (2首)` and `匹配歌曲较少`.

Severity:

- P1 for broken resource flow / 422.
- P2 for matching quality and queue depth.

Status:

- Unfixed.

### P2: Dialog Accessibility and Localization Issues

Observed:

- Console warning: `Missing Description or aria-describedby={undefined} for {DialogContent}`.
- Multiple dialogs expose an English `Close` button in the accessibility tree.
- Friends panel displayed text controls like `返回`, `添加好友`, `发送`, but accessibility snapshot showed `(no interactive elements)`.

Severity:

- P2. It affects accessibility, keyboard navigation, localization polish, and testability.

Status:

- Unfixed.

### P2: Scene Illustration State Is Slow or Ambiguous

Observed:

- Scene image flow repeatedly logs `Generation still in progress`.
- UI shows `正在获取或生成最新场景插画...`.
- `重生成` and `刷新` buttons can remain disabled for extended periods after story text is ready.

Severity:

- P2.

Status:

- Unfixed.

### Positive Notes

- The previous opening-story hard timeout did not recur.
- Main story text now has paragraphs and punctuation that are generally readable.
- Smart recognition completed in roughly 15 seconds and identified key characters.
- Collection panel found 7 characters and 2 landmarks.
- Hard reload preserved game progress after the blank screen.
- TTS can start with `清亮中性`, show `暂停朗读`, and expose a `停止` control.

## Next Priorities

1. Fix stale chunk blank-screen recovery and deployment static asset retention.
2. Fix 2026/2024 timeline source-of-truth drift.
3. Add visible generation progress/heartbeat states for long-running story generation.
4. Fix music 422 and 0/0 queue behavior.
5. Fix dialog `aria-describedby`, localized close labels, and friends panel semantics.
6. Continue this same production game from Week 3 `进入周中` to at least Week 4 after the next heartbeat.
