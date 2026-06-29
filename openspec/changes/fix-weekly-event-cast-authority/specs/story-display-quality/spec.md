## ADDED Requirements

### Requirement: Weekly event prompts preserve preset cast authority

Weekly event generation prompts SHALL include the same preset key-people
authority block used by round, story-only, choice-result, and scheduled-event
generation.

#### Scenario: Modern product-manager weekly event uses preset relationship network
- **Given** the character settings define preset key people such as mentor,
  close friend, and peer relationships
- **When** the weekly event prompt is built from those settings
- **Then** the prompt SHALL include all preset key people by canonical name
- **And** the prompt SHALL state they must not be renamed or replaced
- **And** the prompt SHALL require at least one preset key person each round
- **And** multi-person relationship scenes SHALL use the preset relationship
  network rather than letting new named characters drive the story.
