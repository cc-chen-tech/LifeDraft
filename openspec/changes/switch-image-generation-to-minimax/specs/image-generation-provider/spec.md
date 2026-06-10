## ADDED Requirements

### Requirement: Image generation uses MiniMax provider contracts
The system SHALL call MiniMax image generation for backend text-to-image and image-to-image requests while preserving existing Story101 image endpoints and service return shapes.

#### Scenario: Text-to-image requests use MiniMax schema
- **GIVEN** the backend generates an image from text
- **WHEN** it calls the image provider
- **THEN** it SHALL send `POST /v1/image_generation`
- **AND** the request body SHALL include `model`, `prompt`, `response_format`, `n`, and either `aspect_ratio` or `width` plus `height`
- **AND** it SHALL NOT send the old DashScope `input.messages` / `parameters` shape.

#### Scenario: Image-to-image requests use MiniMax subject references
- **GIVEN** the backend regenerates an image from a reference image
- **WHEN** it calls the image provider
- **THEN** it SHALL send `subject_reference` containing the reference image as `image_file`
- **AND** it SHALL preserve the requested prompt and image count.

#### Scenario: MiniMax response is adapted to existing services
- **GIVEN** MiniMax returns `data.image_urls`
- **WHEN** the backend receives the response
- **THEN** it SHALL download the returned URL and keep returning image bytes to existing services.

#### Scenario: MiniMax provider errors are explicit
- **GIVEN** MiniMax returns a non-zero `base_resp.status_code`
- **WHEN** the backend processes the response
- **THEN** it SHALL raise an image generation error
- **AND** content safety code `1026` SHALL raise `ContentInspectionError`.
