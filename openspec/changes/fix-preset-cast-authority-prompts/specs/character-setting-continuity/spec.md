## ADDED Requirements

### Requirement: Preset key people are authoritative relationship facts
Story generation SHALL treat preset key people in character settings as canonical relationship facts, including their names, roles, and relationship labels.

#### Scenario: Product manager growth story has preset mentor friend and peer
- **GIVEN** character settings define 陆昊然 as 导师, 陈晓雨 as 闺蜜, and 林一凡 as 同期
- **WHEN** story-only or round-event prompts are built
- **THEN** the prompt MUST include each canonical name with its role or relationship label
- **AND** it MUST instruct the model not to rename these people or transfer their roles to invented substitutes
- **AND** it MUST require the generated round to use at least one preset key person instead of omitting the whole preset cast

#### Scenario: World model carries preset relationship authority
- **GIVEN** a saved player state includes preset key people in character settings
- **WHEN** the WorldModel is built from that player state
- **THEN** its constraint text MUST include the canonical preset cast and no-substitution rule
- **AND** it MUST include the same at-least-one-preset-key-person presence rule

#### Scenario: Scheduled commitment events inherit preset relationship authority
- **GIVEN** a scheduled event is due for a player with preset key people
- **WHEN** the scheduled event prompt is built
- **THEN** the prompt MUST include the canonical preset cast and no-substitution rule
- **AND** it MUST include the protagonist identity constraint and setting boundary constraints used by ordinary story prompts
- **AND** it MUST require at least one preset key person to appear when preset key people exist

#### Scenario: Scheduled commitment events retry cast drift before returning
- **GIVEN** a scheduled event generation response replaces the preset cast with invented named substitutes
- **WHEN** quick validation flags that story as not using preset key people
- **THEN** the scheduled event generator MUST retry with the validation failure included in the prompt
- **AND** it MUST return the corrected event instead of the drifted response

#### Scenario: Choice result continuations inherit preset relationship authority
- **GIVEN** a player chooses an option after a story involving preset key people
- **WHEN** the post-choice continuation prompt is built
- **THEN** the prompt MUST include the canonical preset cast and no-substitution rule
- **AND** it MUST include the realistic-world boundary and era constraints used by ordinary story prompts

#### Scenario: Choice result continuations retry cast and setting drift before returning
- **GIVEN** a post-choice continuation generation response drifts into an unrelated external IP world or invented named substitutes
- **WHEN** quick validation flags that continuation
- **THEN** the story service MUST retry with the validation failure included in the prompt
- **AND** it MUST return the corrected continuation instead of the drifted response

#### Scenario: Generic bystanders remain allowed
- **GIVEN** a story scene needs non-recurring background people
- **WHEN** the preset cast authority block is present
- **THEN** the story MAY use generic labels such as 路人 or 陌生人
- **AND** it MUST NOT introduce a named substitute for an existing preset relationship role
