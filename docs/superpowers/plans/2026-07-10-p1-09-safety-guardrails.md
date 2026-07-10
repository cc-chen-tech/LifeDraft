# P1-9 Professional Risk Guardrails Implementation Plan

**Goal:** Prevent generated legal, medical, regulatory, or policy content from presenting evasion tactics or uncertain professional conclusions as zero-risk, guaranteed legal, or absolutely safe.

**Architecture:** Add one deterministic sentence-level professional-risk boundary. It detects a professional-domain marker only when paired with a guarantee/endorsement marker, returns validator issues for model retry paths, and rewrites any unsafe text that still reaches an output boundary. The rewrite removes the guarantee, preserves narrative facts, adds a compact domain-specific uncertainty/professional-review sentence, and is idempotent. Prompt suffixes reduce first-pass violations; deterministic output handling remains the final guarantee.

## Task 1: RED policy contracts

- [ ] Test the exact “亲属名义规避竞业、几乎零风险、合规路径” failure.
- [ ] Test legal, medical, regulatory, English, idempotency, and normal-fiction false-positive cases.
- [ ] Test QuickValidator rejection, story normalization, assistant response, summary output, and prompt constraints.
- [ ] Run focused tests and record the expected missing-policy failures.

## Task 2: Central detector and safe rewrite

- [ ] Implement professional-domain and guarantee marker detection per sentence.
- [ ] Rewrite zero-risk/guaranteed wording without deleting the underlying fictional event.
- [ ] Add compact legal/regulatory or medical uncertainty and qualified-professional-review text.
- [ ] Preserve normal narrative and make repeated application idempotent.
- [ ] Add English behavior and safe fallback text.

## Task 3: Generation and assistant integration

- [ ] Add unsafe professional claims to QuickValidator hard issues so retry-capable paths regenerate.
- [ ] Apply the deterministic boundary in generated-story normalization.
- [ ] Apply it to rewrite/regenerate return paths that do not normalize centrally.
- [ ] Strengthen story/continuation/rewrite/summary system prompts.
- [ ] Apply the boundary and grounding instructions to story-assistant replies.

## Task 4: Summary integration and verification

- [ ] Apply the boundary to compressed, weekly, monthly, yearly, ending, and life-summary outputs.
- [ ] Run focused story, assistant, summary, prompt, validator, and import tests.
- [ ] Run false-positive scans and `git diff --check`.
- [ ] Run `./test.sh all` and browser-smoke an unsafe assistant/story output plus a normal fictional scene.
- [ ] Audit the P1-9-only diff and prepare draft PR `fix(safety): qualify high-risk professional claims`.
