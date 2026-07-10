# P1-2 Image Provider Failure Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace opaque image-generation 500s and repeated provider calls with typed provider failures, bounded retry behavior, cached background failure state, and actionable portrait, collection, and scene-image UI.

**Architecture:** Classify failures once at the MiniMax HTTP boundary and preserve that classification through the image service and API layers. Permanent account/configuration/capacity failures stop immediately and map to a safe structured 503; invalid user requests map to 422; transient upstream failures remain bounded. Background scene generation stores a terminal safe failure for its stable `(game_id, week, round, stage)` key, and only an explicit user retry may clear that failure and start a new task.

**Tech Stack:** Python 3.11, FastAPI, requests/urllib3, SQLAlchemy, React 19, Zustand, TypeScript, Jest, pytest.

## Global Constraints

- P1-2 is the only product issue in this branch and PR.
- Never log or return API keys, authorization headers, or full prompts.
- A MiniMax `2056` capacity response must make exactly one provider request for the user action; model fallback cannot fix an account-wide quota failure.
- Missing provider configuration, invalid credentials, exhausted balance/quota, and upstream failures must not become generic HTTP 500 responses.
- Automatic scene fetch/polling must not restart a terminally failed generation task.
- The user must see a stable placeholder, a safe explanation, and an explicit retry action.
- Content-safety failures remain distinct from provider availability failures.
- Production smoke makes one direct provider request only and records the classified code without exposing secrets.

---

## Root-Cause Record

The 2026-07-10 production QA report reproduced character and scene image 500s from creation and collection. A fresh one-call smoke from this branch reproduced:

```text
provider_smoke_error_type=ImageGenerationError
provider_smoke_error=MiniMax image API returned 2056: 已达到 Token Plan 用量上限
```

MiniMax's official error-code documentation defines `2056` as Token Plan resource exhaustion. Its Token Plan documentation states that non-text image quota resets daily. The request contract itself is valid: the provider returns HTTP 200 with failure information in `base_resp.status_code`.

The application amplifies and obscures that failure:

1. `ImageGenerator._raise_for_minimax_error()` converts every non-content provider error into an untyped `ImageGenerationError`.
2. `ImageGenerator.generate_image()` catches that error through `except Exception`, retries each model three times, and attempts the fallback model even though `2056` is account-wide.
3. Higher-level character generation loops also catch `ImageGenerationError` and can continue issuing requests.
4. `src/services/image/__init__.py` and `src/services/image_service.py` define different `ImageServiceError` classes. Routers importing the latter do not catch errors raised by character/scene subservices using the former.
5. Image and collection routers map remaining service errors to HTTP 500 and may expose provider text.
6. `GET /images/scene/{game}/{round}` clears its in-flight key after failure. The next frontend poll starts the same failed background job again.
7. The generic frontend retry layer retries all 5xx responses three times, including non-idempotent image-generation mutations.
8. Portrait and scene stores stop their spinner but do not preserve a dedicated actionable provider-failure state.

Official references:

- https://platform.minimaxi.com/docs/api-reference/errorcode
- https://platform.minimaxi.com/docs/api-reference/image-generation-i2i
- https://platform.minimaxi.com/docs/token-plan/faq

## File Map

