## Context

The current music system is better than raw keyword search because it builds a `MusicBrief`, enriches some known contexts, filters negative cues, and creates a bounded MiniMax prompt instead of sending the full story. However, it still has no explicit quality model for "does this track fit this scene?" NetEase ranking mostly uses direct metadata matches, MiniMax prompt construction is compact but flat, and known UX-report mismatches are handled as one-off heuristics rather than a repeatable quality gate.

The answer to "is the current generated music highly scene-matched?" should therefore be conservative: it is directionally scene-aware, but not yet measurable enough to call high quality. The main optimization opportunity is to make scene fit explicit, testable, and versioned across brief extraction, candidate scoring, prompt construction, and fallback decisions.

## Goals / Non-Goals

**Goals:**

- Add an explainable scene-fit score for NetEase candidates, local AI-library candidates when available, and newly generated MiniMax tracks.
- Improve `MusicBrief` extraction so it captures scene action, emotional arc, setting texture, intensity range, instrumentation priorities, and avoid-list intent.
- Build MiniMax prompts as structured English music directions instead of only a short summary plus a few fields.
- Add deterministic scene templates for recurring Story101 contexts and keep LLM analysis as an enhancer, not the only source of truth.
- Add offline regression fixtures for known mismatch classes so quality can improve without paid provider calls in CI.
- Preserve API compatibility and queue stability while adding optional diagnostics.

**Non-Goals:**

- Guaranteeing perfect semantic music matching.
- Calling NetEase or MiniMax from normal CI tests.
- Building a full audio-content classifier that analyzes waveform/music theory features.
- Changing the rule that MiniMax receives a bounded English prompt, not the full raw story.
- Replacing the local-library proposal; this change can score library candidates when that capability exists, but it must also work without it.

## Decisions

### 1. Add a scene-fit profile and score

Introduce a `MusicSceneFitProfile` or equivalent structure derived from the story and character settings. It should normalize dimensions such as primary emotion, secondary emotion, scene action, scene type, setting/environment, era, pacing, energy, tension, instrumentation priorities, and negative cues. A `MusicSceneFitScorer` should return a score and reason codes for each candidate.

Alternative considered: keep adding string filters in `MusicResultRanker`. That helps specific failures but does not produce an explainable or tunable quality signal.

### 2. Version the prompt builder

Create a dedicated prompt-builder path for MiniMax music with a version id. The prompt should be structured and bounded:

- role and use case: instrumental narrative gameplay background;
- story summary: compact and sanitized;
- musical direction: primary mood, scene action, setting texture, energy/tempo, instrumentation hierarchy;
- arrangement constraints: loopable, background presence, duration target;
- negative instructions: vocals, lyrics, dominant pop singing, and scene-specific avoid cues.

Alternative considered: keep using `MusicBrief.generation_prompt` directly. That is compatible but makes prompt changes hard to test or compare.

### 3. Use deterministic scene templates before generic fallback

For common Story101 scenes, add deterministic enrichment templates that guide queries and prompts: modern workplace/AI collaboration, suspense/chase, quiet recovery, family conflict, romance, action/conflict, reflective ending, and daily-life transition. LLM analysis can still supply fields, but templates prevent generic or pop-song drift when context is obvious.

Alternative considered: rely entirely on the LLM to infer music intent. Prior reports show that misses often need stable product rules, especially for negative cues and modern workplace scenes.

### 4. Add offline quality fixtures

Build fixtures from representative story excerpts and expected music profiles. Tests should verify brief fields, score thresholds, rejected mismatches, and generated prompt content without network calls.

Alternative considered: manually judge production output only. That is necessary for final UX QA, but it is too slow and subjective as the primary regression gate.

### 5. Add diagnostics without changing playback contracts

The backend can log or optionally return debug fields such as fit score, prompt version, selected strategy, and rejection reasons. The frontend store should preserve unknown generated-track metadata, but UI changes are optional and non-blocking.

Alternative considered: add visible UI explanations immediately. That may be useful later, but the current problem is matching quality rather than user-facing education.

## Risks / Trade-offs

- Fit scoring can overfit metadata and miss subjective musical feel -> Keep scores explainable, use fixtures for known failures, and leave room for production QA tuning.
- More prompt fields can exceed MiniMax prompt limits -> Keep a strict character budget and prioritize scene/action/instrument/negative cues before lower-value details.
- Conservative thresholds can reduce AI reuse or recommendations -> Fall back to safe instrumental/background tracks instead of surfacing bad matches.
- Diagnostics can leak story details -> Log sanitized reason codes and avoid returning raw story summaries or source prompts to the frontend.
- Template expansion can become brittle -> Keep templates small, tested, and focused on recurring Story101 scenes.

## Migration Plan

1. Add offline fixtures and failing tests for brief extraction, fit scoring, prompt construction, and low-confidence fallback.
2. Add scene-fit profile and scorer behind `MusicContextBuilder` / `MusicResultRanker` without changing response fields.
3. Add versioned MiniMax prompt builder with strict prompt budgets.
4. Integrate scoring into NetEase result ranking and generated/local AI candidate selection.
5. Add optional diagnostics to logs or response metadata while keeping existing frontend consumers compatible.
6. Run targeted backend music tests, frontend music store tests, and OpenSpec strict validation before broader gates.

## Open Questions

- The initial fit threshold should be conservative and adjusted after fixture and browser QA evidence.
- If local AI music library work lands first, this scorer should become the shared library-candidate scorer; if not, it should start with NetEase and MiniMax prompt decisions only.
- Production UX review should still listen to generated output because prompt quality tests can validate intent, not actual audio aesthetics.
