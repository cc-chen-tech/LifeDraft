## 1. Origin domain and generation

- [x] 1.1 Add failing contracts for canonical origin validation, compatibility projection, explicit feedback anchors, and legacy synthesis
- [x] 1.2 Implement the story-origin domain model and deterministic compatibility helpers
- [x] 1.3 Add failing API and generator contracts for atomic story-origin candidates
- [x] 1.4 Implement the story-origin prompt, generator, schema, and character API endpoint

## 2. Draft persistence and compatibility

- [x] 2.1 Add failing database/API contracts for revision CAS, day-zero rebase, downstream invalidation, and played-game locking
- [x] 2.2 Implement atomic owned-draft story-origin replacement and durable session synchronization
- [x] 2.3 Add failing preset contracts for deterministic legacy conversion and conflict review
- [x] 2.4 Implement preset normalization and canonical save projection without rewriting played games

## 3. Frontend creation flow

- [x] 3.1 Add failing store/component contracts for the four-step flow and story-origin display without birth year
- [x] 3.2 Implement story-origin types, API client, store steps, display, and removal of the direct date input
- [x] 3.3 Add failing hook/page contracts for whole-card regeneration, stale-result fencing, and dependent-setting invalidation
- [x] 3.4 Implement origin regeneration/rebase flow, return-to-world behavior, and completion review

## 4. Downstream consistency and media fencing

- [x] 4.1 Add failing contracts proving downstream prompts and character images prefer and fence the canonical origin revision
- [x] 4.2 Update world/family/relationship/story/image context and discard stale origin-revision results
- [x] 4.3 Add browser coverage for first origin, historical-to-modern replacement, old-preset review, and first-day date continuity

## 5. Generated contracts and verification

- [x] 5.1 Regenerate OpenAPI/input-limit frontend types and validate the OpenSpec change
- [x] 5.2 Run focused backend/frontend/browser suites and fix every regression
- [ ] 5.3 Run `./test.sh all`, review the final diff against the plan, and publish a Ready PR only with zero failures and green CI
