## MODIFIED Requirements

### Requirement: Character Recognition Is Metadata-Gated

Collection recognition SHALL propose characters that satisfy relationship or importance metadata rules, or that are independently supported by conservative, explicit named-person syntax in the story text. AI-only names and ambiguous text fragments SHALL remain excluded.

#### Scenario: Text contains named phrases without character metadata
- **Given** history text contains named phrases that are not relationship/important character entities and do not satisfy explicit person syntax
- **When** smart recognition runs
- **Then** those phrases SHALL NOT be proposed as characters
- **And** the proposal reason SHALL NOT claim they are explicit named characters solely from text frequency.

#### Scenario: Story introduces clearly named people before metadata catches up
- **Given** story prose explicitly shows `陈远` and `周丽` acting or speaking as people
- **When** smart recognition runs before relationship metadata contains those names
- **Then** both people SHALL be eligible recognition candidates
- **And** existing collected people SHALL remain excluded.

### Requirement: Smart Recognition Reaches Terminal State

Smart recognition and entity add SHALL each leave their blocking loading state with a terminal success, empty, or error state. A successful durable add SHALL NOT remain blocked on collection-detail refresh.

#### Scenario: Recognition has no eligible candidates
- **Given** no eligible relationship/important or explicit prose entities are available
- **When** smart recognition finishes
- **Then** the UI SHALL show an empty-result message
- **And** `添加到收集` SHALL remain disabled with an accurate label
- **And** the dialog SHALL NOT stay on `正在分析故事历史...` or `添加中...`.

#### Scenario: Add succeeds while detail refresh is slow
- **Given** selected recognized entities are durably saved
- **When** the follow-up collection-detail refresh is still running
- **Then** the add dialog SHALL leave `添加中...` and close
- **And** the collection panel SHALL use its non-blocking refresh state.

## ADDED Requirements

### Requirement: Recognition Context Uses Complete Sentences

Recognition fallback descriptions SHALL include the entity name in a normalized context excerpt and SHALL NOT begin with an unexplained fragment cut from the middle of a sentence.

#### Scenario: Entity occurs after a long preceding sentence
- **WHEN** a named person first appears after a Chinese sentence delimiter
- **THEN** the context SHALL start at that sentence boundary
- **AND** it SHALL include the complete sentence containing the person.