- Modify `src/ai/image_exceptions.py`: typed, safe provider failure with category, code, retryability, and trace ID.
- Modify `src/ai/image_generator.py`: classify MiniMax business/HTTP/network failures and stop permanent-error retry/fallback.
- Modify `src/services/image/__init__.py`: one canonical service exception hierarchy.
- Modify `src/services/image_service.py`: import/re-export canonical exceptions instead of redefining them.
- Modify `src/services/image/character_service.py` and `src/services/image/scene_service.py`: preserve typed provider failures.
- Create `src/api/routers/image_failures.py`: shared safe HTTP/SSE serialization.
- Modify `src/api/routers/images.py` and `src/api/routers/collection.py`: structured status mapping and terminal scene-failure cache.
- Modify `frontend/src/lib/api.ts`: no blind retry for image-generation mutations and retain structured failure metadata.
- Modify `frontend/src/stores/useImageStore.ts`: portrait failure state.
- Modify `frontend/src/stores/useSceneImageStore.ts`: terminal scene failure plus explicit retry.
- Modify `frontend/src/components/create/StepPortrait.tsx`, `frontend/src/app/create/page.tsx`, and `frontend/src/hooks/useCharacterCreation.ts`: actionable portrait placeholder.
- Modify `frontend/src/components/game/RoundSceneImage.tsx` and `frontend/src/app/play/page.tsx`: actionable scene placeholder and explicit retry request.
- Test in new `tests/test_image_provider_failure_contract.py` plus existing image router, scene SSE, API retry, store, and component suites.

---

### Task 1: Classify Provider Failures and Stop Permanent Retries

**Files:**
- Modify: `src/ai/image_exceptions.py`
- Modify: `src/ai/image_generator.py`
- Create: `tests/test_image_provider_failure_contract.py`

**Interfaces:**
- Produces `ImageProviderError(code, category, retryable, public_message, provider_trace_id)`.
- Produces a MiniMax policy mapping for `1001`, `1002`, `1004`, `1008`, `1024`, `1026`, `1027`, `1033`, `2013`, `2049`, and `2056`.
- Consumed by Task 2 service exceptions.

- [ ] **Step 1: Write provider-boundary RED tests**

Add real-code tests with a counting fake `requests.Session`:

```python
class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


class CountingSession:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload
        self.post_calls = 0

    def post(self, *args, **kwargs) -> FakeResponse:
        self.post_calls += 1
        return FakeResponse(self.payload)


def configured_generator(payload, *, max_retries=3, models=("image-01", "image-01-live")):
    generator = ImageGenerator(api_key="test-key", base_url="https://example.invalid/v1")
    session = CountingSession(payload)
    generator.session = session
    generator.max_retries = max_retries
    generator.text_to_image_models = list(models)
    return generator, session


def test_minimax_2056_is_typed_capacity_failure_and_is_not_retried():
    generator, session = configured_generator(
        {"base_resp": {"status_code": 2056, "status_msg": "limit"}}
    )

    with pytest.raises(ImageProviderError) as raised:
        generator.generate_image("safe diagnostic prompt")

    assert raised.value.code == "minimax_2056"
    assert raised.value.category == "capacity"
    assert raised.value.retryable is False
    assert raised.value.public_message == "图片生成额度暂时不可用，请稍后再试"
    assert session.post_calls == 1


def test_missing_image_provider_config_is_typed_and_safe():
    generator = ImageGenerator(api_key="", base_url="")

    with pytest.raises(ImageProviderError) as raised:
        generator._call_api(prompt="safe", model="image-01")

    assert raised.value.code == "image_provider_not_configured"
    assert raised.value.category == "configuration"
    assert "API key" not in raised.value.public_message


def test_minimax_transient_upstream_failure_remains_bounded():
    generator, session = configured_generator(
        {"base_resp": {"status_code": 1033, "status_msg": "upstream"}},
        max_retries=2,
        models=("image-01",),
    )

    with pytest.raises(ImageProviderError) as raised:
        generator.generate_image("safe diagnostic prompt")

    assert raised.value.category == "upstream"
    assert raised.value.retryable is True
    assert session.post_calls == 2


def test_valid_minimax_business_response_is_returned():
    payload = {
        "data": {"image_urls": ["https://example.invalid/image.png"]},
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }
    generator, session = configured_generator(payload)

    assert generator._call_api(prompt="safe", model="image-01") == payload
    assert session.post_calls == 1


def test_provider_timeout_is_typed_and_retryable():
    generator, _ = configured_generator({})
    generator.session.post = lambda *args, **kwargs: (_ for _ in ()).throw(requests.Timeout())

    with pytest.raises(ImageProviderError) as raised:
        generator._call_api(prompt="safe", model="image-01")

    assert raised.value.category == "timeout"
    assert raised.value.retryable is True


def test_success_status_without_image_output_is_invalid_response():
    generator, _ = configured_generator({"base_resp": {"status_code": 0}})

    with pytest.raises(ImageProviderError) as raised:
        generator.generate_image("safe")

    assert raised.value.category == "invalid_response"
    assert raised.value.retryable is False
```

