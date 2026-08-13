## 1. Daily timeline and migration

- [x] 1.1 Add failing calendar, 365-day age, 672-day ending, and timeline serialization tests
- [x] 1.2 Implement timeline-v2 state helpers and daily generation budgets
- [x] 1.3 Add failing legacy history/scheduled-event migration and idempotency tests
- [x] 1.4 Implement legacy JSON migration, exact-date scheduling, feature flag, and dry-run/apply report command

## 2. Daily generation and choice contracts

- [x] 2.1 Add failing tests for versioned events, stale selection, duplicate delivery, no continuation call, and custom-choice rejection
- [x] 2.2 Implement atomic daily settlement, canonical day history, seven-day decay, and recoverable post-processing status
- [x] 2.3 Add failing next-day prompt, rewrite candidate, regenerate candidate, and failed-replacement tests
- [x] 2.4 Implement daily prompt/context, coherent rewrite/regenerate replacement, event revisioning, and compatibility response fields

## 3. API, persistence, and media

- [x] 3.1 Add timeline/event/choice request-response schema tests and expose normalized state fields
- [x] 3.2 Add scene-image story-date/day-index columns, daily lookup, invalidation, and legacy compatibility tests
- [x] 3.3 Regenerate OpenAPI artifacts and update API contract consumers

## 4. Frontend daily flow

- [x] 4.1 Add failing character start-date and first-day opening tests
- [x] 4.2 Implement start-date creation input, day-one generation, and legacy opening redirect
- [x] 4.3 Add failing automatic next-day, date-heading, no-custom-choice, no-result/weekly-page, and stale-choice tests
- [x] 4.4 Implement the daily play state machine, structured settlement toast, versioned choice requests, and daily rewrite/regenerate handling
- [x] 4.5 Convert history and scene-image stores/components to day/date keys with legacy read fallback

## 5. Verification and rollout

- [x] 5.1 Run focused backend and frontend daily-timeline regressions plus strict OpenSpec validation
- [x] 5.2 Run Python type/import gates, frontend TypeScript/Jest, and production build
- [x] 5.3 Run isolated Playwright flows for new daily game, migrated save, regeneration/rewrite, and disconnect recovery
- [x] 5.4 Review diff against every approved requirement and document rollout/monitoring evidence
