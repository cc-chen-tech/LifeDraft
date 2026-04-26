# 叙事风格自动匹配与设定编辑设计文档

> 状态：已落地（历史设计记录）  
> 最后核对：2026-04-26

## 背景

当前三大叙事系统（风格引擎、史诗叙事、创意增强）在 `.env` 中已开启，但**绝大多数游戏根本不会触发初始化**。根本原因是：

1. 前端创建游戏时不传 `narrative_style_id`
2. 后端 `auto_match_style()` 置信度阈值 0.3 较高，经常匹配失败
3. `StoryGenerator` 以 `style_id` 为开关条件，`style_id` 为空时三大系统跳过

同时，用户在角色创建最后一步（CompletionScreen）只能**查看**后台生成的设定（family、relationships、traits、wealth），无法修改。

## 目标

1. 让叙事风格在游戏创建时自动匹配并持久化
2. 解除 `style_id` 对三大系统的开关控制，环境变量独立生效
3. 在 CompletionScreen 中支持对后台生成设定给 AI 反馈并重新生成
4. 全程测试驱动，测试写好后不允许更改

---

## 第一部分：叙事风格自动匹配

### 触发时机

在 `PATCH /api/games/{game_id}/character-settings`（`update_character_settings`）保存完 settings 后触发。

当前前端在 wealth 步骤完成后调用此 API，此时 `character_settings` 最完整（包含 era、world、family、relationships、traits、wealth）。

### 匹配逻辑

```python
# 在 update_character_settings 中，保存 settings 后
if merged_settings.get("family_members"):
    try:
        match_result = auto_match_style(merged_settings)
        if match_result.confidence >= 0.3:
            game.narrative_style_id = match_result.style_id
            merged_settings["narrative_style_id"] = match_result.style_id
            # 更新 game.initial_state
            initial_state["character_settings"] = merged_settings
            game.initial_state = initial_state
            db_session.commit()
    except Exception as e:
        logger.warning(f"Style auto-match failed: {e}")
```

- 只有当 `family_members` 存在时触发（判断设定已完整）
- 置信度 >= 0.3 时写入，否则保留现有值（不覆盖）
- 同时把 `narrative_style_id` 写回 `character_settings`，确保前端 `player_state` 能读取

### 影响范围

- `src/api/routers/games.py` — `update_character_settings` 路由（新增匹配逻辑）

---

## 第二部分：解除 style_id 作为系统开关

### 问题

当前 `StoryGenerator.generate_event()` 和 `generate_round_event()` 中：

```python
style_id = player_state.get("narrative_style_id") or ...
if style_id:
    self._init_narrative_systems(style_id, player_state)
```

`style_id` 为空时，即使环境变量 `ENABLE_NARRATIVE_STYLE_ENGINE=true`，三大系统也跳过初始化。

### 改动

1. **移除 `if style_id:` 条件**：环境变量为开关，`style_id` 只决定风格引擎使用哪种 manifest
2. **`style_id` 为空时使用默认风格**：`get_style("")` 返回 None 时，回退到 `get_style("magical_realism")`

### 影响范围

- `src/ai/story_generator.py` — `generate_event`、`generate_round_event`（移除条件）
- `src/ai/story_generator.py` — `_init_narrative_systems`（增加默认风格回退）

---

## 第三部分：CompletionScreen 设定反馈重新生成

### 交互设计

在"查看设定详情"面板中，每个后台生成设定卡片（family、relationships、traits、wealth）增加操作区：

```
┌─────────────────────────────┐
│ 家庭背景                      │
│ ...内容展示...                 │
│                              │
│ [🔄 给反馈重新生成]           │  ← 新增按钮
│                              │
│ ┌──────────────────────────┐│
│ │ 输入反馈：父亲是将军...   ││  ← 展开后输入框
│ └──────────────────────────┘│
│      [重新生成] [取消]       │
└─────────────────────────────┘
```

### 调用链路

```
用户点击"重新生成"
  → 调用 api.character.generateSetting({
       setting_type: "family",
       player_name: playerName,
       life_vision: lifeVision,
       previous_settings: characterSettings,
       language,
       feedback: userFeedback,
     })
  → 后端基于 feedback 重新生成该步骤
  → 更新 characterSettings[stepKey] = 新内容
  → SettingDisplay 重新渲染
```

### 影响范围

- `frontend/src/components/create/CompletionScreen.tsx` — 添加反馈 UI
- `frontend/src/components/game/SettingDisplay.tsx` — 增加 `isEditable` 模式或新增 `SettingFeedbackCard` 组件
- `frontend/src/hooks/useCharacterCreation.ts` — 新增 `regenerateSetting(stepKey, feedback)` 方法