- [ ] **Step 2: Run provider tests and verify RED**

Run:

```bash
python -m pytest tests/test_image_provider_failure_contract.py -q
```

Expected: collection or assertions fail because `ImageProviderError` and classification fields do not exist, and `2056` currently causes more than one call.

- [ ] **Step 3: Implement typed provider policy**

Add this public shape to `src/ai/image_exceptions.py`:

```python
from typing import Literal, Optional

ImageProviderCategory = Literal[
    "configuration",
    "authentication",
    "capacity",
    "rate_limit",
    "timeout",
    "upstream",
    "invalid_request",
    "invalid_response",
]


class ImageProviderError(ImageGenerationError):
    def __init__(
        self,
        *,
        code: str,
        category: ImageProviderCategory,
        retryable: bool,
        public_message: str,
        provider_trace_id: Optional[str] = None,
    ) -> None:
        super().__init__(public_message)
        self.code = code
        self.category = category
        self.retryable = retryable
        self.public_message = public_message
        self.provider_trace_id = provider_trace_id
```

In `image_generator.py`, map provider codes at `_raise_for_minimax_error()`. Keep `1026/1027` as `ContentInspectionError`; classify `1008/2056` as non-retryable capacity, `1004/2049` as non-retryable authentication, `2013` as invalid request, and bounded transient codes as retryable. Convert missing configuration, HTTP status, timeout, connection, JSON decode, and missing image output at the same boundary.

Catch `ImageProviderError` before every broad `ImageGenerationError` or `Exception` retry/fallback block. Re-raise immediately when `retryable is False`; retry transient failures only up to `IMAGE_MAX_RETRIES`, and never multiply account-wide failures across fallback models or character variants.

- [ ] **Step 4: Run provider tests and existing image client tests GREEN**

Run:

```bash
python -m pytest \
  tests/test_image_provider_failure_contract.py \
  tests/test_image_client_refactor.py \
  tests/test_edit_image_extra_params_contract.py \
  tests/test_minimax_image_generation_contract.py -q
```

Expected: all tests pass and the `2056` counter is exactly one.

- [ ] **Step 5: Commit provider classification**

```bash
git add src/ai/image_exceptions.py src/ai/image_generator.py tests/test_image_provider_failure_contract.py
git commit -m "fix(images): classify permanent provider failures"
```

---

### Task 2: Preserve Failure Type Through Services and HTTP APIs

**Files:**
- Modify: `src/services/image/__init__.py`
- Modify: `src/services/image_service.py`
- Modify: `src/services/image/character_service.py`
- Modify: `src/services/image/scene_service.py`
- Create: `src/api/routers/image_failures.py`
- Modify: `src/api/routers/images.py`
- Modify: `src/api/routers/collection.py`
- Modify: `tests/test_images_router.py`
- Create: `tests/test_collection_image_failure_contract.py`

**Interfaces:**
- Produces canonical `ImageProviderServiceError` re-exported from `src.services.image_service`.
- Produces `image_failure_http_exception()` and `public_image_failure()`.
- Produces safe HTTP detail `{code, message, retryable, provider_trace_id?}`.

- [ ] **Step 1: Write service identity and route RED tests**

Add assertions:

