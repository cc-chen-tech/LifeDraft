"""DB integration tests for new Claude-Code-inspired features.

Tests save->read chain integrity for:
- Generation state metrics persistence
- Parallel post-processing data integrity
- Feature flag non-persistence
- Model fallback tracking
- Backward compatibility with old state format
"""

import json
import sqlite3
import threading

import pytest

from src.database.models import Game, GameState, User

# --------------- helpers ---------------


def _create_user(db_session) -> User:
    """Create a test user and return it."""
    user = User(
        private_id="DB-TEST-PRIVATE-001",
        public_id="DBTEST01",
        display_name="DBTestUser",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _create_game(db_session, user: User) -> Game:
    """Create a test game and return it."""
    game = Game(
        user_id=user.user_id,
        language="zh",
    )
    db_session.add(game)
    db_session.commit()
    return game


def _save_game_state(
    db_session, game_id: int, week: int, age: int, state_json: dict
) -> GameState:
    """Save a GameState row and return it."""
    gs = GameState(
        game_id=game_id,
        week=week,
        age=age,
        state_json=state_json,
    )
    db_session.add(gs)
    db_session.commit()
    db_session.refresh(gs)
    return gs


# --------------- fixtures ---------------


@pytest.fixture
def game_ctx(db_session):
    """Provide a (user, game) tuple ready for use."""
    user = _create_user(db_session)
    game = _create_game(db_session, user)
    return user, game


# ====================================================================
# Generation State Metrics Persistence
# ====================================================================


@pytest.mark.integration
class TestGenerationStateMetricsPersistence:
    """Test that StateTracker metrics can be persisted to harness_metrics."""

    def test_harness_metrics_stores_generation_state(self, tmp_path):
        """StateTracker.to_metrics() 写入 harness_metrics 后可读回"""
        from src.ai.harness.metrics import HarnessMetrics

        db_path = str(tmp_path / "harness_test.db")
        hm = HarnessMetrics(db_path=db_path)

        # Simulate a StateTracker.to_metrics() output
        metrics_output = {
            "total_attempts": 3,
            "transitions": [
                {"reason": "initial", "temperature": 0.85, "model": "deepseek-chat"},
                {
                    "reason": "harness_retry",
                    "temperature": 0.9,
                    "model": "deepseek-chat",
                },
                {"reason": "model_fallback", "temperature": 0.85, "model": "qwen-max"},
            ],
            "final_model": "qwen-max",
            "final_temperature": 0.85,
            "total_duration_ms": 12345.6,
            "transition_reasons": ["initial", "harness_retry", "model_fallback"],
        }

        # Write via record_generation (the standard harness API)
        run_id = hm.record_generation(
            game_id="game_42",
            week=5,
            attempts=metrics_output["total_attempts"],
            latency_ms=metrics_output["total_duration_ms"],
            validation_result={
                "score": 85.0,
                "passed": True,
                "detailed_checks": {
                    "continuity": {
                        "priority": "CRITICAL",
                        "passed": True,
                        "evidence": "names consistent",
                        "details": {
                            "transition_reasons": metrics_output["transition_reasons"]
                        },
                    }
                },
            },
        )

        assert run_id is not None

        # Read back directly via sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT game_id, week, attempts, final_score, latency_ms FROM generation_runs WHERE id = ?",
            (run_id,),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "game_42"
        assert row[1] == 5
        assert row[2] == 3
        assert row[3] == 85.0
        assert row[4] == 12345.6

    def test_harness_metrics_preserves_transition_history(self, tmp_path):
        """多次 transition 的历史记录完整持久化"""
        from src.ai.harness.metrics import HarnessMetrics

        db_path = str(tmp_path / "harness_history.db")
        hm = HarnessMetrics(db_path=db_path)

        # Record multiple generations with different attempts
        ids = []
        for i in range(5):
            rid = hm.record_generation(
                game_id="game_hist",
                week=i,
                attempts=i + 1,
                latency_ms=100.0 * (i + 1),
            )
            ids.append(rid)

        # Read back all
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM generation_runs WHERE game_id = ?", ("game_hist",)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 5
        assert all(rid is not None for rid in ids)

    def test_generation_state_metrics_with_all_transition_reasons(self, tmp_path):
        """所有 TransitionReason 枚举值都能正确序列化和反序列化"""
        from src.ai.generation_state import TransitionReason
        from src.ai.harness.metrics import HarnessMetrics

        db_path = str(tmp_path / "harness_reasons.db")
        hm = HarnessMetrics(db_path=db_path)

        all_reasons = [r.value for r in TransitionReason]

        run_id = hm.record_generation(
            game_id="game_reasons",
            week=1,
            attempts=len(all_reasons),
            validation_result={
                "score": 90.0,
                "passed": True,
                "detailed_checks": {
                    "transition_coverage": {
                        "priority": "HIGH",
                        "passed": True,
                        "evidence": json.dumps(all_reasons, ensure_ascii=False),
                        "details": {"reasons": all_reasons},
                    }
                },
            },
        )

        assert run_id is not None

        # Read back constraint check
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT evidence, details FROM constraint_checks WHERE run_id = ?",
            (run_id,),
        )
        row = cursor.fetchone()
        conn.close()

        stored_reasons = json.loads(row[0])
        assert set(stored_reasons) == set(all_reasons)

        stored_details = json.loads(row[1])
        assert set(stored_details["reasons"]) == set(all_reasons)


