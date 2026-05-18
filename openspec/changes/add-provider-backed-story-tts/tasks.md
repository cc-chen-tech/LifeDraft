## 1. Tests First

- [x] 1.1 Add strict mypy/provider static gate coverage for the provider protocol, factory, and concrete providers.
- [x] 1.2 Add import validation tests for delayed provider imports and router/service wiring.
- [x] 1.3 Add backend/frontend contract tests for `playback_mode`, `provider`, `model`, `media_type`, and provider settings fields.
- [x] 1.4 Add real DB integration tests proving provider/model-scoped save-read and asset reuse.
- [x] 1.5 Add browser E2E coverage for backend audio mode and browser speech fallback using story text.
- [x] 1.6 Wire all new tests and this OpenSpec change into `test.sh` before production code changes.

## 2. Backend Implementation

- [x] 2.1 Add typed provider protocol, deterministic local WAV provider, browser fallback provider, and OpenAI-compatible provider module.
- [x] 2.2 Add provider factory/configuration and availability metadata.
- [x] 2.3 Extend schemas and repository lookup so assets are scoped by provider and model.
- [x] 2.4 Update story voice reading service and router to return truthful playback metadata and stable audio files.

## 3. Frontend Implementation

- [x] 3.1 Extend frontend API types with provider/playback metadata.
- [x] 3.2 Update story voice store to use backend audio only for `playback_mode === "audio"`.
- [x] 3.3 Update controls to support browser speech fallback, pause/resume/stop state, and E2E-observable speech text.

## 4. Verification and Release

- [x] 4.1 Run targeted OpenSpec, static, import, contract, DB, frontend, and E2E checks during development.
- [x] 4.2 Perform code review before commit.
- [x] 4.3 Run full `./test.sh all` before pull request publication.
- [ ] 4.4 Push branch, open PR, wait for GitHub checks, merge to `main`, and allow automatic deployment.