```python
def capacity_service_error() -> ImageProviderServiceError:
    return ImageProviderServiceError.from_provider(
        ImageProviderError(
            code="minimax_2056",
            category="capacity",
            retryable=False,
            public_message="图片生成额度暂时不可用，请稍后再试",
        )
    )


def test_image_service_uses_one_exception_identity():
    from src.services.image import ImageServiceError as package_error
    from src.services.image_service import ImageServiceError as facade_error

    assert facade_error is package_error


def test_generate_image_capacity_failure_returns_structured_503(client, owned_game):
    with patch("src.api.routers.images.ImageService") as service_class:
        service_class.return_value.generate_character_image.side_effect = capacity_service_error()
        response = client.post(
            "/images/generate",
            json={
                "game_id": owned_game.game_id,
                "image_type": "character",
                "entity_name": "林见微",
                "description": "现代职场人物",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "minimax_2056",
        "message": "图片生成额度暂时不可用，请稍后再试",
        "retryable": False,
    }


def test_collection_character_capacity_failure_returns_same_503(client):
    with patch("src.api.routers.collection.CollectionService") as service_class:
        service_class.return_value.generate_character_image.side_effect = capacity_service_error()
        response = client.post("/collection/1/characters/林见微/generate-image")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "minimax_2056"
```

- [ ] **Step 2: Run route tests and verify RED**

Run:

```bash
python -m pytest \
  tests/test_images_router.py \
  tests/test_collection_image_failure_contract.py -q
```

Expected: exception identity differs and provider failures return 500.

- [ ] **Step 3: Unify service exceptions and add safe router mapper**

Define only once in `src/services/image/__init__.py`:

```python
class ImageProviderServiceError(ImageServiceError):
    def __init__(self, provider_error: ImageProviderError) -> None:
        super().__init__(provider_error.public_message)
        self.code = provider_error.code
        self.category = provider_error.category
        self.retryable = provider_error.retryable
        self.public_message = provider_error.public_message
        self.provider_trace_id = provider_error.provider_trace_id

    @classmethod
    def from_provider(cls, error: ImageProviderError) -> "ImageProviderServiceError":
        return cls(error)
```

Delete duplicate exception class definitions from `src/services/image_service.py`; import and re-export the canonical classes. In every character, scene, location, item, opening, and regenerate path, catch `ImageProviderError` before generic `ImageGenerationError` and raise `ImageProviderServiceError.from_provider(error)`.

Create `src/api/routers/image_failures.py`:

```python
def public_image_failure(error: ImageProviderServiceError) -> dict[str, object]:
    detail: dict[str, object] = {
        "code": error.code,
        "message": error.public_message,
        "retryable": error.retryable,
    }
    if error.provider_trace_id:
        detail["provider_trace_id"] = error.provider_trace_id
    return detail


def image_failure_http_exception(error: ImageProviderServiceError) -> HTTPException:
    status = 422 if error.category == "invalid_request" else 503
    return HTTPException(status_code=status, detail=public_image_failure(error))
```

Use this helper in all `/images` and `/collection/*generate-image` routes before generic `ImageServiceError`. Log only correlation fields (`provider=minimax`, `code`, `category`, `trace_id`, route/stage), not raw prompts or credentials.

- [ ] **Step 4: Run route and service tests GREEN**

Run:

```bash
python -m pytest \
  tests/test_images_router.py \
  tests/test_collection_image_failure_contract.py \
  tests/test_image_service.py \
  tests/test_scene_image_integrity_narrow_contract.py -q
```

Expected: all tests pass; provider failures are structured 503/422 and generic programming errors remain 500.

- [ ] **Step 5: Commit service/API mapping**

```bash
git add src/services/image src/services/image_service.py src/api/routers/image_failures.py src/api/routers/images.py src/api/routers/collection.py tests/test_images_router.py tests/test_collection_image_failure_contract.py
git commit -m "fix(images): preserve provider failures through APIs"
```

---

### Task 3: Make Background Scene Failure Terminal Until Explicit Retry