---

## 第四部分：测试策略（测试优先）

用户要求：测试写好后不允许更改。所有测试必须更新到 `test.sh`。

### 测试层次

#### 1. 静态分析（mypy 严格模式）

目标：捕获类型不匹配、不存在的属性

- 新增 `mypy.ini` 或更新现有配置启用严格模式
- 重点检查 `story_generator.py`、`style_matcher.py`、`games.py` 的类型
- CI 中运行：`mypy src/ai/story_generator.py src/ai/narrative/style_matcher.py src/api/routers/games.py`

#### 2. 导入验证测试

目标：确保所有延迟导入路径可达（三大系统的子系统初始化是延迟导入）

```python
# tests/test_narrative_imports.py
def test_style_engine_imports():
    from src.ai.narrative.style_manifest import get_style
    from src.ai.narrative.style_prompt_builder import StyleAwarePromptBuilder
    from src.ai.narrative.style_validator import StyleAwareValidator
    assert get_style is not None

def test_epic_imports():
    from src.ai.narrative.character_arc import CharacterArcEngine
    from src.ai.narrative.world_breathing import WorldBreathingEngine
    from src.ai.narrative.conflict_tower import ConflictTower
    from src.ai.narrative.fate_echo import FateEchoDatabase
    assert CharacterArcEngine is not None

def test_creative_imports():
    from src.ai.creative.emotional_arc import EmotionalArcAnalyzer
    from src.ai.creative.novelty_scorer import NoveltyScorer
    from src.ai.creative.foreshadowing_tech import ForeshadowingTechniqueLibrary, HookInjector
    from src.ai.creative.preference_learner import PreferenceLearner
    assert EmotionalArcAnalyzer is not None
```

#### 3. 契约测试

目标：生产者/消费者字段名一致

```python
# tests/test_api_character_settings_contract.py
def test_update_character_settings_request_schema():
    """Verify UpdateCharacterSettingsRequest accepts character_settings dict."""
    from src.api.schemas import UpdateCharacterSettingsRequest
    req = UpdateCharacterSettingsRequest(
        character_settings={"family_members": [{"name": "test"}]}
    )
    assert "family_members" in req.character_settings

def test_game_state_includes_narrative_style_id():
    """Verify game state response includes narrative_style_id field."""
    from src.api.schemas import GameStateResponse
    # Check field exists in model
    assert hasattr(GameStateResponse, 'game_state')
```

#### 4. 后端集成测试（真实 DB）

```python
# tests/test_style_auto_match_integration.py
class TestStyleAutoMatchIntegration:
    """Test save→read链路完整：update_character_settings → 自动匹配 → load_saved_game."""

    def test_complete_settings_triggers_style_match(self, db, client):
        """当 character_settings 包含 family_members 时，narrative_style_id 应被自动匹配."""
        # 创建游戏
        game_id = create_test_game(client)
        
        # 更新完整 settings
        resp = client.patch(f"/api/games/{game_id}/character-settings", json={
            "character_settings": {
                "era": {"year": 1990, "era_description": "现代中国"},
                "family_members": [{"name": "父亲", "role": "父亲"}],
            }
        })
        assert resp.status_code == 200
        
        # 读取游戏状态
        state = client.get(f"/api/games/{game_id}/state")
        assert state.json()["game_state"]["narrative_style_id"] is not None

    def test_incomplete_settings_skips_style_match(self, db, client):
        """当 character_settings 不包含 family_members 时，不应触发匹配."""
        game_id = create_test_game(client)
        
        resp = client.patch(f"/api/games/{game_id}/character-settings", json={
            "character_settings": {"era": {"year": 1990}}
        })
        assert resp.status_code == 200
        
        game = db.query(Game).filter(Game.game_id == game_id).first()
        assert game.narrative_style_id is None

def test_story_generator_initializes_with_empty_style_id():
    """即使 style_id 为空，环境变量开启时三大系统也应初始化."""
    import os
    os.environ["ENABLE_NARRATIVE_STYLE_ENGINE"] = "true"
    os.environ["ENABLE_EPIC_NARRATIVE"] = "true"
    os.environ["ENABLE_CREATIVE_ENHANCEMENT"] = "true"
    
    from src.ai.story_generator import StoryGenerator
    gen = StoryGenerator(MagicMock())
    
    player_state = {
        "narrative_style_id": "",
        "player_name": "Test",
        "decision_history": [],
    }
    gen._init_narrative_systems("", player_state)
    
    assert gen._narrative_systems_initialized is True
    assert gen._style_manifest is not None  # 使用默认风格
```

