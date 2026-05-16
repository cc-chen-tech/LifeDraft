## ADDED Requirements

### Requirement: Bottom Fixed Launchers Do Not Block Gameplay Choices

Collapsed bottom fixed controls SHALL only receive pointer events on their visible interactive element and SHALL NOT expose an invisible container hitbox that can intercept story choice clicks.

#### Scenario: Collapsed assistant hitbox is constrained

- **WHEN** the collapsed bottom assistant launcher is rendered in the browser
- **THEN** its fixed container has pointer events disabled
- **AND** its visible launcher button remains pointer-interactive and accessible as "打开剧情助手"

### Requirement: Story Choices Have Stable Accessible Names

Gameplay choice buttons SHALL expose an accessible name containing the choice ordinal and full choice text so browser automation and assistive technology can target the intended option.

#### Scenario: Choice button names include ordinal and text

- **WHEN** story choices are rendered
- **THEN** the first option is discoverable by role `button` and name `选择 1：<choice text>`
- **AND** the second option is discoverable by role `button` and name `选择 2：<choice text>`

### Requirement: Character Creation Step Dots Are Accessible

The character creation step indicator SHALL expose each step dot as a named button and SHALL identify the current step.

#### Scenario: All creation steps are named

- **WHEN** the character creation page is rendered
- **THEN** each step indicator button is discoverable by a name in the format `第 N 步：<step label>`
- **AND** the active step exposes current-step state.

### Requirement: Portrait Step Communicates Waiting And Continuation

The portrait step action button SHALL tell users when portrait generation is still pending and SHALL use "下一步" once a portrait is available.

#### Scenario: Portrait generation is pending

- **WHEN** the user reaches the portrait step and no portrait is available
- **THEN** the primary action is disabled
- **AND** the primary action text communicates that the app is waiting for image generation

#### Scenario: Portrait generation is ready

- **WHEN** the user reaches the portrait step and at least one portrait is available
- **THEN** the primary action uses the same "下一步" continuation language as previous creation steps

### Requirement: Registration Sheet Autofocus Is Preserved

Opening the registration sheet SHALL focus the display-name input without requiring an extra click.

#### Scenario: Registration input receives focus

- **WHEN** the user opens registration from the welcome page
- **THEN** the display-name input is focused