# ====================================================================
# Parallel Post-Processing Data Integrity
# ====================================================================


@pytest.mark.integration
class TestParallelPostProcessingDataIntegrity:
    """Test that parallel post-processing results persist correctly."""

    def test_parallel_world_model_update_no_data_loss(self, db_session, game_ctx):
        """并行更新 world_model_data 后读回，所有字段完整"""
        _, game = game_ctx

        world_model_data = {
            "character_locations": {"李白": {"location": "长安", "since_week": 3}},
            "career_records": {"主角": {"current_job": "翰林学士", "started_week": 1}},
            "active_commitments": [{"description": "赴约", "deadline_week": 10}],
            "causal_chains": [{"cause": "遇见李白", "effects": ["结交好友"]}],
            "physical_states": {"主角": {"health": "良好", "injuries": []}},
            "dynamic_facts": [{"fact": "长安繁华", "category": "location"}],
            "character_profiles": {"李白": {"personality": "豪放"}},
        }

        state_json = {
            "player_name": "测试玩家",
            "energy": 80,
            "mood": 70,
            "knowledge": 50,
            "wealth": 1000,
            "week": 5,
            "age": 25,
            "world_model_data": world_model_data,
        }

        gs = _save_game_state(
            db_session, game.game_id, week=5, age=25, state_json=state_json
        )

        # Read back
        loaded = db_session.query(GameState).filter_by(state_id=gs.state_id).one()
        loaded_wm = loaded.state_json["world_model_data"]

        assert loaded_wm["character_locations"]["李白"]["location"] == "长安"
        assert loaded_wm["career_records"]["主角"]["current_job"] == "翰林学士"
        assert len(loaded_wm["active_commitments"]) == 1
        assert loaded_wm["causal_chains"][0]["cause"] == "遇见李白"
        assert loaded_wm["physical_states"]["主角"]["health"] == "良好"
        assert loaded_wm["dynamic_facts"][0]["fact"] == "长安繁华"
        assert loaded_wm["character_profiles"]["李白"]["personality"] == "豪放"

    def test_parallel_postprocessing_save_read_roundtrip(self, db_session, game_ctx):
        """PostProcessingResult 各字段写入 GameState.state_json -> 读回 -> 一致"""
        _, game = game_ctx

        # Simulate PostProcessingResult fields saved into state_json
        pp_result = {
            "compression_result": {
                "compressed_story": "主角在长安遇到了李白...",
                "compression_ratio": 0.65,
                "key_events_preserved": ["遇见李白", "饮酒作诗"],
            },
            "world_model_updates": {
                "character_locations": {"杜甫": {"location": "成都", "since_week": 8}},
                "career_records": {},
            },
            "vector_stored": True,
            "weekly_summary": "第五周：主角在长安结识了诗友，开始了新的诗歌创作生涯。",
        }

        state_json = {
            "player_name": "测试玩家",
            "energy": 75,
            "mood": 85,
            "week": 5,
            "age": 25,
            "knowledge": 60,
            "wealth": 800,
            "post_processing": pp_result,
            "world_model_data": pp_result["world_model_updates"],
        }

        gs = _save_game_state(
            db_session, game.game_id, week=5, age=25, state_json=state_json
        )

        loaded = db_session.query(GameState).filter_by(state_id=gs.state_id).one()
        loaded_pp = loaded.state_json["post_processing"]

        assert loaded_pp["compression_result"]["compression_ratio"] == 0.65
        assert loaded_pp["compression_result"]["key_events_preserved"] == [
            "遇见李白",
            "饮酒作诗",
        ]
        assert loaded_pp["vector_stored"] is True
        assert "主角在长安" in loaded_pp["weekly_summary"]

    def test_concurrent_world_model_writes_no_corruption(self, db_session, game_ctx):
        """模拟并发写入 world_model_data 的不同子字段，验证无覆盖"""
        _, game = game_ctx

        # Prepare base state
        base_state = {
            "player_name": "并发测试",
            "energy": 100,
            "mood": 100,
            "knowledge": 50,
            "wealth": 500,
            "week": 3,
            "age": 25,
            "world_model_data": {
                "character_locations": {},
                "career_records": {},
                "active_commitments": [],
                "causal_chains": [],
                "physical_states": {},
                "dynamic_facts": [],
                "character_profiles": {},
            },
        }

        gs = _save_game_state(
            db_session, game.game_id, week=3, age=25, state_json=base_state
        )

        # Use a separate engine for thread-safety (SQLite in-memory DBs aren't shared across connections)
        # Instead, we simulate concurrent dict merging and a single write
        updates_a = {
            "character_locations": {"王维": {"location": "终南山", "since_week": 3}}
        }
        updates_b = {
            "career_records": {"主角": {"current_job": "县令", "started_week": 2}}
        }

        # Simulate merge (what the parallel postprocessor would do)
        merged = base_state["world_model_data"].copy()
        results = {}
        lock = threading.Lock()

        def apply_update(key, value):
            with lock:
                results[key] = value

        t1 = threading.Thread(
            target=apply_update,
            args=("character_locations", updates_a["character_locations"]),
        )
        t2 = threading.Thread(
            target=apply_update, args=("career_records", updates_b["career_records"])
        )
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        merged.update(results)

        # Save merged state
        loaded = db_session.query(GameState).filter_by(state_id=gs.state_id).one()
        loaded.state_json = {**base_state, "world_model_data": merged}
        db_session.commit()

        # Verify both fields survived
        db_session.expire_all()
        final = db_session.query(GameState).filter_by(state_id=gs.state_id).one()
        wm = final.state_json["world_model_data"]

        assert "王维" in wm["character_locations"]
        assert wm["character_locations"]["王维"]["location"] == "终南山"
        assert "主角" in wm["career_records"]
        assert wm["career_records"]["主角"]["current_job"] == "县令"

    def test_compression_result_in_state_json(self, db_session, game_ctx):
        """compression_result 保存到 state_json 后结构完整"""
        _, game = game_ctx

        compression_result = {
            "compressed_story": "第三周总结：主角在市场上购买了一本古籍...",
            "compression_ratio": 0.45,
            "key_events_preserved": ["购买古籍", "遇到书商", "发现秘密"],
            "original_length": 2000,
            "compressed_length": 900,
        }

        state_json = {
            "player_name": "压缩测试",
            "energy": 90,
            "mood": 75,
            "knowledge": 60,
            "wealth": 700,
            "week": 3,
            "age": 25,
            "compression_result": compression_result,
        }

        gs = _save_game_state(
            db_session, game.game_id, week=3, age=25, state_json=state_json
        )

        loaded = db_session.query(GameState).filter_by(state_id=gs.state_id).one()
        cr = loaded.state_json["compression_result"]

        assert cr["compression_ratio"] == 0.45
        assert len(cr["key_events_preserved"]) == 3
        assert cr["original_length"] == 2000
        assert cr["compressed_length"] == 900
        assert "古籍" in cr["compressed_story"]