**Files:**
- Modify: `src/api/routers/images.py`
- Modify: `tests/test_scene_image_sse_integration.py`
- Modify: `tests/test_scene_image_imports.py`
- Modify: `tests/test_gate_real_db_no_mock.py`

**Interfaces:**
- `GET /images/scene/{game_id}/{round_number}?week=W&stage=S` consumes cached terminal state.
- Optional `retry=true` is the only GET path that clears a cached terminal failure and starts a new background attempt.
- SSE `scene_image_failed` carries the same safe structured failure fields as HTTP.

- [ ] **Step 1: Write terminal-failure RED tests**

```python
def test_scene_get_does_not_restart_cached_terminal_failure(client, monkeypatch):
    key = _get_event_key(7, 2, 1, "event")
    _scene_image_latest[key] = {
        "type": "scene_image_failed",
        "game_id": 7,
        "week": 2,
        "round_number": 1,
        "stage": "event",
        "code": "minimax_2056",
        "message": "图片生成额度暂时不可用，请稍后再试",
        "retryable": False,
    }
    starts: list[dict[str, object]] = []
    monkeypatch.setattr(
        "src.api.routers.images._trigger_scene_generation_in_background",
        lambda **kwargs: starts.append(kwargs),
    )

    first = client.get("/images/scene/7/1?week=2&stage=event")
    second = client.get("/images/scene/7/1?week=2&stage=event")

    assert first.status_code == second.status_code == 503
    assert starts == []


def test_explicit_scene_retry_clears_failure_and_starts_once(client, monkeypatch):
    key = _get_event_key(7, 2, 1, "event")
    _scene_image_latest[key] = {
        "type": "scene_image_failed",
        "game_id": 7,
        "week": 2,
        "round_number": 1,
        "stage": "event",
        "code": "minimax_2056",
        "message": "图片生成额度暂时不可用，请稍后再试",
        "retryable": False,
    }
    starts: list[dict[str, object]] = []
    monkeypatch.setattr(
        "src.api.routers.images._trigger_scene_generation_in_background",
        lambda **kwargs: starts.append(kwargs),
    )

    response = client.get("/images/scene/7/1?week=2&stage=event&retry=true")

    assert response.status_code == 202
    assert len(starts) == 1
```

- [ ] **Step 2: Run scene tests and verify RED**

Run:

```bash
python -m pytest \
  tests/test_scene_image_sse_integration.py \
  tests/test_scene_image_imports.py \
  tests/test_gate_real_db_no_mock.py -q
```

Expected: repeated GET starts generation again and `retry` is not supported.

- [ ] **Step 3: Cache safe failure and require explicit retry**

Before auto-triggering a missing scene, read `_scene_image_latest[key]`. If it is `scene_image_failed` and `retry` is false, return its safe status/detail without starting a thread. If `retry` is true, remove the failed entry atomically before using `_scene_image_inflight` deduplication.

In the background exception handler, serialize `ImageProviderServiceError` with `public_image_failure()` and never publish `str(error)` for provider failures. Always discard the in-flight key in `finally`, while leaving the terminal failure cached.

- [ ] **Step 4: Run scene tests GREEN**

Run the same command from Step 2. Expected: all tests pass and the start counter remains zero until explicit retry.

- [ ] **Step 5: Commit scene failure state**

```bash
git add src/api/routers/images.py tests/test_scene_image_sse_integration.py tests/test_scene_image_imports.py tests/test_gate_real_db_no_mock.py
git commit -m "fix(images): cache terminal scene failures"
```

---

