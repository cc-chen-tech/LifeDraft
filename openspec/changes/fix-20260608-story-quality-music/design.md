## Context

The 2026-06-08 live report shows a split between surface fixes and core quality regressions. MiniMax TTS, entity collection, endpoint paths, titles, choices, and scene images improved, but required preset people never entered the story, an invented character replaced a preset friend, music recommendations ignored their own exclusion brief, `/api/music/generate` became slow or unstable, and initial wealth defaulted to `10,000` instead of the configured `¥50,000`.

Existing code already has useful pieces: `character_settings.relationships.key_people`, `WorldModel.build_constraints_text`, quick validation, story validation/retry loops, music brief negative cues, NetEase search pools, MiniMax generation, real DB tests, and Playwright fixtures. The gap is that these pieces do not yet enforce one canonical player setup across prompts, validators, persistence, and UI.

## Goals / Non-Goals

**Goals:**

- Make preset key people authoritative for story prompts, validation, and entity/relationship synchronization.
- Ensure music recommendation filtering happens on returned playable songs and not only in the generated brief.
- Bound music generation latency and convert provider failures into structured JSON degradation.
- Preserve configured wealth amount and currency unit through game initialization and frontend display.
- Add tests first, wire every new test into `test.sh`, and keep the tests unchanged after they are written.

**Non-Goals:**

- Rewriting the story engine or changing the full narrative architecture.
- Replacing NetEase search or MiniMax music generation with another provider.
- Retrofitting already-corrupted live saves where an invented character has become canonical history.
- Adding new paid membership behavior beyond existing MiniMax music/TTS flows.

## Decisions

### Decision 1: Treat `character_settings.relationships.key_people` as authoritative setup facts

The prompt layer will emit a compact required-cast block containing name, role, relationship, and description. The validation layer will measure story coverage for required names and reject obvious substitution drift. The collection layer will prefer canonical preset names when extracted candidates match a known role/relationship.

Alternative considered: only strengthen the generation prompt. This was rejected because the live issue persisted across many hours; prompt-only guidance is too weak when retry and extraction layers can still accept a drifted cast.

### Decision 2: Add deterministic validators before adding more LLM retries

Validation will be string/fact based first: required names, role facts, and invented-substitute cues. If required preset names are absent below the threshold, the retry prompt gets a direct correction. This keeps tests deterministic and avoids depending on model behavior.

Alternative considered: ask the model to self-grade relationship adherence. This was rejected because it is slower, non-deterministic, and hard to cover without mocks.

### Decision 3: Filter songs by canonical song key, negative cue variants, and weak metadata

Music pool supplement will track both provider IDs and normalized `(song name, artist)` keys. Negative cue matching will normalize whitespace/case and support cue families such as `等你下课`, `小幸运`, `断了的弦`, `type beat`, meme songs, vocal-pop, and unrelated anime OPs when the brief is workplace/suspense/background.

Alternative considered: rely on better search queries. This was rejected because the report showed the brief already had negative cues, yet returned songs were still wrong.

### Decision 4: Bound MiniMax music generation at service/API boundaries

The MiniMax request payload will use accepted audio settings and explicit provider timeout. The API route will return JSON with `available: false`/`error` metadata when generation fails or times out, without blocking story choices or returning gateway HTML.

Alternative considered: let frontend abort the fetch. This was rejected because production symptoms included backend/gateway failures; the backend must degrade correctly even if the browser waits.

### Decision 5: Use configured wealth as the source of truth for initial state

`character_settings.wealth.wealth` (or compatible numeric aliases) becomes the initial `PlayerState.wealth` when present. Currency metadata remains in `character_settings.wealth`, while the frontend formats the numeric state with the configured currency unit.

Alternative considered: keep state in abstract "currency points" and only change the label. This was rejected because the user-visible setup explicitly says `¥50,000`; showing `10,000 货币` is a data contract failure, not just copy.

## Risks / Trade-offs

- Required-cast validation could over-constrain scenes where not every person should appear immediately -> mitigate by setting coverage thresholds by phase and forcing at least one overdue required person per early round instead of requiring all names in every paragraph.
- Canonicalizing invented substitutes could rename a legitimate new character -> mitigate by only applying canonical replacement when role/relationship cues match a preset person and the canonical person is currently missing.
- Stricter music filtering may return fewer NetEase tracks -> mitigate by allowing structured empty/degraded recommendation and still enqueuing AI generated music when enabled.
- Music generation timeout may stop a slow but eventually valid provider response -> mitigate by using the existing provider timeout config and caching successful later retries by brief hash.
- Existing saves may already contain `10,000` wealth -> mitigate by fixing new-game initialization and read/display contracts, not rewriting historical saves automatically.

## Migration Plan

No schema migration is required. The change updates behavior for newly generated stories, newly initialized games, and future music requests. Existing games keep their stored state; only generated prompts, validators, recommendation filtering, and API degradation behavior change.
