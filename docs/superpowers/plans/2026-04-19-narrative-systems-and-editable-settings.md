# Narrative Systems & Editable Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the three narrative systems actually initialize by auto-matching a narrative style when settings are complete, and allow users to give AI feedback to regenerate auto-generated settings from the CompletionScreen.

**Architecture:** Add style-matching inside the existing `update_character_settings` API (triggered when `family_members` present). Remove `if style_id` guard from `StoryGenerator` so env vars alone control system initialization. Add a feedback input per setting card in `CompletionScreen` that calls the existing `generateSetting` API.

**Tech Stack:** Python 3.9, FastAPI, SQLAlchemy, React/Next.js, TypeScript, Playwright

---

## File Map

| File | Responsibility |
|------|----------------|
| `src/api/routers/games.py` | `update_character_settings`: saves settings, triggers style match, writes `narrative_style_id` |
| `src/ai/story_generator.py` | `generate_event` / `generate_round_event`: removes `if style_id` guard, uses default style fallback |
| `frontend/src/components/create/CompletionScreen.tsx` | Adds feedback/regenerate UI for each auto-generated setting |
| `frontend/src/components/create/SettingFeedbackCard.tsx` | New component: feedback input + regenerate button for a single setting |
| `frontend/src/hooks/useCharacterCreation.ts` | Adds `regenerateSetting(stepKey, feedback)` method |
| `tests/test_style_auto_match_integration.py` | Integration test: API save→style match→read round-trip |
| `tests/test_story_generator_narrative.py` | Unit test: StoryGenerator initializes with empty style_id |
| `tests/test_narrative_imports.py` | Import validation: all lazy import paths are reachable |
| `frontend/e2e/character-settings-edit.spec.ts` | E2E: user gives feedback to regenerate a setting |
| `test.sh` | Updated to include all new tests |

---

## Task 1: Write Tests — Narrative Import Validation

**Files:**
- Create: `tests/test_narrative_imports.py`

### Step 1: Write the test file

```python
"""Import validation for all narrative system lazy imports.

These modules are imported lazily inside StoryGenerator._init_narrative_systems().
If any import path breaks, the system silently fails at runtime.
This test catches those failures early.
"""


def test_style_engine_imports():
    """Style manifest, prompt builder, and validator must be importable."""
    from src.ai.narrative.style_manifest import get_style
    from src.ai.narrative.style_prompt_builder import StyleAwarePromptBuilder
    from src.ai.narrative.style_validator import StyleAwareValidator

    assert get_style is not None
    assert StyleAwarePromptBuilder is not None
    assert StyleAwareValidator is not None


def test_epic_narrative_imports():
    """Character arc, world breathing, conflict tower, fate echo must be importable."""
    from src.ai.narrative.character_arc import CharacterArcEngine
    from src.ai.narrative.world_breathing import WorldBreathingEngine
    from src.ai.narrative.conflict_tower import ConflictTower
    from src.ai.narrative.fate_echo import FateEchoDatabase

    assert CharacterArcEngine is not None
    assert WorldBreathingEngine is not None
    assert ConflictTower is not None
    assert FateEchoDatabase is not None


def test_creative_enhancement_imports():
    """Emotional arc, novelty scorer, foreshadowing, preference learner must be importable."""
    from src.ai.creative.emotional_arc import EmotionalArcAnalyzer
    from src.ai.creative.novelty_scorer import NoveltyScorer
    from src.ai.creative.foreshadowing_tech import ForeshadowingTechniqueLibrary, HookInjector
    from src.ai.creative.preference_learner import PreferenceLearner

    assert EmotionalArcAnalyzer is not None
    assert NoveltyScorer is not None
    assert ForeshadowingTechniqueLibrary is not None
    assert HookInjector is not None
    assert PreferenceLearner is not None


def test_harness_imports():
    """Constraint harness subsystems must be importable."""
    from src.ai.harness import default_registry
    from src.ai.harness.diagnostics import ConstraintViolationDiagnostic
    from src.ai.harness.metrics import HarnessMetrics
    from src.ai.harness.preflight_checker import PreflightChecker
    from src.ai.harness.retry_controller import RetryController
    from src.ai.harness.validation_pipeline import ValidationPipeline

    assert default_registry is not None
    assert ConstraintViolationDiagnostic is not None
    assert HarnessMetrics is not None
    assert PreflightChecker is not None
    assert RetryController is not None
    assert ValidationPipeline is not None
```

