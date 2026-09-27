# Public story plaza implementation

## Contract

- An anonymous visitor can browse a public story list and read its chapters without registering.
- The owner of a saved story has one publication switch. Turning it on publishes all persisted, completed chapters and automatically includes later completed chapters. Turning it off makes the story disappear from the list and makes its link return 404 immediately.
- A public response contains only a story title, author display name, chapter dates and readable story text. It never exposes a game state, account identifier, options, effects, or an in-progress current event.
- Existing friend visibility (`Game.is_public`) is independent of plaza publication.

## Data and API

1. Add a one-to-one `StoryPublication` table (`game_id`, opaque `public_id`, `enabled`, timestamps). This avoids changing the meaning of the existing friend-sharing field and lets an old link work again if the owner republishes.
2. Add owner-only `GET /api/plaza/mine` and `PUT /api/plaza/mine/{game_id}`. Require normal authentication and enforce ownership in the query. Publication requires at least one completed persisted chapter.
3. Add anonymous `GET /api/plaza` with bounded pagination and search, and `GET /api/plaza/{public_id}`. Read the latest saved `GameState` at request time, reconstruct only the public chapter DTO, and send `Cache-Control: no-store`. Include the older `round_history` format when `day_history` is absent.
4. Add integration tests for anonymous access, ownership, off-link revocation, automatic inclusion of later chapters, incomplete chapter exclusion, and response-field whitelist.

## UI

1. Add an always-visible plaza entry on the home page and a sharing-management entry from saved games.
2. Build `/plaza` for anonymous browsing with search, empty/error/loading states and a responsive editorial layout consistent with the existing ink palette.
3. Build `/plaza/[publicId]` for chapter reading and navigation; support a direct link with no account session.
4. Build `/plaza/manage` with one switch per owned story, clear automatic-update copy, and a copy-link action only while public. Keep the switch disabled when there is no completed chapter.
5. Add targeted UI tests for browse/read and publication toggle; run type, lint, build, and backend tests.

## Implementation order

Backend contract tests (red), table/API/projection (green), frontend behavior tests (red), UI/client (green), then verification and browser review.