### Task 4: Show Actionable Frontend Failures Without Blind Retries

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/__tests__/lib/apiRetryPolicy.test.ts`
- Modify: `frontend/src/__tests__/lib/api.error-handling.test.ts`
- Modify: `frontend/src/stores/useImageStore.ts`
- Modify: `frontend/src/__tests__/stores/useImageStore.test.ts`
- Modify: `frontend/src/stores/useSceneImageStore.ts`
- Modify: `frontend/src/__tests__/stores/useSceneImageStore.test.ts`
- Modify: `frontend/src/components/create/StepPortrait.tsx`
- Modify: `frontend/src/__tests__/components/StepPortrait.test.tsx`
- Modify: `frontend/src/app/create/page.tsx`
- Modify: `frontend/src/hooks/useCharacterCreation.ts`
- Modify: `frontend/src/components/game/RoundSceneImage.tsx`
- Modify: `frontend/src/__tests__/components/HistorySceneImage.test.tsx`
- Modify: `frontend/src/app/play/page.tsx`

**Interfaces:**
- API errors retain `status`, `code`, and `retryable`.
- `useImageStore.imageGenerationError` owns portrait failure text.
- `useSceneImageStore.roundSceneError` owns current scene failure text.
- `fetchRoundSceneImage(..., {retry: true})` is used only by explicit UI actions.

- [ ] **Step 1: Write frontend RED tests**

Add these behaviors:

```typescript
it("does not retry image generation mutations on 503", () => {
  expect(shouldRetryApiResponse(503, "/images/generate", 0)).toBe(false);
  expect(shouldRetryApiResponse(503, "/collection/1/characters/A/generate-image", 0)).toBe(false);
});

it("retains structured image failure metadata", async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: false,
    status: 503,
    statusText: "Service Unavailable",
    json: async () => ({
      detail: { code: "minimax_2056", message: "图片生成额度暂时不可用，请稍后再试", retryable: false },
    }),
  });
  await expect(api.images.generate({
    game_id: 1,
    image_type: "character",
    entity_name: "林见微",
    description: "现代职场人物",
  })).rejects.toMatchObject({
    status: 503,
    code: "minimax_2056",
    retryable: false,
  });
});

it("shows a portrait placeholder and retry after provider failure", async () => {
  render(<StepPortrait {...props} imageGenerationError="图片生成额度暂时不可用，请稍后再试" />);
  expect(screen.getByText("图片生成额度暂时不可用，请稍后再试")).toBeVisible();
  expect(screen.getByRole("button", { name: "重试生成人物形象" })).toBeEnabled();
});

it("stops scene loading and requires explicit retry after 503", async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: false,
    status: 503,
    statusText: "Service Unavailable",
    json: async () => ({
      detail: { code: "minimax_2056", message: "图片生成额度暂时不可用，请稍后再试", retryable: false },
    }),
  });
  await useSceneImageStore.getState().fetchRoundSceneImage(1, 0, 0, "event");
  expect(useSceneImageStore.getState()).toMatchObject({
    isLoadingRoundSceneImage: false,
    roundSceneError: "图片生成额度暂时不可用，请稍后再试",
  });
});
```

- [ ] **Step 2: Run frontend tests and verify RED**

Run:

```bash
cd frontend
npx jest \
  src/__tests__/lib/apiRetryPolicy.test.ts \
  src/__tests__/lib/api.error-handling.test.ts \
  src/__tests__/stores/useImageStore.test.ts \
  src/__tests__/stores/useSceneImageStore.test.ts \
  src/__tests__/components/StepPortrait.test.tsx --runInBand