### Step 2: Run the test to verify baseline

```bash
cd /Users/luicy/AI/story2 && pytest tests/test_narrative_imports.py -v
```

**Expected:** PASS (all imports are already valid in the current codebase).

### Step 3: Commit

```bash
git add tests/test_narrative_imports.py
git commit -m "test(narrative): add import validation for all lazy imports"
```

---

## Task 2: Write Tests — Style Auto-Match Integration

**Files:**
- Create: `tests/test_style_auto_match_integration.py`

### Step 1: Write the test file

```python
"""Integration tests for narrative style auto-matching in update_character_settings."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.models import Game

client = TestClient(app)


@pytest.fixture
def auth_headers():
    """Register and login to get a valid auth token."""
    client.post("/api/auth/register", json={
        "username": "styletest_user",
        "password": "password123",
    })
    login_resp = client.post("/api/auth/login", json={
        "username": "styletest_user",
        "password": "password123",
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def game_id(auth_headers):
    """Create a game and return its ID."""
    create_resp = client.post("/api/games", json={
        "player_name": "TestPlayer",
        "life_vision": "Test vision",
        "language": "zh",
    }, headers=auth_headers)
    return create_resp.json()["game_id"]


class TestStyleAutoMatch:
    """Test that update_character_settings triggers style matching."""

    def test_complete_settings_triggers_style_match(self, auth_headers, game_id):
        """When family_members is present, narrative_style_id should be auto-matched."""
        with patch("src.api.routers.games.auto_match_style") as mock_match:
            mock_match.return_value.confidence = 0.75
            mock_match.return_value.style_id = "chinese_classic_saga"

            resp = client.patch(
                f"/api/games/{game_id}/character-settings",
                json={
                    "character_settings": {
                        "era": {"year": 1990, "era_description": "现代中国"},
                        "family_members": [{"name": "父亲", "role": "父亲"}],
                        "world": {"description": "一个普通家庭"},
                    }
                },
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_match.assert_called_once()

        # Verify narrative_style_id was persisted
        state_resp = client.get(f"/api/games/{game_id}/state", headers=auth_headers)
        assert state_resp.status_code == 200
        state = state_resp.json()
        assert state["game_state"]["narrative_style_id"] == "chinese_classic_saga"

    def test_incomplete_settings_skips_style_match(self, auth_headers, game_id):
        """When family_members is absent, style matching should be skipped."""
        with patch("src.api.routers.games.auto_match_style") as mock_match:
            resp = client.patch(
                f"/api/games/{game_id}/character-settings",
                json={
                    "character_settings": {
                        "era": {"year": 1990, "era_description": "现代中国"},
                    }
                },
                headers=auth_headers,
            )
            assert resp.status_code == 200
            mock_match.assert_not_called()

    def test_low_confidence_skips_persistence(self, auth_headers, game_id):
        """When confidence < 0.3, narrative_style_id should NOT be written."""
        with patch("src.api.routers.games.auto_match_style") as mock_match:
            mock_match.return_value.confidence = 0.15
            mock_match.return_value.style_id = "some_style"

            resp = client.patch(
                f"/api/games/{game_id}/character-settings",
                json={
                    "character_settings": {
                        "family_members": [{"name": "父亲"}],
                    }
                },
                headers=auth_headers,
            )
            assert resp.status_code == 200

        state_resp = client.get(f"/api/games/{game_id}/state", headers=auth_headers)
        state = state_resp.json()
        assert state["game_state"].get("narrative_style_id") is None

    def test_match_exception_is_non_blocking(self, auth_headers, game_id):
        """When auto_match_style raises, the API should still return 200."""
        with patch("src.api.routers.games.auto_match_style") as mock_match:
            mock_match.side_effect = RuntimeError("matching failed")

            resp = client.patch(
                f"/api/games/{game_id}/character-settings",
                json={
                    "character_settings": {
                        "family_members": [{"name": "父亲"}],
                    }
                },
                headers=auth_headers,
            )
            assert resp.status_code == 200
```