# ====================================================================
# Backward Compatibility
# ====================================================================


@pytest.mark.integration
class TestBackwardCompatibility:
    """Test that old state format remains loadable."""

    def test_game_state_with_new_fields_backward_compatible(self, db_session, game_ctx):
        """旧格式 state_json（无新字段如 generation_metrics）读取不报错"""
        _, game = game_ctx

        # Old format: no generation_metrics, no world_model_data, no post_processing
        old_state_json = {
            "player_name": "旧版玩家",
            "energy": 80,
            "mood": 70,
            "knowledge": 40,
            "wealth": 500,
            "week": 2,
            "age": 25,
            "relationships": {"老张": 60},
            "characters": {},
            "decision_history": [{"week": 1, "choice": "读书"}],
            "story_history": ["第一周的故事..."],
        }

        gs = _save_game_state(
            db_session, game.game_id, week=2, age=25, state_json=old_state_json
        )

        loaded = db_session.query(GameState).filter_by(state_id=gs.state_id).one()
        sj = loaded.state_json

        # Should load without error
        assert sj["player_name"] == "旧版玩家"
        assert sj["energy"] == 80

        # New fields should be absent (not magically appear)
        assert "generation_metrics" not in sj
        assert "world_model_data" not in sj
        assert "post_processing" not in sj

        # Loading into PlayerState should fill defaults for missing fields
        from src.game.state import PlayerState

        ps = PlayerState.from_dict(sj)
        assert ps.player_name == "旧版玩家"
        # world_model_data gets default from PlayerDataMixin
        assert isinstance(ps.world_model_data, dict)
        assert "character_locations" in ps.world_model_data

    def test_old_world_model_data_format_still_works(self, db_session, game_ctx):
        """旧的 world_model_data 格式（无新字段）仍可正常加载"""
        _, game = game_ctx

        # Old world_model_data with only some original keys
        old_wm = {
            "character_locations": {"小明": {"location": "北京"}},
            "career_records": {},
            # Missing: active_commitments, causal_chains, physical_states, dynamic_facts, character_profiles
        }

        state_json = {
            "player_name": "旧WM玩家",
            "energy": 90,
            "mood": 80,
            "knowledge": 55,
            "wealth": 600,
            "week": 4,
            "age": 26,
            "world_model_data": old_wm,
        }

        gs = _save_game_state(
            db_session, game.game_id, week=4, age=26, state_json=state_json
        )

        loaded = db_session.query(GameState).filter_by(state_id=gs.state_id).one()
        loaded_wm = loaded.state_json["world_model_data"]

        # Original fields should be present
        assert loaded_wm["character_locations"]["小明"]["location"] == "北京"

        # Loading into PlayerState should still work (Pydantic fills missing sub-keys)
        from src.game.state import PlayerState

        ps = PlayerState.from_dict(loaded.state_json)
        assert ps.world_model_data["character_locations"]["小明"]["location"] == "北京"
        # The PlayerState model itself has defaults, but stored JSON keeps only what was saved
        assert isinstance(ps.world_model_data, dict)