```

Expected: image 503 retries three times, metadata is absent, and the stores/components lack failure state.

- [ ] **Step 3: Implement API and store failure state**

In `api.ts`, identify non-idempotent image generation/regeneration paths and return `false` from retry policy for every response status. When parsing object detail, attach metadata:

```typescript
throw Object.assign(new Error(errorMessage), {
  status: response.status,
  code: typeof detailRecord.code === "string" ? detailRecord.code : undefined,
  retryable: typeof detailRecord.retryable === "boolean" ? detailRecord.retryable : undefined,
});
```

Add `imageGenerationError` and `roundSceneError`, clear them only when an explicit new attempt begins or succeeds, and set them on terminal API/SSE failure. Initial scene fetch uses no retry query; buttons call `fetchRoundSceneImage(..., { retry: true })`.

- [ ] **Step 4: Implement actionable placeholders**

`StepPortrait` renders the provider message instead of an indefinite spinner when `imageGenerationError` is set and calls a supplied `onRetryGeneration`. `RoundSceneImageDisplay` renders `roundSceneError`, keeps existing images visible when present, and labels the explicit action “重试生成场景插画”. Collection keeps its existing error panel, now backed by the safe structured message and a single network request.

- [ ] **Step 5: Run focused frontend tests and typecheck GREEN**

Run:

```bash
cd frontend
npx jest \
  src/__tests__/lib/apiRetryPolicy.test.ts \
  src/__tests__/lib/api.error-handling.test.ts \
  src/__tests__/stores/useImageStore.test.ts \
  src/__tests__/stores/useSceneImageStore.test.ts \
  src/__tests__/components/StepPortrait.test.tsx \
  src/__tests__/pages/CreatePage.test.tsx \
  src/__tests__/pages/PlayPage.test.tsx --runInBand
npx tsc --noEmit --strict
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit frontend failure UX**

```bash
git add frontend/src/lib/api.ts frontend/src/stores/useImageStore.ts frontend/src/stores/useSceneImageStore.ts frontend/src/components/create/StepPortrait.tsx frontend/src/app/create/page.tsx frontend/src/hooks/useCharacterCreation.ts frontend/src/components/game/RoundSceneImage.tsx frontend/src/app/play/page.tsx frontend/src/__tests__
git commit -m "fix(frontend): expose actionable image failures"
```

---

### Task 5: Verification, One-Call Provider Smoke, and PR

**Files:**
- Modify: `docs/superpowers/plans/2026-07-10-p1-02-image-generation.md`

**Interfaces:**
- Verifies every P1-2 invariant and produces PR evidence.

- [ ] **Step 1: Run obsolete-contract and secret scans**

```bash
rg -n "except ImageServiceError.*status_code=500|MiniMax image API returned|Server error: 500" src/api src/services frontend/src
git grep -nE "MINIMAX_API_KEY=.+|IMAGE_API_KEY=.+" -- ':!*.example'
```

Expected: no provider/service availability path maps to generic 500; no secret value is tracked.

- [ ] **Step 2: Run focused backend and frontend suites**

Run all commands from Tasks 1-4. Expected: all exit 0.

- [ ] **Step 3: Run repository gates**

```bash
git diff --check
./test.sh all
```

Expected: all layers pass. If the global E2E lock is held, record the owner and rerun `./test.sh e2e` after release.

- [ ] **Step 4: Run one real provider smoke without blind retry**

Use the configured local `.env` without printing it and call `ImageGenerator.generate_image()` once. Record one of two honest outcomes:

- Success: valid image bytes are returned and the local API/UI path displays the image.
- Provider unavailable: a typed `ImageProviderError` is returned with one provider HTTP call, a safe public code/message, and no secret/prompt leak. Do not call mock success a production success.

- [ ] **Step 5: Browser-smoke three user paths**

1. Character creation portrait: failure stops loading and shows placeholder plus retry.
2. Collection character generation: one request, safe message, button becomes usable again.
3. Scene generation: automatic fetch does not restart cached failure; explicit retry starts exactly one new attempt.

- [ ] **Step 6: Final audit and PR preparation**

```bash
git status --short
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
```

Expected: only P1-2 implementation, tests, and this plan are present.

Create one draft PR titled `fix(images): surface provider failures without repeated generation` with:

- current one-call `2056` evidence and official provider semantics;
- root cause including duplicate service exception identities;
- provider-call count before/after;
- HTTP/SSE structured failure contract;
- portrait, collection, and scene browser evidence;
- focused and repository gate results;
- explicit note that account quota availability remains external, while the product no longer reports opaque 500s or multiplies cost.