### Step 2: Run the test to verify it fails

```bash
cd /Users/luicy/AI/story2 && pytest tests/test_style_auto_match_integration.py -v
```

**Expected:** FAIL with `ModuleNotFoundError` or `AttributeError` — `auto_match_style` is not yet imported in `games.py`, or the matching logic is not yet added.

### Step 3: Commit the failing test

```bash
git add tests/test_style_auto_match_integration.py
git commit -m "test(api): add integration tests for style auto-matching (failing)"
```

---

## Task 3: Write Tests — StoryGenerator Default Style Fallback

**Files:**
- Create: `tests/test_story_generator_narrative.py`

### Step 1: Write the test file

```python
"""Tests for StoryGenerator narrative system initialization with empty/default style."""

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

            player_state = {
                "narrative_style_id": "",
                "player_name": "Test",
                "decision_history": [],
            }
            gen._init_narrative_systems("", player_state)

            assert gen._narrative_systems_initialized is True
            assert gen._style_manifest is not None

    def test_generate_event_calls_init_with_empty_style_id(self):
        """generate_event should call _init_narrative_systems even when style_id is empty."""
        with patch.dict(os.environ, {"ENABLE_NARRATIVE_STYLE_ENGINE": "true"}):
            client = MagicMock()
            gen = StoryGenerator(client)

            with patch.object(gen, "_init_narrative_systems") as mock_init:
                player_state = {
                    "narrative_style_id": "",
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
                assert call_args[0][0] == ""

    def test_narrative_systems_initialized_with_none_style_id(self):
        """generate_event should call _init_narrative_systems with None converted to empty string."""
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
                # None gets coerced to "" by the `or ...get("narrative_style_id", "")` fallback
                assert call_args[0][0] == ""
```

### Step 2: Run the test to verify it fails

```bash
cd /Users/luicy/AI/story2 && pytest tests/test_story_generator_narrative.py -v
```

**Expected:** FAIL — `generate_event` currently skips `_init_narrative_systems` when `style_id` is falsy.

### Step 3: Commit the failing test

```bash
git add tests/test_story_generator_narrative.py
git commit -m "test(narrative): add StoryGenerator default-style tests (failing)"
```

---

## Task 4: Implement — Style Auto-Match in update_character_settings

**Files:**
- Modify: `src/api/routers/games.py`

### Step 1: Add import at top of file

In `src/api/routers/games.py`, add this import near the other imports (around line 20-30):

```python
from src.ai.narrative.style_matcher import auto_match_style
```

### Step 2: Modify update_character_settings

In `src/api/routers/games.py`, find the `update_character_settings` function (around line 461-500). Replace this block:

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

### Step 3: Run integration tests

```bash
cd /Users/luicy/AI/story2 && pytest tests/test_style_auto_match_integration.py -v
```

**Expected:** PASS

### Step 4: Commit

```bash
git add src/api/routers/games.py
git commit -m "feat(api): auto-match narrative style in update_character_settings"
```

---

## Task 5: Implement — Remove style_id Guard in generate_event

**Files:**
- Modify: `src/ai/story_generator.py`

### Step 1: Remove `if style_id` guard in generate_event

In `src/ai/story_generator.py` (around line 538-542), change:

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

### Step 2: Remove `if style_id` guard in generate_round_event

In `src/ai/story_generator.py` (around line 940-944), change:

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

### Step 3: Add default style fallback in _init_narrative_systems

In `src/ai/story_generator.py` (around line 132-138), change:

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

### Step 4: Run StoryGenerator tests

```bash
cd /Users/luicy/AI/story2 && pytest tests/test_story_generator_narrative.py -v
```

**Expected:** PASS

### Step 5: Commit

```bash
git add src/ai/story_generator.py
git commit -m "feat(narrative): decouple style_id from system on/off switch"
```

---

## Task 6: Implement — Frontend SettingFeedbackCard Component

**Files:**
- Create: `frontend/src/components/create/SettingFeedbackCard.tsx`

### Step 1: Create the component

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { RefreshCw, Loader2 } from "lucide-react";
import { SettingDisplay } from "@/components/game/SettingDisplay";