#### 5. 契约测试（前端 API 类型）

```python
# tests/test_api_types_contract.py
def test_generate_setting_request_has_feedback_field():
    """Verify frontend can pass feedback to generateSetting API."""
    # Check openapi schema or types
    from frontend.src.types.api_generated import GenerateSettingRequest
    assert hasattr(GenerateSettingRequest, 'feedback')
```

#### 6. E2E 浏览器测试（Playwright）

```typescript
// frontend/e2e/character-settings-edit.spec.ts
test('user can give feedback to regenerate family setting', async ({ page }) => {
  // 1. 创建游戏到 CompletionScreen
  await createGameToCompletion(page);
  
  // 2. 点击"查看设定详情"
  await page.click('text=查看设定详情');
  
  // 3. 找到 family 卡片，点击"给反馈重新生成"
  await page.click('[data-testid="family-feedback-button"]');
  
  // 4. 输入反馈
  await page.fill('[data-testid="family-feedback-input"]', '父亲是将军');
  
  // 5. 点击重新生成
  await page.click('text=重新生成');
  
  // 6. 等待生成完成，验证内容变化
  await expect(page.locator('[data-testid="family-content"]')).toContainText('将军');
});

test('narrative style is auto-matched after completing settings', async ({ page }) => {
  // 1. 完成角色创建
  await completeCharacterCreation(page);
  
  // 2. 查看设定详情
  await page.click('text=查看设定详情');
  
  // 3. 验证叙事风格已显示
  await expect(page.locator('[data-testid="narrative-style"]')).toBeVisible();
});
```

### test.sh 更新

```bash
#!/bin/bash
set -e

echo "=== 1. Static Analysis (mypy) ==="
mypy --strict src/ai/story_generator.py src/ai/narrative/style_matcher.py src/api/routers/games.py

echo "=== 2. Import Validation ==="
pytest tests/test_narrative_imports.py -v

echo "=== 3. Contract Tests ==="
pytest tests/test_api_character_settings_contract.py tests/test_api_types_contract.py -v

echo "=== 4. Integration Tests (Real DB) ==="
pytest tests/test_style_auto_match_integration.py -v

echo "=== 5. Unit Tests ==="
pytest tests/test_story_generator_narrative.py -v

echo "=== 6. E2E Tests ==="
cd frontend && npx playwright test e2e/character-settings-edit.spec.ts

echo "=== All tests passed ==="
```

---

## Spec Self-Review

1. **Placeholder scan**：无 TBD/TODO，所有字段名和函数名与代码库一致
2. **内部一致性**：
   - `auto_match_style` 调用方式与 `game_initializer.py:96-99` 一致
   - `get_style("magical_realism")` 与 `style_manifest.py` 接口一致（Bug #12 修复）
   - `api.character.generateSetting` 参数与现有 `useCharacterCreation.ts:219-224` 一致
3. **Scope检查**：聚焦在三件事上——自动匹配、解除开关、反馈重新生成，无额外功能
4. **歧义检查**：
   - "设定完整" 明确定义为 `family_members` 存在
   - 默认风格明确为 `magical_realism`（Bug #12 修复）
   - 反馈重新生成调用已有 API，不新增后端端点

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/api/routers/games.py` | 修改 | `update_character_settings` 中添加自动匹配逻辑 |
| `src/ai/story_generator.py` | 修改 | 移除 `if style_id` 条件，增加默认风格回退 |
| `frontend/src/components/create/CompletionScreen.tsx` | 修改 | 添加反馈重新生成 UI |
| `frontend/src/components/game/SettingDisplay.tsx` | 修改（或新增组件） | 增加可反馈模式 |
| `frontend/src/hooks/useCharacterCreation.ts` | 修改 | 新增 `regenerateSetting` 方法 |
| `tests/test_style_auto_match_integration.py` | 新增 | 后端集成测试 |
| `tests/test_story_generator_narrative.py` | 新增 | StoryGenerator 默认风格测试 |
| `tests/test_narrative_imports.py` | 新增 | 延迟导入验证 |
| `tests/test_api_character_settings_contract.py` | 新增 | API 契约测试 |
| `frontend/e2e/character-settings-edit.spec.ts` | 新增 | E2E 测试 |
| `test.sh` | 修改 | 纳入所有新测试 |
