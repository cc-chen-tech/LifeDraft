# Collection Manual Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let players manually add and safely delete people, items, and landmarks from the collection panel with a polished, accessible story-archive interaction.

**Architecture:** Keep explicit REST endpoints for each entity family and persist through the existing player-state snapshot path. Extend the Zustand collection store with category-specific create actions, then replace the item-only dialog with a reusable category-aware dialog and expose confirmed deletion from each directory row as well as the existing detail dialogs.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy/SQLite integration contracts, React 19, Next.js 16, Zustand, Radix UI, Tailwind CSS 4, Jest/Testing Library.

**Spec:** Approved in chat on 2026-09-12; the visual direction below was explored in Superdesign draft `cd30afb1-ff1c-4724-95a3-63eff9db7ca8`.

## Global Constraints

- Preserve the Story101 Cinematic Cold palette and existing Spline Sans typography.
- Use full-width divided directory rows rather than cards; every interactive target is at least 44px.
- Manual addition is available for people, items, and landmarks; item-only history description extraction remains optional.
- Reject blank and duplicate names; never allow the protagonist to be deleted or manually duplicated.
- Keep add/delete dialogs open when persistence fails and show actionable feedback in the active dialog.
- Persist changes only through `_save_player_state`; do not mutate historical snapshots in place.
- Backend API changes require regenerated OpenAPI and frontend API type artifacts.
- Tests use real state/SQLite contracts for domain behavior; component tests exercise public UI behavior.

---

### Task 1: Domain and API contracts for manual people and landmark creation

**Files:**
- Modify: `src/api/schemas.py`
- Modify: `src/services/collection_service.py`
- Modify: `src/api/routers/collection.py`
- Test: `tests/test_collection_entity_lifecycle_db_contracts.py`
- Test: `tests/test_input_limits_contract.py`
- Test: `tests/test_api_collection.py`

**Interfaces:**
- Consumes: `PlayerState.add_character`, `PlayerState.add_landmark`, `_save_player_state`.
- Produces: `CollectionService.create_character(state, name)`, `CollectionService.create_landmark(state, name)`, `POST /api/collection/{game_id}/characters/create`, and `POST /api/collection/{game_id}/landmarks/create`.

- [ ] **Step 1: Write failing real-state service contracts**

```python
def test_manual_character_and_landmark_creation_uses_safe_defaults_and_rejects_duplicates():
    state = PlayerState(player_name="林岚", week=4)
    service = CollectionService(_session())
    assert service.create_character(state, "  陈舟  ")["name"] == "陈舟"
    assert service.create_landmark(state, "  旧书院  ")["name"] == "旧书院"
    with pytest.raises(ValueError, match="已存在"):
        service.create_character(state, "陈舟")
    with pytest.raises(ValueError, match="主角"):
        service.create_character(state, "林岚")
```

- [ ] **Step 2: Run the service contract and verify RED**

Run: `python -m pytest tests/test_collection_entity_lifecycle_db_contracts.py -q`

Expected: FAIL because `create_character` and `create_landmark` do not exist.

- [ ] **Step 3: Add constrained request schema and minimal service methods**

```python
class CreateCollectionEntityRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=NAME_MAX_CHARS)

def create_character(self, player_state: PlayerState, name: str) -> Dict[str, Any]:
    clean_name = name.strip()
    # Reject blank, protagonist, and duplicate; add CharacterState with safe defaults.

def create_landmark(self, player_state: PlayerState, name: str) -> Dict[str, Any]:
    clean_name = name.strip()
    # Reject blank and duplicate; add LandmarkState with week-aware defaults.
```

- [ ] **Step 4: Add authenticated endpoints and persistence tests**

```python
@router.post("/{game_id}/characters/create")
async def create_character(game_id: int, request: CreateCollectionEntityRequest, ...):
    _, player_state = _get_player_state(game_id, user_id)
    entity = CollectionService(db).create_character(player_state, request.name)
    _save_player_state(game_id, player_state)
    return {"success": True, "character": entity}
```

Add the parallel landmark endpoint, assert 401 for anonymous access, 400 for duplicate/invalid state, success response shape, and a save call after successful creation.

- [ ] **Step 5: Verify GREEN for backend contracts**

Run: `python -m pytest tests/test_collection_entity_lifecycle_db_contracts.py tests/test_input_limits_contract.py tests/test_api_collection.py -q`

Expected: all selected tests pass.

