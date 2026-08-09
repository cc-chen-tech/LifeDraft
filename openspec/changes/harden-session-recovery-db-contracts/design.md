# Design

The contract uses the configured SQLAlchemy database and production
`StateRepository` and `SessionService` instances. It creates an owner, an
intruder, a game, and two ordered snapshots. The test then observes state loading
and restoration through their public interfaces. No DB, session, or game-loop
methods are replaced.

The restored session is removed in cleanup so the module-level session store cannot
leak across later tests.
