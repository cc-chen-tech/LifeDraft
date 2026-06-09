# Story101 Production QA Heartbeat - 2026-06-09 06:37 UTC

## Scope

- Production URL: https://story101.live
- Production SHA: `158f11c879fa3ea3c03e578114be6467dbc3d3cb`
- Evidence directory: `docs/qa-evidence/2026-06-09-heartbeat-0637-production/`
- Browser path covered: logout, register, create character, save preset, start opening story, retry opening story, enter play, TTS voice switch, collection, history, settings, MiniMax music, submit first choice.

## Release State

- Local `main` and `origin/main` are both `158f11c879fa3ea3c03e578114be6467dbc3d3cb`.
- ECS `/opt/story2` is also `158f11c879fa3ea3c03e578114be6467dbc3d3cb`.
- Production `/api/health` returned OK and homepage returned HTTP 200.
- GitHub Actions on this SHA still fail before runner logs are available (`log not found`), matching the existing platform runner blocker rather than local test failure.
- Open PRs remain draft-only: #58 draft/UNSTABLE and #54 draft/DIRTY.

## Findings

### P1 - Opening Story First Attempt Can Show `Generation timeout`

Evidence:

- `20-opening-page.png`
- `21-opening-retry-20s.png`
- `22-opening-retry-success.png`

Steps:

1. Register a new user.
2. Create a new character named `顾晨`.
3. Save the preset.
4. Click `开始游戏`.
5. On `/story/opening`, the first attempt showed `故事生成失败: Generation timeout`.
6. Click `重试`; the story later appeared successfully.

Impact:

- The game is not permanently blocked because retry recovered, but first-run confidence is poor.
- Production logs show game creation and supporting generation succeeded; the issue appears to be opening-story streaming timeout/recovery behavior rather than a hard backend outage.

Root-cause hypothesis:

- The opening-story SSE path emits a timeout error before a slow generation completes or before a cached completed result is surfaced to the first client.
- The frontend treats the error as terminal even though retry can obtain a usable story.

Status:

- Unfixed in this heartbeat.
- Needs regression coverage around slow first-token opening generation and retry/cache recovery.

### P1 - Week 1 Story Generation Is Too Long Before Choices Appear

Evidence:

- `24-play-after-10s.png`
- `26-week1-options.png`
- `27-week1-options-ready-after-longwait.png`
- `35-after-choice-20s.png`
- `36-after-choice-complete-enter-midweek.png`

Steps:

1. Enter `/play` after the recovered opening story.
2. Wait for the first event.
3. The page displayed a very long story body and `正在处理中...`.
4. After a long wait, three choices eventually appeared.
5. Selecting choice 1 started another long continuation with `正在处理中...`.
6. The result eventually completed and exposed `进入周中`, so this is a latency/clarity defect rather than a hard stuck state in this run.

Impact:

- The latest duplicate `choice-sync` recovery fix appears to avoid the previous hard stuck state, because choices eventually appeared.
- However, the round can feel stalled for more than a minute, and `恢复当前进度` appears while generation is still legitimately running.

Root-cause hypothesis:

- Story continuation length and post-generation option validation are too heavy for a single interaction turn.
- The UI exposes recovery controls during normal long-running generation, which can confuse users into thinking state is broken.

Status:

- Unfixed in this heartbeat.
- Needs tests for bounded story display/option latency messaging and recovery-button gating.

### P2 - Created Modern Scenario Still Drifts From Requested Year

Evidence:

- `07-create-basic-filled.png`
- `11-create-world-ready.png`

Steps:

1. Set life vision to `在2026年的杭州做独立游戏制作人...`.
2. Continue through generated setting steps.

Observed:

- World generation used `2024年的杭州`.
- Opening story also started on `2024年1月3日`.

Impact:

- The generated story remains plausible, but violates the explicit requested year.

Status:

- Unfixed in this heartbeat.

### P2 - Initial Wealth Display Still Does Not Match Scenario Funding

Evidence:

- `24-play-after-10s.png`

Observed:

- HUD showed `财富: ¥10,000`.
- Generated story text later referenced `5万启动资金` and `注册资金才十万块`.

Impact:

- The HUD financial state is less believable for a modern startup scenario and conflicts with generated narrative details.

Status:

- Unfixed in this heartbeat.

### P2 - Music Player Works But One Click Path Hung `agent-browser`

Evidence:

- `32-music-state-after-click-hang.png`
- `33-before-choice.png`
- `34-music-play-click.png`

Observed:

- Clicking the compact `AI MiniMax 叙事MiniMax` cursor-interactive area caused the CLI click command to hang.
- Pressing Escape and using explicit player controls worked; playback switched to a `暂停` state and progress advanced.

Impact:

- Core playback appears functional, but the compact hit target is brittle for automation and potentially ambiguous for users.

Status:

- Unfixed in this heartbeat.

## Positive Checks

- Registration succeeded.
- Full character creation succeeded.
- Character detail panel opened.
- Preset save succeeded.
- Retry opening story succeeded.
- TTS voice switch to `沉稳男声` started generation and playback controls appeared.
- Collection panel opened.
- History panel opened and did not overlap with collection.
- Settings menu opened.
- MiniMax music appeared and explicit playback controls worked.
- First choice submission did not immediately hit the prior duplicate choice-sync hard error.