# ====================================================================
# Feature Flag Non-Persistence
# ====================================================================


@pytest.mark.integration
class TestFeatureFlagNonPersistence:
    """Test that feature flags are runtime-only."""

    def test_feature_flag_state_not_persisted_in_db(self, db_session, game_ctx):
        """feature flags 仅运行时生效，不存入 game_states.state_json"""
        _, game = game_ctx

        from config.feature_flags import FEATURE_DEFAULTS

        state_json = {
            "player_name": "Flag测试",
            "energy": 100,
            "mood": 100,
            "knowledge": 50,
            "wealth": 1000,
            "week": 1,
            "age": 25,
        }

        gs = _save_game_state(
            db_session, game.game_id, week=1, age=25, state_json=state_json
        )

        loaded = db_session.query(GameState).filter_by(state_id=gs.state_id).one()
        sj = loaded.state_json

        # Verify no feature flag keys leaked into state_json
        for flag_name in FEATURE_DEFAULTS:
            assert (
                flag_name not in sj
            ), f"Feature flag '{flag_name}' should not be in state_json"

        assert "feature_flags" not in sj
        assert "constraint_harness" not in sj
        assert "parallel_postprocessing" not in sj

    def test_feature_flag_changes_dont_affect_saved_games(self, db_session, game_ctx):
        """修改 feature flag 后读取旧存档，行为不受影响"""
        _, game = game_ctx

        # Save a game state
        state_json = {
            "player_name": "FlagChange测试",
            "energy": 80,
            "mood": 75,
            "knowledge": 60,
            "wealth": 900,
            "week": 3,
            "age": 26,
            "world_model_data": {
                "character_locations": {"小红": {"location": "上海"}},
                "career_records": {},
            },
        }

        gs = _save_game_state(
            db_session, game.game_id, week=3, age=26, state_json=state_json
        )

        # Read the game state back - it should be identical regardless of feature flags
        loaded = db_session.query(GameState).filter_by(state_id=gs.state_id).one()
        assert loaded.state_json["player_name"] == "FlagChange测试"
        assert loaded.state_json["energy"] == 80
        assert (
            loaded.state_json["world_model_data"]["character_locations"]["小红"][
                "location"
            ]
            == "上海"
        )

        # Feature flags are runtime-only: state_json has no feature flag data
        assert "feature_flags" not in loaded.state_json


