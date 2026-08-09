## Context

WorldModelUpdater reconciles structured analysis output into PlayerState without provider access.

## Goals / Non-Goals

**Goals:** gate new location/career defaults and fuzzy commitment completion.

**Non-Goals:** alter updater behavior or use AI/database services.

## Decisions

- Use a real PlayerState and assert stored dictionaries.
