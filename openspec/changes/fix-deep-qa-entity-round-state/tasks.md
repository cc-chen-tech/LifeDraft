## 1. Character recognition integrity

- [x] 1.1 Add a failing regression test for rejecting fabricated names and lexical fragments while retaining an explicit honorific name.
- [x] 1.2 Filter parsed character candidates by exact story evidence before candidates can be supplemented or returned.
- [x] 1.3 Run focused recognition tests and commit the completed character-integrity function.

## 2. Player-facing round display

- [x] 2.1 Add a failing scene-image label test for a zero-based first round.
- [x] 2.2 Derive a scene-image display label from the zero-based state index without changing persisted state semantics.
- [x] 2.3 Run focused frontend tests and commit the completed display function.

## 3. Verification

- [x] 3.1 Run the relevant backend and frontend regression suites, type checks, and strict OpenSpec validation.
- [x] 3.2 Run the applicable browser regression path and capture a concise verification record.
- [ ] 3.3 Commit OpenSpec task completion, open a PR from the latest-main branch, and observe its checks.
