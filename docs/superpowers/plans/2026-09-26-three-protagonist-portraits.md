# Three Protagonist Portraits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pre-generate three era-appropriate, visually distinct portraits of one protagonist; persist the choice; make both regeneration actions recoverable and preserve the other candidates.

**Architecture:** Build on the durable single-image job in PR #382. Persist a candidate batch with three independently recoverable slots and a separate per-game selection. Keep image generation, job orchestration, selection, and the React view behind separate interfaces; use the existing image storage and async poll path.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy/SQLite, existing image provider, React, Next.js, Zustand, Jest, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-26-three-protagonist-portraits-design.md`

## Global Constraints

- The three images share name, age, gender, backstory, personality, origin, era and culture; appearance and clothing differ.
- Each slot makes one independent text-to-image call without a reference to another candidate or a shared face anchor.
- Start enqueue after game creation, before the portrait step; no long browser request waits for the provider.
- Keep successful slots and the current selected image through errors, refresh, retries and origin changes.
- Old one-image games stay usable and do not trigger automatic paid generations.
- Scope is `player_main`; other image entities and historic game snapshots retain their existing contracts.
- Automated CI uses provider fakes; a single controlled real-provider visual review is a separate release gate.

## Review Focus

- Two tabs enqueue the same game and origin simultaneously: one batch and at most one provider call per slot (Task 3).
- A provider saves an image and the worker stops before marking its slot complete: recovery reconciles the saved image rather than billing again (Task 3).
- A user selects candidate B while A's feedback edit runs: the edit must not steal selection from B (Task 5).
- A staged fresh batch partially succeeds while the old selection remains in use: the new preview cannot silently change scene references (Tasks 4 and 6).
- A selection request names a foreign, inactive, or unrelated image: reject it without changing the current selection (Task 4).

## File Map

- `src/database/models.py`: candidate batch, slot and per-game selection records; `init_db()` creates the new tables for existing databases.
- `src/services/image/character_service.py`, `src/services/image_service.py`: one candidate image per independent direction, with a small facade delegation; existing storage contract.
- `src/services/portrait_candidate_jobs.py`: batch creation, slot reconciliation, restart recovery and progress projection; keep `portrait_image_jobs.py` responsible for scheduling one durable job.
- `src/services/portrait_selection.py`: ownership-independent selection domain checks, default choice, and scene-reference lookup.
- `src/api/schemas.py`, `src/api/routers/images.py`: authenticated batch, selection and progress endpoints.
- `src/services/image_service.py`, `src/services/image/__init__.py`: selected-image fallback for scene and opening references.
- `frontend/src/lib/api.ts`, `frontend/src/stores/useImageStore.ts`: typed batch API, selected image ID and polling lifecycle.
- `frontend/src/hooks/useCharacterCreation.ts`, `frontend/src/app/create/page.tsx`, `frontend/src/components/create/StepPortrait.tsx`: early enqueue, selection call and three-slot UI.
- `tests/test_portrait_candidates.py`, `tests/test_portrait_image_jobs.py`, `tests/test_image_service_persistence_contracts.py`, frontend store/component tests and `frontend/e2e/portrait-candidates.spec.ts`: behavioral contracts and end-to-end recovery.

---

### Task 1: Persist batches, slots and the selected image

**Files:**
- Modify: `src/database/models.py`
- Create: `src/services/portrait_selection.py`
- Create: `tests/test_portrait_candidates.py`

**Interfaces:**
- Produces: `PortraitCandidateBatch(batch_id, game_id, user_id, job_id, origin_revision, mode, active_key, created_at)`, `PortraitCandidateSlot(batch_id, slot_index, image_id, status, error_code)`, and `PortraitSelection(game_id, image_id, is_user_selected)`.
- Produces: `selected_portrait(db: Session, game_id: int) -> Image | None` and `set_default_portrait(db: Session, game_id: int, image_id: int) -> None`.
- Test helpers in `tests/test_portrait_candidates.py`: `create_owned_game(db) -> Game` inserts a `User` and its `Game`; `add_two_active_portraits(db, game_id) -> tuple[Image, Image]` inserts two active `player_main` images. Reuse these helpers in later tasks.