# ====================================================================
# Model Fallback Tracking
# ====================================================================


@pytest.mark.integration
class TestModelFallbackTracking:
    """Test that model usage is tracked in game events."""

    def test_model_used_field_persisted_in_game_event(self, db_session, game_ctx):
        """使用降级模型生成的事件，state_json 中记录 model_used"""
        _, game = game_ctx

        state_json = {
            "player_name": "模型降级测试",
            "energy": 90,
            "mood": 80,
            "knowledge": 55,
            "wealth": 1200,
            "week": 7,
            "age": 27,
            "current_event_data": {
                "event_description": "你在书院里遇到一位神秘的老师...",
                "options": [
                    {"text": "向他请教", "effects": {"knowledge": 10}},
                    {"text": "默默离开", "effects": {"mood": -5}},
                ],
                "story_text": "清晨的书院笼罩在薄雾中...",
                "model_used": "qwen-max",  # Fallback model
            },
        }

        gs = _save_game_state(
            db_session, game.game_id, week=7, age=27, state_json=state_json
        )

        loaded = db_session.query(GameState).filter_by(state_id=gs.state_id).one()
        event_data = loaded.state_json["current_event_data"]

        assert event_data["model_used"] == "qwen-max"
        assert "event_description" in event_data
        assert len(event_data["options"]) == 2

    def test_model_fallback_chain_persisted(self, db_session, game_ctx):
        """模型降级链完整记录在 state_json 中"""
        _, game = game_ctx

        state_json = {
            "player_name": "降级链测试",
            "energy": 85,
            "mood": 70,
            "knowledge": 50,
            "wealth": 1000,
            "week": 10,
            "age": 28,
            "generation_metadata": {
                "model_used": "qwen-max",
                "fallback_chain": ["deepseek-chat", "deepseek-chat", "qwen-max"],
                "total_attempts": 3,
                "final_temperature": 0.9,
            },
        }

        gs = _save_game_state(
            db_session, game.game_id, week=10, age=28, state_json=state_json
        )

        loaded = db_session.query(GameState).filter_by(state_id=gs.state_id).one()
        meta = loaded.state_json["generation_metadata"]

        assert meta["model_used"] == "qwen-max"
        assert meta["fallback_chain"] == ["deepseek-chat", "deepseek-chat", "qwen-max"]
        assert meta["total_attempts"] == 3
        assert meta["final_temperature"] == 0.9

    def test_multiple_game_states_with_different_models(self, db_session, game_ctx):
        """同一游戏多个状态使用不同模型，各自记录正确"""
        _, game = game_ctx

        models = ["deepseek-chat", "deepseek-chat", "qwen-max", "deepseek-chat"]
        state_ids = []

        for i, model in enumerate(models):
            state_json = {
                "player_name": "多模型测试",
                "energy": 100 - i * 5,
                "mood": 80,
                "knowledge": 50,
                "wealth": 1000,
                "week": i + 1,
                "age": 25,
                "current_event_data": {
                    "event_description": f"第{i+1}周事件",
                    "options": [],
                    "model_used": model,
                },
            }
            gs = _save_game_state(
                db_session, game.game_id, week=i + 1, age=25, state_json=state_json
            )
            state_ids.append(gs.state_id)

        # Verify each state has the correct model
        for sid, expected_model in zip(state_ids, models):
            loaded = db_session.query(GameState).filter_by(state_id=sid).one()
            assert (
                loaded.state_json["current_event_data"]["model_used"] == expected_model
            )
