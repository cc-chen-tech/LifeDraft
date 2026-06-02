# collection-recognition-gating Specification

## Purpose
TBD - created by archiving change fix-live-gameplay-recovery-collection. Update Purpose after archive.
## Requirements
### Requirement: Character Recognition Is Metadata-Gated

Collection recognition SHALL propose characters only when they satisfy the system's relationship or importance metadata rules.

#### Scenario: Text contains named phrases without character metadata
- **Given** history text contains named phrases that are not relationship/important character entities
- **When** smart recognition runs
- **Then** those phrases SHALL NOT be proposed as characters
- **And** the proposal reason SHALL NOT claim they are explicit named characters solely from text frequency.

### Requirement: Smart Recognition Reaches Terminal State

Smart recognition SHALL leave loading with a terminal success, empty, or error state.

#### Scenario: Recognition has no eligible candidates
- **Given** no eligible relationship/important entities are available
- **When** smart recognition finishes
- **Then** the UI SHALL show an empty-result message
- **And** `添加到收集` SHALL remain disabled with an accurate label
- **And** the dialog SHALL NOT stay on `正在分析故事历史...` or `添加中...`.

### Requirement: Existing Collection Entities Are Not Re-Proposed

Smart recognition SHALL not propose entities already in the player's collection.

#### Scenario: Relationship character already collected
- **Given** `陆子衿` is already collected as a relationship character
- **When** recognition analyzes later history
- **Then** `陆子衿` SHALL NOT appear as a new candidate.