- [ ] **Step 1: Write failing persistence and legacy fallback tests**

```python
def test_first_slot_sets_default_but_cannot_override_manual_selection(db_session):
    game = create_owned_game(db_session)
    first, second = add_two_active_portraits(db_session, game.game_id)
    set_default_portrait(db_session, game.game_id, first.image_id)
    selection = db_session.get(PortraitSelection, game.game_id)
    selection.image_id, selection.is_user_selected = second.image_id, True
    db_session.commit()
    set_default_portrait(db_session, game.game_id, first.image_id)
    assert selected_portrait(db_session, game.game_id).image_id == second.image_id
```

Also create one legacy active primary image with no selection row and assert `selected_portrait` returns it.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_portrait_candidates.py -q`

Expected: import failure for new models/helper.

- [ ] **Step 3: Add the records and selection fallback**

```python
class PortraitCandidateBatch(Base):
    __tablename__ = "portrait_candidate_batches"
    batch_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    job_id = Column(Integer, ForeignKey("portrait_image_generation_jobs.job_id"), nullable=False, unique=True)
    origin_revision = Column(Integer, nullable=True)
    mode = Column(String(20), nullable=False)  # initial | fresh
    active_key = Column(String(160), nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class PortraitCandidateSlot(Base):
    __tablename__ = "portrait_candidate_slots"
    batch_id = Column(Integer, ForeignKey("portrait_candidate_batches.batch_id"), primary_key=True)
    slot_index = Column(Integer, primary_key=True)
    image_id = Column(Integer, ForeignKey("images.image_id"), nullable=True)
    status = Column(String(20), nullable=False, default="queued")
    error_code = Column(String(80), nullable=True)

class PortraitSelection(Base):
    __tablename__ = "portrait_selections"
    game_id = Column(Integer, ForeignKey("games.game_id"), primary_key=True)
    image_id = Column(Integer, ForeignKey("images.image_id"), nullable=False)
    is_user_selected = Column(Boolean, nullable=False, default=False)
```

Add a unique constraint on `(batch_id, slot_index)` via the composite primary key. `selected_portrait` reads the active selected `player_main` image, then falls back to the newest active primary main-character image for legacy games. `set_default_portrait` inserts only when no selection exists.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/test_portrait_candidates.py -q`

Expected: tests pass. Commit only the three Task 1 files.

### Task 2: Generate three independent era-bound looks

**Files:**
- Modify: `src/services/image/character_service.py`, `src/services/image_service.py`
- Test: `tests/test_character_service_contract.py`

**Interfaces:**
- Produces: `CharacterImageService.generate_character_candidate(*, game_id, name, description, era, character_settings, direction, batch_id, slot_index) -> Image`.
- Consumes: existing image client `generate_character_images(..., num_images=1, reference_image_url=None)` and storage service.

- [ ] **Step 1: Add provider-spy tests for each direction**

```python
@pytest.mark.parametrize("slot_index", [0, 1, 2])
def test_candidate_is_independent_and_keeps_era_constraints(slot_index, service, image_client):
    service.generate_character_candidate(
        game_id=7, name="于谦", description="明代书生，28岁", era="明代",
        character_settings={"era": {"era_name": "明代"}},
        direction=CANDIDATE_DIRECTIONS[slot_index], batch_id=9, slot_index=slot_index,
    )
    call = image_client.generate_character_images.call_args.kwargs
    assert call["num_images"] == 1
    assert call["reference_image_url"] is None
    assert "明代" in call["description"] + str(call["style_hint"])
```

Add one combined test asserting all three prompts use the same core role facts, differ in face/hair/clothing directions, and `generate_appearance_anchor` is never called. Reuse fixture patterns from this file; no paid calls.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_character_service_contract.py -q`

Expected: candidate method is missing.

- [ ] **Step 3: Add explicit direction values and one-image generation**

```python
CANDIDATE_DIRECTIONS = (
    "外貌方向一：方脸、浓眉、利落的发型；穿符合身份和时代的简洁日常服装",
    "外貌方向二：清瘦长脸、细眉、柔和的发型；穿符合身份和时代的另一种层次搭配",
    "外貌方向三：圆脸、短眉、蓬松的发型；穿符合身份和时代的不同剪裁服装",
)

def generate_character_candidate(self, *, game_id, name, description, era,
                                 character_settings, direction, batch_id, slot_index):
    constrained_style = _build_image_era_constraints(character_settings, "zh")
    images, _ = self.image_client.generate_character_images(
        name=name, description=f"{description}。{direction}", era=era,
        style_hint=constrained_style, num_images=1, reference_image_url=None,
    )
    if not images:
        raise ImageServiceError("没有成功生成任何图片")
    return self._save_candidate_image(
        game_id=game_id, name=name, image_data=images[0][0], prompt=images[0][1],
        batch_id=batch_id, slot_index=slot_index, direction=direction,
    )
```

Extract only the shared image-save logic from `generate_character_image` into `_save_candidate_image`; save candidates inactive until the batch worker validates origin and marks the slot ready. Do not change the existing reference-edit behavior.
Add `ImageService.generate_character_candidate` as a direct delegation to `CharacterImageService.generate_character_candidate`; keep orchestration out of the facade. Persist `batch_id`, `slot_index`, direction and the frozen source setting revision in image metadata.

```python
def _save_candidate_image(self, *, game_id, name, image_data, prompt,
                          batch_id, slot_index, direction):
    path, storage_type = self.storage_service.save_image(
        image_data=image_data, game_id=game_id,
        image_type="character", entity_name=f"{name}_{slot_index + 1}",
    )
    image = ImageModel(
        game_id=game_id, image_type="character", entity_name=name,
        entity_key="player_main", prompt_text=prompt, storage_path=path,
        storage_type=storage_type, is_active=False, is_primary=False,
        metadata_json={"batch_id": batch_id, "slot_index": slot_index,
                       "appearance_direction": direction},
    )
    self.db.add(image)
    self.db.commit()
    self.db.refresh(image)
    return image
```

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/test_character_service_contract.py -q`

Expected: all tests pass. Commit Task 2 files.

### Task 3: Durable batch orchestration and progress API

**Files:**
- Create: `src/services/portrait_candidate_jobs.py`
- Modify: `src/services/portrait_image_jobs.py`, `src/api/routers/images.py`, `src/api/schemas.py`
- Test: `tests/test_portrait_candidates.py`, `tests/test_portrait_image_jobs.py`
- Create: `tests/test_api_portrait_candidates.py`

**Interfaces:**
- Produces: `enqueue_candidate_batch(db, user_id, game_id, mode) -> PortraitImageGenerationJob`, `run_candidate_batch(job_id, session_factory, image_service_factory) -> None`, `candidate_batch_state(db, game_id, user_id) -> PortraitCandidateBatchResponse`.
- API: `POST /images/character/candidates`, `GET /images/character/candidates?game_id=`, `POST /images/character/candidates/{batch_id}/retry`.
- Test helpers: `batch_with_two_ready_slots` is a batch with slots 0/1 ready and slot 2 queued; `fake_provider` records slot indices and returns a saved inactive `Image`; `Session` is `sessionmaker(bind=temp_db_file[0])`. Define these in the Task 3 tests before invoking `run_candidate_batch`.

- [ ] **Step 1: Add DB and API failure tests**

```python
def test_batch_returns_before_provider_and_reuses_same_origin(db_session, owner):
    first = enqueue_candidate_batch(db_session, owner.user_id, owner.game_id, "initial")
    second = enqueue_candidate_batch(db_session, owner.user_id, owner.game_id, "initial")
    assert first.job_id == second.job_id
    assert len(db_session.query(PortraitCandidateSlot).all()) == 3

def test_retry_only_missing_slot_after_worker_restart(db_session, batch_with_two_ready_slots, fake_provider):
    run_candidate_batch(batch_with_two_ready_slots.job_id, session_factory=Session, image_service_factory=fake_provider)
    assert fake_provider.generated_slot_indices == [2]
```

Also test simultaneous enqueue with two file-backed SQLite sessions, wrong owner returns 403/404, a stale origin cannot activate a result, and a persisted image with matching batch/slot metadata is reconciled after a crash before another provider call. Define `create_owned_game(db)` and `add_two_active_portraits(db, game_id)` in `tests/test_portrait_candidates.py`; the first creates a `User` and `Game`, and the second creates two active `player_main` images.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_portrait_candidates.py tests/test_portrait_image_jobs.py tests/test_api_portrait_candidates.py -q`

Expected: batch service and routes are missing.

- [ ] **Step 3: Implement idempotent slot execution**

```python
def run_candidate_batch(job_id, *, session_factory=SessionLocal,
                        image_service_factory=ImageService):
    db = session_factory()
    try:
        job = db.get(PortraitImageGenerationJob, job_id)
        batch = db.query(PortraitCandidateBatch).filter_by(job_id=job_id).one()
        for slot in sorted(db.query(PortraitCandidateSlot).filter_by(batch_id=batch.batch_id),
                           key=lambda item: item.slot_index):
            if slot.status == "ready":
                continue
            reconcile_saved_slot(db, batch, slot)
            if slot.status == "ready":
                continue
            generate_one_slot(db, job, batch, slot, image_service_factory)
        finish_batch_from_slots(db, job, batch)
    finally:
        db.close()
```

`generate_one_slot` saves batch/slot metadata with the image; after returning, fence on current origin/job status, mark just this image active and its slot ready, set the first default selection if absent, and commit. On provider error mark that slot failed and keep processing other slots. `reconcile_saved_slot` finds a persisted matching image before retrying; use a constrained metadata scan for this game's `player_main` images to avoid duplicate billing after an image was saved. The job's public status may be `partial_failed`; return three slot states plus `completed_count` and `selected_image_id`. Give active batches a unique `active_key` (`initial:{game_id}:{revision}` or `fresh:{game_id}`); on unique-key conflict reload and return the existing batch, and clear the key only when the job becomes terminal. For `initial`, also return the latest completed batch of the same revision instead of re-generating. Reuse the key when retrying a partial batch. A process-local lock alone is insufficient.
Read the frozen common character facts from the owned `Game`/latest `GameState` at enqueue, store them in the job request, and pass the same snapshot to all three slots. Read `origin_revision` from the same snapshot, so later background completion cannot silently change one slot's input.

- [ ] **Step 4: Add authenticated routes and restart scheduling**

```python
@router.post("/character/candidates", status_code=202,
             response_model=PortraitCandidateBatchResponse)
def create_candidates(req: CreatePortraitCandidatesRequest,
                      db: Session = Depends(get_session),
                      user: int = Depends(get_current_user)):
    verify_game_ownership(db, req.game_id, user)
    job = enqueue_candidate_batch(db, user, req.game_id, req.mode)
    schedule_portrait_image_job(int(job.job_id))
    return candidate_batch_state(db, req.game_id, user)
```

Route latest-state and missing-slot retry through the same ownership check. Extend startup recovery and `run_portrait_image_job` to dispatch candidate jobs by operation without changing legacy one-image job behavior.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python -m pytest tests/test_portrait_candidates.py tests/test_portrait_image_jobs.py tests/test_api_portrait_candidates.py -q`

Expected: selected tests pass. Commit Task 3 files.

### Task 4: Persist user choice and use it for image references

**Files:**
- Modify: `src/services/portrait_selection.py`, `src/api/routers/images.py`, `src/api/schemas.py`
- Modify: `src/services/image_service.py`, `src/services/image/__init__.py`
- Test: `tests/test_portrait_candidates.py`, `tests/test_image_service_persistence_contracts.py`

**Interfaces:**
- Produces: `select_portrait(db: Session, game_id: int, image_id: int) -> Image`, `PUT /images/character/selection`.
- Consumes: Task 1 `selected_portrait` and Task 3 candidate batch/slot records.
- Test helper: `bad_image_id(db, kind)` inserts and returns an image ID for one of `foreign_game`, `inactive`, or `npc`; keep it in `tests/test_portrait_candidates.py` beside the ownership tests.

- [ ] **Step 1: Write failing ownership, refresh and reference tests**

```python
@pytest.mark.parametrize("bad_image_kind", ["foreign_game", "inactive", "npc"])
def test_bad_selection_preserves_current(db_session, owned_game, bad_image_kind):
    before = selected_portrait(db_session, owned_game.game_id).image_id
    with pytest.raises(ValueError):
        select_portrait(db_session, owned_game.game_id, bad_image_id(db_session, bad_image_kind))
    assert selected_portrait(db_session, owned_game.game_id).image_id == before
```

Add a fresh-session DB read after selecting slot 2 and assert both image reference helpers return that ID without an explicit request image. Add a staged-batch test asserting references still return the old selected image until the user picks a new one.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_portrait_candidates.py tests/test_image_service_persistence_contracts.py -q`

Expected: selection action is missing or reference uses `is_primary`.

- [ ] **Step 3: Implement selection and reference lookup**

```python
def select_portrait(db: Session, game_id: int, image_id: int) -> Image:
    image = db.get(Image, image_id)
    if image is None or image.game_id != game_id or image.entity_key != "player_main":
        raise ValueError("图片不属于当前主角")
    if not image.is_active or not is_selectable_candidate(db, game_id, image_id):
        raise ValueError("图片不可选择")
    row = db.get(PortraitSelection, game_id)
    if row is None:
        row = PortraitSelection(game_id=game_id, image_id=image_id, is_user_selected=True)
        db.add(row)
    else:
        row.image_id, row.is_user_selected = image_id, True
    db.commit()
    return image
```

`is_selectable_candidate` accepts ready slots in current/staged batches plus the legacy current main image, and checks the storage object through `ImageStorageService` before committing selection. Replace both `is_primary` fallback queries with `selected_portrait`; validate explicit image IDs as active `player_main` images belonging to this game before using them as references.

- [ ] **Step 4: Expose selection and verify GREEN**

```python
@router.put("/character/selection", response_model=PortraitSelectionResponse)
def put_portrait_selection(req: SelectPortraitRequest,
                           db: Session = Depends(get_session),
                           user: int = Depends(get_current_user)):
    verify_game_ownership(db, req.game_id, user)
    image = select_portrait(db, req.game_id, req.image_id)
    return PortraitSelectionResponse(game_id=req.game_id, image_id=int(image.image_id))
```

Run: `python -m pytest tests/test_portrait_candidates.py tests/test_image_service_persistence_contracts.py -q`. Expected: pass. Commit Task 4 files.

### Task 5: Regenerate one slot or stage a fresh set

**Files:**
- Modify: `src/services/portrait_image_jobs.py`, `src/services/portrait_candidate_jobs.py`, `src/api/routers/images.py`
- Test: `tests/test_portrait_image_jobs.py`, `tests/test_portrait_candidates.py`

**Interfaces:**
- Existing `POST /images/character/regenerate-async` edits the selected slot only; the new UI calls `POST /images/character/candidates` with `mode=fresh` for a new set of three. Keep the older `regenerate-fresh-async` route usable for legacy clients and one-image games.
- Consumes: Task 4 `selected_portrait`/`select_portrait`, Task 3 batch API.

- [ ] **Step 1: Write failing replacement and preservation tests**

```python
def test_feedback_replaces_only_target_slot(db_session, ready_three_slot_batch):
    source_id, other_ids = ready_three_slot_batch.selected_id, ready_three_slot_batch.other_ids
    complete_feedback_job(db_session, source_id, "换一件明代衣服")
    assert all(db_session.get(Image, image_id).is_active for image_id in other_ids)
    assert selected_portrait(db_session, ready_three_slot_batch.game_id).image_id != source_id

def test_selection_changed_during_edit_is_not_stolen(db_session, ready_three_slot_batch):
    pending = enqueue_feedback_job(db_session, ready_three_slot_batch.selected_id)
    select_portrait(db_session, ready_three_slot_batch.game_id, ready_three_slot_batch.other_ids[0])
    finish_feedback_job(db_session, pending)
    assert selected_portrait(db_session, ready_three_slot_batch.game_id).image_id == ready_three_slot_batch.other_ids[0]
```

Also assert failed/superseded edit retains original file and slot; fresh generation with zero successes retains old selection, partial success is selectable, and retry addresses only missing slots. Define `complete_feedback_job`, `enqueue_feedback_job` and `finish_feedback_job` in `tests/test_portrait_candidates.py` using `PortraitImageJobService.enqueue` plus `run_portrait_image_job` with a fake image-service factory.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_portrait_image_jobs.py tests/test_portrait_candidates.py -q`

Expected: legacy worker deactivates every old main-character image.

- [ ] **Step 3: Fence and swap the target slot only**

```python
source_slot = find_ready_slot(db, source_image_id)
if source_slot is not None:
    source = db.get(Image, source_image_id)
    candidate = db.get(Image, new_image_id)
    source_slot.image_id = new_image_id
    source.is_active = False
    candidate.is_active = True
    selection = db.get(PortraitSelection, game_id)
    if selection is not None and selection.image_id == source_image_id:
        selection.image_id = new_image_id
    db.commit()
```

Before this transaction, verify source slot still points at the original image, batch and origin are current, and job is running. Keep unrelated slots and files untouched; delete only the replaced file after a successful commit and only if no retained reference needs it. Route legacy one-image games through their existing behavior.

- [ ] **Step 4: Stage fresh three-slot generation**

```python
def enqueue_fresh_set(db: Session, user_id: int, source_image_id: int):
    source = db.get(Image, source_image_id)
    if selected_portrait(db, source.game_id).image_id != source_image_id:
        raise ValueError("只能从当前选中的形象开始")
    return enqueue_candidate_batch(db, user_id, source.game_id, "fresh")
```

Keep old choice during generation; selecting a ready new slot promotes the new batch. Use the current game setting snapshot for the new batch, not the edited source image as visual reference. The async response remains short.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python -m pytest tests/test_portrait_image_jobs.py tests/test_portrait_candidates.py -q`

Expected: pass. Commit Task 5 files.

### Task 6: Connect creation, store and three-slot UI

**Files:**
- Modify: `frontend/src/lib/api.ts`, `frontend/src/stores/useImageStore.ts`, `frontend/src/hooks/useCharacterCreation.ts`, `frontend/src/app/create/page.tsx`, `frontend/src/components/create/StepPortrait.tsx`
- Generated: `frontend/src/types/openapi-schema.json`, `frontend/src/types/api-generated.d.ts`
- Test: `frontend/src/__tests__/stores/useImageStore.test.ts`, `frontend/src/__tests__/components/StepPortrait.test.tsx`, `frontend/src/__tests__/hooks/useCharacterCreation.test.ts`

**Interfaces:**
- Produces: `api.images.enqueuePortraitCandidates(gameId, mode)`, `api.images.getPortraitCandidates(gameId)`, `api.images.selectPortrait(gameId, imageId)`; store `selectedImageId: number | null`, `selectPlayerImage(imageId): Promise<void>`, `retryMissingPortraitSlots(batchId): Promise<void>`.

- [ ] **Step 1: Write failing store and component tests**

```ts
it('restores the server selected image rather than the first array item', async () => {
  api.images.getPortraitCandidates = jest.fn().mockResolvedValue({
    selected_image_id: 22,
    slots: [{ slot_index: 0, image_id: 11, status: 'ready' },
            { slot_index: 1, image_id: 22, status: 'ready' },
            { slot_index: 2, image_id: null, status: 'running' }],
  });
  await useImageStore.getState().loadPlayerImages(7);
  expect(useImageStore.getState().playerImage?.image_id).toBe(22);
});
```

Test that click calls the selection API and updates the marker only after success, rejection keeps the old marker, world-step game creation enqueues before navigation, old one-image game does not auto-enqueue, and partial batch UI shows `2/3` with retry for the missing slot.

- [ ] **Step 2: Verify RED**

Run: `cd frontend && npm test -- --runInBand src/__tests__/stores/useImageStore.test.ts src/__tests__/components/StepPortrait.test.tsx src/__tests__/hooks/useCharacterCreation.test.ts`

Expected: new API/store actions do not exist.

- [ ] **Step 3: Add typed API and store lifecycle**

```ts
type PortraitSlot = { slot_index: number; image_id: number | null; status: string; error_code?: string | null };
type PortraitCandidateState = {
  batch_id: number; job_id: number; status: string;
  completed_count: number; selected_image_id: number | null; slots: PortraitSlot[];
};

async function selectPlayerImage(imageId: number): Promise<void> {
  const gameId = get().playerImages.find(image => image.image_id === imageId)?.game_id;
  if (!gameId) throw new Error('图片不属于当前游戏');
  const result = await api.images.selectPortrait(gameId, imageId);
  set(state => ({
    selectedImageId: result.image_id,
    selectedImageIndex: state.playerImages.findIndex(image => image.image_id === result.image_id),
    playerImage: state.playerImages.find(image => image.image_id === result.image_id) ?? null,
  }));
}
```

Keep the existing 3-second poll loop but refresh batch progress on every result. If enqueue response is lost, query latest batch before treating it as failure. Do not issue a new enqueue merely because polling failed. Preserve selected ID through `loadPlayerImages` and `setPlayerImages`.

- [ ] **Step 4: Start early and show each slot**

```ts
setGameSession(result.game_id, result.game_id.toString());
void enqueuePortraitCandidates(result.game_id, 'initial');
nextCreationStep();
```

Render three fixed-position slot buttons with `aria-pressed` for the server-selected ID, pending/failure placeholders and a missing-slot retry button. Pass image IDs rather than array indexes through `create/page.tsx`; label fresh regeneration as generating three new images. Keep the old currently-used image visible while a fresh batch is staged.

- [ ] **Step 5: Sync generated types, verify GREEN and commit**

Run: `cd frontend && npm run sync:api-types && npm test -- --runInBand src/__tests__/stores/useImageStore.test.ts src/__tests__/components/StepPortrait.test.tsx src/__tests__/hooks/useCharacterCreation.test.ts && npx tsc --noEmit`

Expected: all selected tests and TypeScript pass. Commit Task 6 files, including generated API types.

### Task 7: Browser recovery and final verification

**Files:**
- Create: `frontend/e2e/portrait-candidates.spec.ts`
- Modify only if the test exposes a concrete defect: files from Tasks 3–6.

**Interfaces:**
- Consumes: candidate batch routes and creation UI; no new product API.
- Test helpers in this new file: `installPortraitRoutes(page, options)` registers mocked batch/enqueue/image routes and records their call count on `page`; `reachPortraitStep(page)` uses the existing character-creation fixture pattern to reach `/create` portrait; `portraitEnqueueCount(page)` returns the recorded count. The route state changes only when the test explicitly advances it.

- [ ] **Step 1: Add deterministic browser scenarios**

```ts
test('restores three candidates after a disconnected enqueue and reload', async ({ page }) => {
  await installPortraitRoutes(page, {
    enqueueDisconnects: true,
    slots: ['ready', 'running', 'failed'],
    selectedImageId: 41,
  });
  await page.goto('/create');
  await reachPortraitStep(page);
  await expect(page.getByText('已完成 1/3')).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: '选择人物形象 1' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: '重试未完成的形象' }).click();
  expect(await portraitEnqueueCount(page)).toBe(1);
});
```

Use Playwright route mocks and a controllable pending promise or virtual clock to represent a provider lasting over 60 seconds without invoking the paid provider. Add a second scenario for a staged fresh batch preserving old selected scene reference until click.

- [ ] **Step 2: Verify RED, repair only discovered defects, verify GREEN**

Run: `cd frontend && npx playwright test e2e/portrait-candidates.spec.ts`

Expected initially: fail on uncovered recovery state. After repair: both scenarios pass. Run browser/E2E only in this integration worktree.

- [ ] **Step 3: Run final focused and broad gates**

Run: `python -m pytest tests/test_portrait_candidates.py tests/test_portrait_image_jobs.py tests/test_character_service_contract.py tests/test_image_service_persistence_contracts.py tests/test_api_portrait_candidates.py -q`

Run: `cd frontend && npm test -- --runInBand src/__tests__/stores/useImageStore.test.ts src/__tests__/components/StepPortrait.test.tsx src/__tests__/hooks/useCharacterCreation.test.ts && npx tsc --noEmit`

Run: `./test.sh all`

Expected: all relevant tests pass; report any pre-existing failures separately. Once local gates pass, push a dependent PR targeting PR #382's branch, inspect the exact HEAD and all CI checks, and keep merge, deployment and paid-provider review as separate decisions.
