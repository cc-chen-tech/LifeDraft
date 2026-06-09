## MODIFIED Requirements

### Requirement: Long Narrative Text Is Displayed In Readable Paragraphs

The story reader SHALL preserve authored markdown when present, but SHALL add conservative visual paragraph breaks for long single-line Chinese narrative text so generated stories are readable even when the model omits blank lines.

#### Scenario: Long Chinese story arrives as one line

- **Given** the story text contains multiple Chinese sentences with no markdown paragraph breaks
- **When** the play page renders the narrative story
- **Then** the reader SHALL display it as multiple paragraphs
- **And** it SHALL NOT mutate the saved story text or text passed to narration/music features.

### Requirement: Realistic Modern Settings Preserve World Boundary

Story generation prompts SHALL preserve realistic modern character settings and SHALL NOT allow unrequested cyberpunk, future-world, or external IP-world drift.

#### Scenario: Ordinary modern character settings

- **Given** character settings describe a contemporary realistic character without sci-fi or cyberpunk intent
- **When** an opening, story-only, or round-event prompt is generated
- **Then** the prompt SHALL explicitly forbid unrequested cyberpunk/future-world drift
- **And** the prompt SHALL explicitly forbid introducing known external IP worlds or proper nouns such as "夜之城", "荒坂集团", and "Cyberpunk 2077".

#### Scenario: Explicit cyberpunk settings

- **Given** character settings explicitly request cyberpunk or future sci-fi
- **When** a story prompt is generated
- **Then** the prompt SHALL NOT add the realistic-modern cyberpunk prohibition block.