### Task 2: Frontend API and store lifecycle

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/stores/useCollectionStore.ts`
- Test: `frontend/src/__tests__/stores/useCollectionStore.cache.test.ts`
- Generated: `frontend/src/types/openapi-schema.json`
- Generated: `frontend/src/types/api-generated.d.ts`
- Generated: `frontend/src/types/input-limits.generated.ts`

**Interfaces:**
- Consumes: the two new FastAPI endpoints and existing item endpoint.
- Produces: `createCharacter`, `createItem`, and `createLandmark` actions returning `Promise<boolean>` so dialogs close only on success.

- [ ] **Step 1: Write failing store lifecycle tests**

```ts
it.each([
  ["createCharacter", "/api/collection/1/characters/create"],
  ["createLandmark", "/api/collection/1/landmarks/create"],
])("%s persists and refreshes", async (action, endpoint) => {
  const succeeded = await useCollectionStore.getState()[action](1, "新实体");
  expect(succeeded).toBe(true);
  expect(global.fetch).toHaveBeenCalledWith(endpoint, expect.objectContaining({ method: "POST" }));
});
```

Also assert each create action returns `false`, preserves the dialog-facing error, and does not request a refresh when the create response fails.

- [ ] **Step 2: Run targeted store tests and verify RED**

Run: `cd frontend && npm test -- --runInBand src/__tests__/stores/useCollectionStore.cache.test.ts`

Expected: FAIL because character and landmark creation actions are missing and item creation returns void.

- [ ] **Step 3: Implement API clients and boolean store actions**

```ts
createCharacter: (gameId, data) => fetchJson(`/collection/${gameId}/characters/create`, ...)
createLandmark: (gameId, data) => fetchJson(`/collection/${gameId}/landmarks/create`, ...)

