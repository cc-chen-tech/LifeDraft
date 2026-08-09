## ADDED Requirements

### Requirement: In-memory collection response assembly coverage
The maintained backend suite SHALL cover CollectionService's public collection assembly using deterministic image caches.

#### Scenario: Collection contains every supported entity source
- **WHEN** player state contains a player, NPC, key person, family member, item, landmark, and cached images
- **THEN** the response preserves counts, normalized fields, image URLs, and image-generated flags for each collection category

#### Scenario: Duplicate character sources are not repeated
- **WHEN** canonical and supplemental character sources share a name
- **THEN** the response includes that character once using the first supported source

#### Scenario: Empty sources retain valid response shape
- **WHEN** a player state has only a player identity and no collected entities
- **THEN** the response contains zero non-player entities and zero counts for items and landmarks

### Requirement: Maintained workflow parity
The backend coverage and backend-test workflows SHALL enumerate the collection assembly module identically.

#### Scenario: CI derives maintained backend lists
- **WHEN** both workflow command lists are parsed
- **THEN** the collection assembly module occurs once in the same order
