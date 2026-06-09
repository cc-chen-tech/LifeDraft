## 1. Frontend Regression Tests

- [x] 1.1 Update `StatusBar` unit tests to require age/week/progress while rejecting runtime resource metric labels and values.
- [x] 1.2 Update `ChoiceImpactDisplay` unit tests to require no visible card for resource-only effects.
- [x] 1.3 Update ending page unit tests to reject the final numeric resource stats grid.
- [x] 1.4 Update `LifeReviewCard` unit tests to reject resource curves and raw resource keys.
- [x] 1.5 Update browser E2E specs that previously required 4D resource visibility.
- [x] 1.6 Run the new/updated tests before implementation and confirm expected failures.

## 2. Frontend Implementation

- [x] 2.1 Remove resource metric rendering from `StatusBar` while keeping age/week/progress visible.
- [x] 2.2 Make `ChoiceImpactDisplay` filter `energy`, `mood`, `knowledge`, and `wealth` effects.
- [x] 2.3 Remove final numeric resource stats rendering from the ending page.
- [x] 2.4 Remove resource curve rendering from `LifeReviewCard`.

## 3. Verification

- [x] 3.1 Run focused frontend unit tests.
- [x] 3.2 Run focused browser E2E coverage for the hidden metric contract.
- [x] 3.3 Run `openspec validate hide-player-resource-metrics-frontend --strict`.
- [x] 3.4 Run the applicable `test.sh` gate without skipping tests.