createCharacter: async (gameId, name) => {
  set({ isLoading: true, error: null });
  try {
    await api.collection.createCharacter(gameId, { name });
    await get().fetchCollection(gameId, true);
    set({ isLoading: false });
    return true;
  } catch (err) {
    set({ error: message, isLoading: false });
    return false;
  }
}
```

Apply the same success contract to item and landmark creation.

- [ ] **Step 4: Regenerate API contracts**

Run: `cd frontend && npm run sync:api-types`

- [ ] **Step 5: Verify GREEN for store and generated-contract checks**

Run: `cd frontend && npm test -- --runInBand src/__tests__/stores/useCollectionStore.cache.test.ts`

Run: `python -m pytest tests/test_gate_contracts_no_mock.py tests/test_input_limits_contract.py -q`

### Task 3: Category-aware add dialog and refined command strip

**Files:**
- Delete: `frontend/src/components/game/collection/AddItemDialog.tsx`
- Create: `frontend/src/components/game/collection/AddEntityDialog.tsx`
- Modify: `frontend/src/components/game/collection/index.ts`
- Modify: `frontend/src/components/game/collection/types.ts`
- Modify: `frontend/src/components/game/CollectionPanel.tsx`
- Test: `frontend/src/__tests__/components/game/CollectionPanelActions.test.tsx`
- Test: `frontend/src/__tests__/components/game/CollectionPanelVisualContract.test.tsx`

**Interfaces:**
- Consumes: active `CollectionTab` and the three boolean create actions.
- Produces: a reusable add dialog with category-specific title, noun, placeholder, helper text, and item-only description checkbox.

- [ ] **Step 1: Write failing component behavior tests**

```tsx
it.each([
  ["characters", "添加人物", "新人物", "createCharacter"],
  ["items", "添加物品", "新物品", "createItem"],
  ["landmarks", "添加标志物", "新地点", "createLandmark"],
])("adds from the %s tab", async (tab, buttonName, name, action) => {
  renderPanelWithTab(tab);
  await user.click(screen.getByRole("button", { name: buttonName }));
  await user.type(screen.getByRole("textbox", { name: /名称/ }), name);
  await user.click(screen.getByRole("button", { name: "添加" }));
  expect(actionMock(action)).toHaveBeenCalledWith(expect.any(Number), name, expect.anything());
});
```

Assert the history-description checkbox only appears for items, focus returns to the contextual add action, and a failed action keeps the dialog open with its error visible.

- [ ] **Step 2: Run targeted component tests and verify RED**

Run: `cd frontend && npm test -- --runInBand src/__tests__/components/game/CollectionPanelActions.test.tsx src/__tests__/components/game/CollectionPanelVisualContract.test.tsx`

Expected: FAIL because only the item tab exposes manual addition and the dialog is item-specific.

- [ ] **Step 3: Build `AddEntityDialog` and connect all three actions**

Use an entity label map keyed by `CollectionTab`; keep the item checkbox conditional. Replace the stacked full-width command list with a compact flex command strip: contextual add on the left, smart recognition on the right, and retain batch landmark image generation without narrowing either primary target below 44px.

- [ ] **Step 4: Keep failed submissions open and restore focus**

Only close/reset after the chosen create action returns `true`. Render the current create error inside the open dialog using the existing feedback styling.

- [ ] **Step 5: Verify GREEN for add interaction and visual contracts**

Run: `cd frontend && npm test -- --runInBand src/__tests__/components/game/CollectionPanelActions.test.tsx src/__tests__/components/game/CollectionPanelVisualContract.test.tsx`

### Task 4: Discoverable row deletion for all directories

**Files:**
- Modify: `frontend/src/components/game/collection/CharacterList.tsx`
- Modify: `frontend/src/components/game/collection/ItemList.tsx`
- Modify: `frontend/src/components/game/collection/LandmarkList.tsx`
- Modify: `frontend/src/components/game/collection/types.ts`
- Modify: `frontend/src/components/game/CollectionPanel.tsx`
- Test: `frontend/src/__tests__/components/game/CollectionPanelActions.test.tsx`
- Test: `frontend/src/__tests__/components/game/CollectionPanelVisualContract.test.tsx`

**Interfaces:**
- Consumes: `onOpenDeleteConfirm(type, name)` and `deletingEntity`.
- Produces: separate semantic detail and delete buttons per list row; protagonist rows omit delete.

- [ ] **Step 1: Write failing row-action tests**

```tsx
expect(screen.getByRole("button", { name: "删除人物陈晓雨" })).toBeVisible();
expect(screen.queryByRole("button", { name: "删除人物林舟" })).not.toBeInTheDocument();
await user.click(screen.getByRole("button", { name: "删除物品旧怀表" }));
expect(screen.getByRole("dialog", { name: "确认删除" })).toBeVisible();
```

- [ ] **Step 2: Run row-action tests and verify RED**

Run: `cd frontend && npm test -- --runInBand src/__tests__/components/game/CollectionPanelActions.test.tsx src/__tests__/components/game/CollectionPanelVisualContract.test.tsx`

Expected: FAIL because deletion is only inside detail dialogs.

- [ ] **Step 3: Split each row into detail and delete actions**

Keep the detail action flexible and width-safe. Add a trailing `Button` with `variant="quiet"`, `size="icon-touch"`, a rust-colored hover/focus state, a `Trash2` icon, and category-specific accessible name. Disable only the entity currently being deleted.

- [ ] **Step 4: Preserve confirmation, focus, and failure behavior**

Use the existing confirmation dialog. On cancel, focus returns to the row delete action; on successful deletion, it falls back to the active tab. On failure, keep confirmation open and show the store error in the dialog.

- [ ] **Step 5: Verify GREEN for all directory actions**

Run: `cd frontend && npm test -- --runInBand src/__tests__/components/game/CollectionPanelActions.test.tsx src/__tests__/components/game/CollectionPanelVisualContract.test.tsx`

### Task 5: Cross-layer verification and PR delivery

**Files:**
- Review all modified and generated files.

**Interfaces:**
- Consumes: completed backend, store, UI, and generated contracts.
- Produces: one tested commit and one GitHub PR against `main`.

- [ ] **Step 1: Run focused backend and frontend suites**

Run: `python -m pytest tests/test_collection_entity_lifecycle_db_contracts.py tests/test_api_collection.py tests/test_input_limits_contract.py tests/test_gate_contracts_no_mock.py -q`

Run: `cd frontend && npm test -- --runInBand src/__tests__/components/game/CollectionPanelActions.test.tsx src/__tests__/components/game/CollectionPanelVisualContract.test.tsx src/__tests__/stores/useCollectionStore.cache.test.ts`

- [ ] **Step 2: Run cross-layer gates**

Run: `cd frontend && npm run test:types && npm run lint`

Run: `./test.sh all`

- [ ] **Step 3: Review the rendered panel**

Run the local app or the smallest existing browser flow that opens the collection sheet. Check 320px and 544px widths, keyboard focus, add success/failure, row deletion confirmation, and nested overlay order.

- [ ] **Step 4: Inspect diff and commit**

Run: `git diff --check && git status --short && git diff --stat`

Commit: `git commit -m "feat: add manual collection management"`

- [ ] **Step 5: Push and create PR**

Push `codex/collection-manual-management-20260912` and create a PR against `main` containing behavior, UX, contract-generation, and verification evidence.
