## Context

The current image layer is already centralized behind `ImageClient`, with `ImageGenerator` handling text-to-image and image-to-image calls. Existing callers should not need route or frontend changes.

MiniMax image generation uses:

- Server: `https://api.minimaxi.com`
- Endpoint: `POST /v1/image_generation`
- Auth: `Authorization: Bearer <API key>`
- T2I fields: `model`, `prompt`, `aspect_ratio` or `width`/`height`, `response_format`, `n`, `prompt_optimizer`, `aigc_watermark`
- I2I extra field: `subject_reference: [{ type: "character", image_file: <url-or-data-url> }]`
- Response fields: `data.image_urls` or `data.image_base64`, plus `base_resp.status_code`

## Approach

Keep the existing public Python API and replace only provider-specific request/response translation inside `ImageGenerator`.

1. Add MiniMax payload helpers:
   - normalize `/v1/image_generation` URL from either a server root or `/v1` base URL;
   - map app sizes such as `1328*1328`, `1664*928`, and `928*1664` to MiniMax aspect ratios;
   - fall back to `width`/`height` for supported explicit dimensions.
2. Convert existing `negative_prompt` extra params into prompt guidance instead of sending unsupported MiniMax fields.
3. Parse URL and base64 responses into the existing `(bytes, prompt)` and `(bytes, prompt, url)` return shapes.
4. Treat non-zero `base_resp.status_code` as provider errors, with MiniMax content safety code `1026` mapped to `ContentInspectionError`.
5. Keep retry/model-fallback loops but make default model lists MiniMax-compatible.

## Non-Goals

- No frontend route changes.
- No generated image storage schema changes.
- No live MiniMax API call in tests; tests run against a local HTTP server that verifies real HTTP payloads.
