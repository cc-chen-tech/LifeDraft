## 1. Tests And Contracts First

- [x] 1.1 Add contract tests for `MusicBrief` structure and fallback defaults.
- [x] 1.2 Add provider-selection tests for non-member, member with AI disabled, and member with AI enabled.
- [x] 1.3 Add queue-policy tests proving current song is never interrupted and near-term queue remains stable.
- [x] 1.4 Add fallback tests proving AI generation failure leaves or refreshes Netease recommendations.
- [x] 1.5 Add persistence/reuse tests for generated music asset metadata and brief-hash lookup.

## 2. Music Brief And Netease Matching

- [x] 2.1 Introduce a structured music brief data model.
- [ ] 2.2 Update story analysis to produce music brief fields plus Netease search queries.
- [ ] 2.3 Improve Netease query construction from mood, era, scene type, energy, instruments, and negative cues.
- [ ] 2.4 Add deterministic or AI-assisted reranking of Netease search results before playlist merge.
- [ ] 2.5 Keep API response compatibility for existing frontend music playback.

## 3. Queue Policy

- [ ] 3.1 Extract playlist merge behavior into an explicit queue policy.
- [x] 3.2 Preserve the current song on every recommendation update.
- [x] 3.3 Preserve the first upcoming song when inserting background-generated tracks where practical.
- [x] 3.4 Add source metadata to playlist items without breaking existing Netease song handling.

## 4. Premium AI Generation Path

- [x] 4.1 Add feature-flag and membership checks for background AI music generation.
- [ ] 4.2 Add a generation job interface without requiring a final provider implementation.
- [x] 4.3 Add generated music asset metadata persistence and lookup by brief/provider hash.
- [x] 4.4 Insert completed generated tracks into future queue slots only, never as an immediate current-song replacement.
- [x] 4.5 Record generation failures and fall back to Netease recommendations.

## 5. Frontend Integration

- [x] 5.1 Accept and preserve music item `source` metadata in frontend types/store.
- [ ] 5.2 Keep current playback stable when backend queue updates arrive.
- [ ] 5.3 Optionally surface generated-track source labels without making AI tracks feel mandatory.

## 6. Verification

- [x] 6.1 Run targeted backend music tests.
- [ ] 6.2 Run targeted frontend music store/player tests.
- [ ] 6.3 Run the project test gate used for music-related changes.
