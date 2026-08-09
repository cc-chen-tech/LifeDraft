## ADDED Requirements

### Requirement: Completed Opening Continuity Is Persisted Proactively
The opening page SHALL begin idempotent persistence of the final opening story as soon as a complete opening is available, including restored openings, without waiting for the user to press the start button.

#### Scenario: Streamed opening completes
- **WHEN** the opening SSE emits a non-empty complete story for a game
- **THEN** the page SHALL start persisting that story in character settings exactly once for that game and story

#### Scenario: Existing opening is restored
- **WHEN** the page loads a previously completed opening from the game store
- **THEN** the page SHALL ensure the restored story has an in-flight or completed continuity persistence operation

### Requirement: Starting Play Has Bounded Visible Waiting
The opening page SHALL make start activation visibly pending, prevent duplicate activation, and navigate no later than two seconds after activation while allowing continuity persistence to finish in the background.

#### Scenario: Continuity was already persisted
- **WHEN** the user presses start after proactive persistence completed
- **THEN** the page SHALL navigate to play without an additional persistence request

#### Scenario: Continuity persistence is still pending
- **WHEN** the user presses start while persistence remains in progress
- **THEN** the start control SHALL immediately display an entering state
- **AND** the page SHALL navigate when persistence finishes or after two seconds, whichever happens first

#### Scenario: Continuity persistence fails
- **WHEN** the initial persistence attempt fails
- **THEN** the page SHALL retry once
- **AND** a second failure SHALL NOT prevent navigation to play
