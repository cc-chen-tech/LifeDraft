## Why

Story101 currently sends image generation requests using the DashScope multimodal-generation payload shape. The requested provider is MiniMax image generation, whose text-to-image and image-to-image APIs both use `POST /v1/image_generation` with `image-01` / `image-01-live` models and a different response contract.

## What Changes

- Switch the backend image generation adapter to MiniMax `image-01` by default for text-to-image.
- Switch image-to-image regeneration to MiniMax `image-01` with `subject_reference`.
- Preserve existing `ImageClient` and frontend API contracts so character images, opening illustrations, scene images, and collection images keep using the same app endpoints.
- Map existing app image sizes to MiniMax aspect ratios or width/height fields.
- Parse MiniMax `data.image_urls` / `data.image_base64` responses and MiniMax `base_resp` errors.
- Update image provider defaults in settings and `.env.example`.

## Impact

- Backend image provider: `src/ai/image_generator.py`, `src/ai/image_config.py`, `config/settings.py`.
- Environment template: `.env.example`.
- Contract tests for MiniMax T2I/I2I request and response handling.
