## ADDED Requirements

### Requirement: Latest reading request wins after runtime settings load

The story voice store SHALL share a pending runtime-settings request and SHALL NOT
allow an older reading attempt to start playback after a newer attempt supersedes it.

#### Scenario: Two reading attempts wait for browser-only settings

- **WHEN** two different reading attempts begin while runtime settings are pending
- **AND** settings select browser-only playback
- **THEN** settings are requested once
- **AND** only the newest attempt begins browser speech

### Requirement: Long browser speech completes its chunk lifecycle

The story voice store SHALL process every generated browser-speech chunk before it
reports a completed reading.

#### Scenario: Browser utterances finish in sequence

- **WHEN** browser playback is selected for text longer than one speech chunk
- **THEN** each completed utterance starts the next chunk
- **AND** the store returns to idle only after the final chunk completes
