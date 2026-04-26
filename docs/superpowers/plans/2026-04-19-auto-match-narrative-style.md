# Auto-Match Narrative Style Implementation Plan

> Status: Implemented (kept as historical implementation plan)  
> Last reviewed: 2026-04-26
>
> **Note:** Default style changed from `chinese_classic_saga` to `magical_realism` (Bug #12 fix, commit 7960409).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In `update_character_settings`, automatically match a narrative style after saving complete character settings, and decouple `style_id` from the on/off switch of the three narrative systems.

**Architecture:** Add a style-matching step inside the existing `update_character_settings` API call, triggered only when settings contain `family_members`. Then modify `StoryGenerator` to always initialize narrative systems when env vars are enabled, using a default style when none is matched.

**Tech Stack:** Python 3.9, FastAPI, SQLAlchemy, existing `StyleMatcher` in `src/ai/narrative/style_matcher.py`

---

## File Map

| File | Responsibility |
|------|----------------|
| `src/api/routers/games.py` | `update_character_settings` route: saves settings, triggers style match, writes `narrative_style_id` to DB |
| `src/ai/story_generator.py` | `generate_event` / `generate_round_event`: removes `if style_id` guard, uses default style fallback |
| `tests/test_style_auto_match.py` | Tests for style matching integration in the API route |
| `tests/test_story_generator_narrative.py` | Tests for `StoryGenerator` default-style fallback |

---

## Task 1: Style Match in `update_character_settings`

**Files:**
- Modify: `src/api/routers/games.py:478-500`
- Test: `tests/test_style_auto_match.py`

### Step 1: Write the failing test

```python
# tests/test_style_auto_match.py
"""Tests for narrative style auto-matching in update_character_settings."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_update_character_settings_triggers_style_match():
    """When family_members is present, narrative_style_id should be auto-matched."""
    # Register and login to get a valid user
    client.post("/api/auth/register", json={
        "username": "styletest",
        "password": "password123",
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "styletest",
        "password": "password123",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a game
    create_resp = client.post("/api/games", json={
        "player_name": "TestPlayer",
        "life_vision": "Test vision",
        "language": "zh",
    }, headers=headers)
    game_id = create_resp.json()["game_id"]

    # Update character_settings with complete settings (includes family_members)
    with patch("src.api.routers.games.auto_match_style") as mock_match:
        mock_match.return_value.confidence = 0.75
        mock_match.return_value.style_id = "magical_realism"

        resp = client.patch(
            f"/api/games/{game_id}/character-settings",
            json={
                "character_settings": {
                    "era": {"year": 1990, "era_description": "现代中国"},
                    "family_members": [{"name": "父亲", "relationship": "父亲"}],
                    "world": {"description": "一个普通家庭"},
                }
            },
            headers=headers,
        )
        assert resp.status_code == 200
        mock_match.assert_called_once()

    # Verify narrative_style_id was persisted
    state_resp = client.get(f"/api/games/{game_id}/state", headers=headers)
    assert state_resp.status_code == 200
    state = state_resp.json()
    assert state["game_state"]["narrative_style_id"] == "magical_realism"


def test_update_character_settings_skips_match_when_incomplete():
    """When family_members is absent, style matching should be skipped."""
    client.post("/api/auth/register", json={
        "username": "styletest2",
        "password": "password123",
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "styletest2",
        "password": "password123",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post("/api/games", json={
        "player_name": "TestPlayer2",
        "life_vision": "Test vision",
        "language": "zh",
    }, headers=headers)
    game_id = create_resp.json()["game_id"]

    with patch("src.api.routers.games.auto_match_style") as mock_match:
        resp = client.patch(
            f"/api/games/{game_id}/character-settings",
            json={
                "character_settings": {
                    "era": {"year": 1990, "era_description": "现代中国"},
                    # No family_members
                }
            },
            headers=headers,
        )
        assert resp.status_code == 200
        mock_match.assert_not_called()
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_style_auto_match.py -v
```

**Expected:** FAIL with `ModuleNotFoundError: No module named 'src.api.routers.games'` or `auto_match_style not found in games.py`.

### Step 3: Implement style matching in `update_character_settings`

```python
# src/api/routers/games.py
# Add import at the top of the file (near other imports)
from src.ai.narrative.style_matcher import auto_match_style

# In update_character_settings, after line 496 (game_session update block):
        # Auto-match narrative style if settings are complete
        if merged_settings.get("family_members"):
            try:
                match_result = auto_match_style(merged_settings)
                if match_result.confidence >= 0.3:
                    game.narrative_style_id = match_result.style_id
                    merged_settings["narrative_style_id"] = match_result.style_id
                    initial_state["character_settings"] = merged_settings
                    game.initial_state = initial_state  # type: ignore[assignment]
                    db_session.commit()
                    logger.info(
                        f"Auto-matched narrative style for game {game_id}: "
                        f"{match_result.style_id} (confidence={match_result.confidence:.2f})"
                    )
            except Exception as e:
                logger.warning(f"Style auto-match failed for game {game_id}: {e}")
```

The exact insertion point is after the `game_session` block (line 494-496) and before `return MessageResponse` (line 498). Replace the existing block:

```python
        # Also update active session if it exists
        game_session = session_store.get(game_id)
        if game_session and game_session.game_loop and game_session.game_loop.player_state:
            game_session.game_loop.player_state.character_settings = merged_settings

        return MessageResponse(success=True, message="Character settings updated")
```

With:

```python
        # Also update active session if it exists
        game_session = session_store.get(game_id)
        if game_session and game_session.game_loop and game_session.game_loop.player_state:
            game_session.game_loop.player_state.character_settings = merged_settings

        # Auto-match narrative style if settings are complete
        if merged_settings.get("family_members"):
            try:
                match_result = auto_match_style(merged_settings)
                if match_result.confidence >= 0.3:
                    game.narrative_style_id = match_result.style_id
                    merged_settings["narrative_style_id"] = match_result.style_id
                    initial_state["character_settings"] = merged_settings
                    game.initial_state = initial_state  # type: ignore[assignment]
                    db_session.commit()
                    logger.info(
                        f"Auto-matched narrative style for game {game_id}: "
                        f"{match_result.style_id} (confidence={match_result.confidence:.2f})"
                    )
            except Exception as e:
                logger.warning(f"Style auto-match failed for game {game_id}: {e}")

        return MessageResponse(success=True, message="Character settings updated")
```

### Step 4: Run tests

```bash
pytest tests/test_style_auto_match.py -v
```

**Expected:** PASS

### Step 5: Commit

```bash
git add src/api/routers/games.py tests/test_style_auto_match.py
git commit -m "feat(api): auto-match narrative style in update_character_settings"
```

---

## Task 2: Decouple `style_id` from System On/Off Switch

**Files:**
- Modify: `src/ai/story_generator.py:538-542` (generate_event)
- Modify: `src/ai/story_generator.py:940-944` (generate_round_event)
- Modify: `src/ai/story_generator.py:132-138` (_init_narrative_systems style fallback)
- Test: `tests/test_story_generator_narrative.py`

### Step 1: Write the failing test

```python
# tests/test_story_generator_narrative.py
"""Tests for StoryGenerator narrative system initialization with default style."""
import os
from unittest.mock import MagicMock, patch

import pytest

from src.ai.story_generator import StoryGenerator


class TestNarrativeSystemInitialization:
    """Test that narrative systems initialize regardless of style_id presence."""

    def test_style_engine_initializes_with_default_when_no_style_id(self):
        """When style_id is empty but env var is enabled, default style should be used."""
        with patch.dict(os.environ, {"ENABLE_NARRATIVE_STYLE_ENGINE": "true"}):
            client = MagicMock()
            gen = StoryGenerator(client)

            # _init_narrative_systems with empty style_id should still initialize
            player_state = {
                "narrative_style_id": "",  # empty
                "player_name": "Test",
                "decision_history": [],
            }
            gen._init_narrative_systems("", player_state)

            # Even with empty style_id, if env var is on, _narrative_systems_initialized should be True
            assert gen._narrative_systems_initialized is True

    def test_narrative_systems_initialized_with_empty_style_id(self):
        """generate_event should call _init_narrative_systems even when style_id is empty."""
        with patch.dict(os.environ, {"ENABLE_NARRATIVE_STYLE_ENGINE": "true"}):
            client = MagicMock()
            gen = StoryGenerator(client)

            # Patch _init_narrative_systems to verify it's called
            with patch.object(gen, "_init_narrative_systems") as mock_init:
                player_state = {
                    "narrative_style_id": "",
                    "player_name": "Test",
                    "decision_history": [],
                    "week": 1,
                }
                # Mock out downstream calls to avoid full generation
                with patch.object(gen, "_gather_narrative_hints", return_value={}):
                    with patch.object(gen.client, "call", return_value="test story"):
                        with patch("src.ai.story_generator.get_story_only_prompt", return_value="prompt"):
                            with patch("src.ai.story_generator.get_system_prompt", return_value="sys"):
                                with patch.object(gen, "_log_constraint_completeness"):
                                    with pytest.raises(Exception):
                                        gen.generate_event(player_state, option_generator=MagicMock())

                # _init_narrative_systems should have been called with empty string
                mock_init.assert_called_once()
                call_args = mock_init.call_args
                assert call_args[0][0] == ""  # style_id is empty string

    def test_narrative_systems_initialized_with_none_style_id(self):
        """generate_event should call _init_narrative_systems with None style_id."""
        with patch.dict(os.environ, {"ENABLE_NARRATIVE_STYLE_ENGINE": "true"}):
            client = MagicMock()
            gen = StoryGenerator(client)

            with patch.object(gen, "_init_narrative_systems") as mock_init:
                player_state = {
                    "narrative_style_id": None,
                    "player_name": "Test",
                    "decision_history": [],
                    "week": 1,
                }
                with patch.object(gen, "_gather_narrative_hints", return_value={}):
                    with patch.object(gen.client, "call", return_value="test story"):
                        with patch("src.ai.story_generator.get_story_only_prompt", return_value="prompt"):
                            with patch("src.ai.story_generator.get_system_prompt", return_value="sys"):
                                with patch.object(gen, "_log_constraint_completeness"):
                                    with pytest.raises(Exception):
                                        gen.generate_event(player_state, option_generator=MagicMock())

                mock_init.assert_called_once()
                call_args = mock_init.call_args
                assert call_args[0][0] == ""  # None becomes "" via fallback
```

### Step 2: Run test to verify it fails

```bash
pytest tests/test_story_generator_narrative.py -v
```

**Expected:** FAIL because `generate_event` currently has `if style_id:` guard that skips `_init_narrative_systems` when style_id is empty/None.

### Step 3: Modify `generate_event` to remove `if style_id` guard

In `src/ai/story_generator.py:538-542`, change:

```python
        style_id = player_state.get("narrative_style_id") or (character_settings or {}).get(
            "narrative_style_id", ""
        )
        if style_id:
            self._init_narrative_systems(style_id, player_state)
```

To:

```python
        style_id = player_state.get("narrative_style_id") or (character_settings or {}).get(
            "narrative_style_id", ""
        )
        self._init_narrative_systems(style_id, player_state)
```

### Step 4: Modify `generate_round_event` to remove `if style_id` guard

In `src/ai/story_generator.py:940-944`, change:

```python
        style_id = player_state.get("narrative_style_id") or (character_settings or {}).get(
            "narrative_style_id", ""
        )
        if style_id:
            self._init_narrative_systems(style_id, player_state)
```

To:

```python
        style_id = player_state.get("narrative_style_id") or (character_settings or {}).get(
            "narrative_style_id", ""
        )
        self._init_narrative_systems(style_id, player_state)
```

### Step 5: Modify `_init_narrative_systems` to use default style fallback

In `src/ai/story_generator.py:132-138`, change:

```python
                self._style_manifest = get_style(style_id)
                if self._style_manifest:
                    self._prompt_builder = StyleAwarePromptBuilder(self._style_manifest)
                    self._style_validator = StyleAwareValidator(self._style_manifest)
                    logger.info(f"Style engine initialized: {style_id}")
                else:
                    logger.warning(f"Style '{style_id}' not found, style engine disabled")
```

To:

```python
                self._style_manifest = get_style(style_id)
                if not self._style_manifest and not style_id:
                    # Use default style when no style_id is matched
                    self._style_manifest = get_style("chinese_classic_saga")
                    logger.info("Using default style: chinese_classic_saga")
                if self._style_manifest:
                    self._prompt_builder = StyleAwarePromptBuilder(self._style_manifest)
                    self._style_validator = StyleAwareValidator(self._style_manifest)
                    logger.info(f"Style engine initialized: {self._style_manifest.style_id}")
                else:
                    logger.warning(f"Style '{style_id}' not found, style engine disabled")
```

### Step 6: Run tests

```bash
pytest tests/test_story_generator_narrative.py -v
```

**Expected:** PASS

### Step 7: Commit

```bash
git add src/ai/story_generator.py tests/test_story_generator_narrative.py
git commit -m "feat(narrative): decouple style_id from system on/off switch"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| 在 `update_character_settings` 保存 settings 后自动匹配叙事风格 | Task 1 |
| 匹配的 `style_id` 写入 `Game.narrative_style_id` 和 `character_settings` | Task 1 |
| 设定不完整时（无 family_members）跳过匹配 | Task 1 |
| 解除 `style_id` 作为三大系统开关条件 | Task 2 |
| `style_id` 为空时使用默认风格 `chinese_classic_saga` | Task 2 |

## Placeholder Scan

No placeholders found. All code blocks contain complete, runnable code.

## Type Consistency Check

- `StyleMatchResult` used in Task 1 matches definition in `style_matcher.py` (has `style_id`, `confidence`, `all_scores`)
- `get_style("chinese_classic_saga")` matches `style_manifest.py` interface
- `StoryGenerator._init_narrative_systems` signature unchanged: `(self, style_id: str, player_state: Dict[str, Any])`

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-19-auto-match-narrative-style.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
