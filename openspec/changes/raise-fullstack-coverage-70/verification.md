## Baseline

The current `main` baseline was measured with the maintained backend workflow
selection and `--cov=src` on 2026-07-15:

- Backend: 243 passed, 3 existing SQLAlchemy warnings, 7,424 / 23,293 covered
  statements (31.87%).
- Frontend: 105 suites and 1,816 tests passed. Lines 78.75%, statements
  77.87%, functions 71.32%, branches 72.16%.

## First Backend Batch

The new world-model, collection-shape, and round-illustration suites were run
twice in the maintained environment: 9 passed on each run. They were then
promoted to both workflow selections in the same order.

The expanded maintained selection was also measured twice:

- 252 passed, 3 existing SQLAlchemy warnings, 7,854 / 23,293 covered
  statements (33.72%).
- 252 passed, 3 existing SQLAlchemy warnings, 7,854 / 23,293 covered
  statements (33.72%).

The selected module deltas are:

| Module | Baseline | Current |
| --- | ---: | ---: |
| `src/game/world_model_updater.py` | 6.33% | 31.63% |
| `src/services/collection_service.py` | 14.48% | 47.18% |
| `src/game/round/illustration_service.py` | 8.55% | 50.74% |

## 70 Percent Boundary

At the unchanged full-backend denominator, 70% requires 16,306 covered
statements. This branch is currently 8,452 statements short. No backend
coverage threshold is introduced or raised in this batch; the next batch must
continue to target high-risk modules while retaining `--cov=src`.

The frontend global threshold is now set to 70% for every metric and the full
Jest coverage command passes at the recorded baseline values.

## Second Backend Batch

The SSE helper state and image prompt builder suites were each run twice in the
maintained environment: 6 passed on each run. They were promoted to both
workflow selections in the same order.

The expanded maintained selection was measured twice:

- 258 passed, 3 existing SQLAlchemy warnings, 7,945 / 23,293 covered
  statements (34.11%).
- 258 passed, 3 existing SQLAlchemy warnings, 7,945 / 23,293 covered
  statements (34.11%).

| Module | Before second batch | Current |
| --- | ---: | ---: |
| `src/api/routers/gameplay/sse_helpers.py` | 5.88% | 7.06% |
| `src/ai/image_prompt_builder.py` | 9.33% | 40.67% |

The remaining distance to 70% is now 8,361 statements. The next worthwhile
batches are `sse_helpers` durable-operation paths, `scene_service` local data
paths, and gameplay state transitions, each as a separate test-only change.