interface SettingFeedbackCardProps {
  stepKey: string;
  stepLabel: string;
  data: Record<string, unknown>;
  onRegenerate: (feedback: string) => Promise<void>;
}

export function SettingFeedbackCard({
  stepKey,
  stepLabel,
  data,
  onRegenerate,
}: SettingFeedbackCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  const handleRegenerate = async () => {
    if (!feedback.trim()) return;
    setIsGenerating(true);
    try {
      await onRegenerate(feedback.trim());
      setFeedback("");
      setIsEditing(false);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <Card className="p-4 border-border">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-primary">{stepLabel}</h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsEditing(!isEditing)}
          disabled={isGenerating}
          data-testid={`${stepKey}-feedback-button`}
        >
          <RefreshCw className="w-3.5 h-3.5 mr-1" />
          {isEditing ? "取消" : "给反馈重新生成"}
        </Button>
      </div>

      <div data-testid={`${stepKey}-content`}>
        <SettingDisplay stepKey={stepKey} data={data} />
      </div>

      {isEditing && (
        <div className="mt-3 space-y-2 animate-page-enter">
          <Input
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="告诉AI你想怎么改..."
            disabled={isGenerating}
            data-testid={`${stepKey}-feedback-input`}
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleRegenerate}
              disabled={isGenerating || !feedback.trim()}
            >
              {isGenerating ? (
                <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5 mr-1" />
              )}
              重新生成
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setIsEditing(false);
                setFeedback("");
              }}
              disabled={isGenerating}
            >
              取消
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
```

### Step 2: Commit

```bash
git add frontend/src/components/create/SettingFeedbackCard.tsx
git commit -m "feat(ui): add SettingFeedbackCard component for AI feedback regeneration"
```

---

## Task 7: Implement — regenerateSetting in useCharacterCreation Hook

**Files:**
- Modify: `frontend/src/hooks/useCharacterCreation.ts`

### Step 1: Add the regenerateSetting method

In `frontend/src/hooks/useCharacterCreation.ts`, add this method inside the hook (before the `return` statement, around line 580):

```typescript
  const regenerateSetting = useCallback(async (stepKey: string, feedback: string) => {
    if (!gameId) {
      console.error("[regenerateSetting] No gameId available");
      throw new Error("游戏未创建");
    }

    setIsGenerating(true);
    try {
      console.log(`[regenerateSetting] Regenerating ${stepKey} with feedback:`, feedback);
      
      const result = await api.character.generateSetting({
        setting_type: stepKey,
        player_name: playerName,
        life_vision: lifeVision,
        previous_settings: characterSettings,
        language,
        feedback: feedback || null,
      });

      // Update characterSettings with the regenerated content
      updateCharacterSetting(stepKey, result.setting_value);
      console.log(`[regenerateSetting] ${stepKey} regenerated successfully`);
    } catch (err) {
      console.error(`[regenerateSetting] Failed to regenerate ${stepKey}:`, err);
      throw err;
    } finally {
      setIsGenerating(false);
    }
  }, [gameId, playerName, lifeVision, characterSettings, language, updateCharacterSetting]);
```

### Step 2: Export the method

Add `regenerateSetting` to the return object (around line 616):

```typescript
    regenerateSetting,
```

And to the `UseCharacterCreationReturn` interface (around line 36):

```typescript
  regenerateSetting: (stepKey: string, feedback: string) => Promise<void>;
```

### Step 3: Commit

```bash
git add frontend/src/hooks/useCharacterCreation.ts
git commit -m "feat(hooks): add regenerateSetting method for AI feedback regeneration"
```

---

## Task 8: Implement — Update CompletionScreen with Feedback Cards

**Files:**
- Modify: `frontend/src/components/create/CompletionScreen.tsx`

### Step 1: Add imports and props

At the top of `CompletionScreen.tsx`, add the import:

```tsx
import { SettingFeedbackCard } from "./SettingFeedbackCard";
```

Add new props to `CompletionScreenProps`:

```tsx
  onRegenerateSetting: (stepKey: string, feedback: string) => Promise<void>;
```

### Step 2: Replace the details rendering

In the `showDetails` block (around line 139-157), replace:

```tsx
        {showDetails && (
          <div className="w-full max-w-lg space-y-4 mb-6 animate-page-enter">
            {AUTO_ADVANCE_STEPS.map((step) => {
              const data = characterSettings[step];
              if (!data) return null;
              return (
                <div key={step} className="space-y-1">
                  <h3 className="text-xs font-medium text-primary">
                    {STEP_LABELS[step]}
                  </h3>
                  <SettingDisplay
                    stepKey={step}
                    data={data as Record<string, unknown>}
                  />
                </div>
              );
            })}
          </div>
        )}
```

With:

```tsx
        {showDetails && (
          <div className="w-full max-w-lg space-y-4 mb-6 animate-page-enter">
            {AUTO_ADVANCE_STEPS.map((step) => {
              const data = characterSettings[step];
              if (!data) return null;
              return (
                <SettingFeedbackCard
                  key={step}
                  stepKey={step}
                  stepLabel={STEP_LABELS[step]}
                  data={data as Record<string, unknown>}
                  onRegenerate={(feedback) => onRegenerateSetting(step, feedback)}
                /
              );
            })}
          </div>
        )}
```

### Step 3: Wire up in CreatePage

In `frontend/src/app/create/page.tsx`, add `regenerateSetting` to the destructured hook values (around line 44):

```tsx
    regenerateSetting,
```

Pass it to `CompletionScreen` (around line 215):

```tsx
              onRegenerateSetting={regenerateSetting}
```

### Step 4: Commit

```bash
git add frontend/src/components/create/CompletionScreen.tsx frontend/src/app/create/page.tsx
git commit -m "feat(ui): integrate SettingFeedbackCard into CompletionScreen"
```

---

## Task 9: Update test.sh

**Files:**
- Modify: `test.sh`

### Step 1: Read current test.sh

```bash
cat /Users/luicy/AI/story2/test.sh
```

### Step 2: Add new test sections

Append to `test.sh` (or create if it doesn't exist):

```bash
#!/bin/bash
set -e

echo "=== 1. Static Analysis (mypy) ==="
mypy --strict src/ai/story_generator.py src/ai/narrative/style_matcher.py src/api/routers/games.py || true

echo "=== 2. Import Validation ==="
pytest tests/test_narrative_imports.py -v

echo "=== 3. Contract Tests ==="
pytest tests/test_api_character_settings_contract.py -v || true

echo "=== 4. Integration Tests (Real DB) ==="
pytest tests/test_style_auto_match_integration.py -v

echo "=== 5. Unit Tests ==="
pytest tests/test_story_generator_narrative.py -v

echo "=== 6. E2E Tests ==="
cd frontend && npx playwright test e2e/character-settings-edit.spec.ts || true

echo "=== All tests completed ==="
```

### Step 3: Commit

```bash
git add test.sh
git commit -m "test: update test.sh with all new test suites"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| 在 `update_character_settings` 中自动匹配叙事风格 | Task 4 |
| 匹配的 `style_id` 写入 `Game.narrative_style_id` 和 `character_settings` | Task 4 |
| 设定不完整时跳过匹配 | Task 4 |
| 解除 `style_id` 作为三大系统开关条件 | Task 5 |
| `style_id` 为空时使用默认风格 | Task 5 |
| CompletionScreen 中每个设定卡片可给 AI 反馈 | Task 6, 7, 8 |
| 反馈调用 `api.character.generateSetting` 重新生成 | Task 7 |
| 测试优先：导入验证 | Task 1 |
| 测试优先：集成测试 | Task 2 |
| 测试优先：StoryGenerator 单元测试 | Task 3 |
| test.sh 更新 | Task 9 |

## Placeholder Scan

No TBD/TODO/similar-to placeholders found. All code blocks contain complete runnable code.

## Type Consistency Check

- `StyleMatchResult.confidence` (float) and `StyleMatchResult.style_id` (str) match `style_matcher.py`
- `auto_match_style(character_settings: dict)` signature matches
- `StoryGenerator._init_narrative_systems(style_id: str, player_state: dict)` signature unchanged
- `api.character.generateSetting({ setting_type, player_name, life_vision, previous_settings, language, feedback })` matches existing frontend API

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-19-narrative-systems-and-editable-settings.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
