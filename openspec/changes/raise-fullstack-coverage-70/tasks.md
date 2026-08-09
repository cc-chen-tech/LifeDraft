## 1. Frontend 70 Percent Gate

- [x] 1.1 Set all four Jest global coverage thresholds to 70 percent without
  changing the coverage source include/exclude list.
- [x] 1.2 Run the complete frontend Jest coverage suite and record all four
  global results.

## 2. High-Risk Backend Contract Batches

- [x] 2.1 Add a new deterministic test file for `WorldModelUpdater` state and
  fallback contracts using concrete game state only.
- [x] 2.2 Add a new deterministic test file for `CollectionService` identity,
  nested field, and image-cache response contracts without provider calls.
- [x] 2.3 Add a new deterministic test file for round illustration request and
  persistence contracts without external image generation.
- [x] 2.4 Run each new backend suite twice in the maintained environment and
  exclude any unstable suite from promotion.
- [x] 2.5 Add deterministic SSE payload, retry-cache, and round-identity
  contracts without starting a worker or calling a provider.
- [x] 2.6 Add deterministic image-prompt era, fallback, safety, and
  appearance-anchor contracts without calling the prompt provider.
- [x] 2.7 Run the new SSE and image-prompt suites twice in the maintained
  environment and exclude any unstable suite from promotion.

## 3. Maintained Backend Ratchet

- [x] 3.1 Add only twice-stable candidate suites to both backend workflows in
  identical order.
- [x] 3.2 Promote a later stable high-risk batch to both workflows in
  identical order.
- [x] 3.3 Re-measure the maintained backend selection twice with `--cov=src`
  after the later promoted batch and retain or raise a backend floor only when
  both results prove it.
- [x] 3.4 Record the remaining distance from full-backend 70 percent coverage
  and the next high-risk module batches without changing the full-suite policy.

## 4. Final Verification

- [x] 4.1 Validate the OpenSpec change, check workflow-selection parity, and
  inspect the scoped diff.
- [x] 4.2 Commit only new tests, coverage-gate configuration, and OpenSpec
  artifacts on the isolated branch.
