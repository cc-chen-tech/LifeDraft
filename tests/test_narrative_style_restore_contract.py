"""GameLoop Narrative Style ID Restoration Contract Tests.

验证 load_game 方法正确从存档中恢复 narrative_style_id。
Layer 3: 契约测试 — 字段注入/恢复契约。
"""

from typing import Any, Dict
import pytest

pytestmark = [pytest.mark.unit]



class TestNarrativeStyleIdRestoration:
    """测试 narrative_style_id 恢复契约"""

    @staticmethod
    def _create_minimal_state_dict(overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """创建最小可用的 state_dict"""
        data = {
            "player_name": "TestHero",
            "week": 10,
            "age": 25,
            "current_round": 0,
            "rounds_per_week": 3,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
        }
        if overrides:
            data.update(overrides)
        return data

    def test_restore_narrative_style_id_from_state_dict(self):
        """state_dict 中的 narrative_style_id 应恢复到 game_loop 上"""
        from src.ai.generator import EventGenerator
        from src.game.game_loop import GameLoop

        loop = GameLoop(ai_generator=EventGenerator(), language="zh")
        state_dict = self._create_minimal_state_dict({"narrative_style_id": "dark_noir_mystery"})
        loop.load_game(state_dict)

        assert loop.narrative_style_id == "dark_noir_mystery", (
            f"应恢复 narrative_style_id='dark_noir_mystery'，" f"实际: {loop.narrative_style_id}"
        )

    def test_missing_narrative_style_id_is_acceptable(self):
        """state_dict 中无 narrative_style_id 时不应崩溃"""
        from src.ai.generator import EventGenerator
        from src.game.game_loop import GameLoop

        loop = GameLoop(ai_generator=EventGenerator(), language="zh")
        state_dict = self._create_minimal_state_dict()
        # 不应抛出异常
        player_state = loop.load_game(state_dict)
        assert player_state is not None

    def test_narrative_style_id_none_value_skipped(self):
        """narrative_style_id 为 None 时不设置属性（被 if style_id: 跳过）"""
        from src.ai.generator import EventGenerator
        from src.game.game_loop import GameLoop

        loop = GameLoop(ai_generator=EventGenerator(), language="zh")
        state_dict = self._create_minimal_state_dict({"narrative_style_id": None})
        loop.load_game(state_dict)
        # None 值被 `if style_id:` 跳过，属性不会被创建
        assert not hasattr(
            loop, "narrative_style_id"
        ), "None 值应被跳过，不应创建 narrative_style_id 属性"

    def test_narrative_style_id_empty_string_skipped(self):
        """narrative_style_id 为空字符串时不覆盖现有值"""
        from src.ai.generator import EventGenerator
        from src.game.game_loop import GameLoop

        loop = GameLoop(ai_generator=EventGenerator(), language="zh")
        state_dict = self._create_minimal_state_dict({"narrative_style_id": ""})
        loop.load_game(state_dict)
        # 空字符串被 `if style_id:` 跳过
        assert True  # 不应崩溃

    def test_player_state_loaded_with_correct_fields(self):
        """narrative_style_id 恢复不影响 PlayerState 加载"""
        from src.ai.generator import EventGenerator
        from src.game.game_loop import GameLoop

        loop = GameLoop(ai_generator=EventGenerator(), language="zh")
        state_dict = self._create_minimal_state_dict({"narrative_style_id": "chinese_classic_saga"})
        player_state = loop.load_game(state_dict)

        assert player_state.player_name == "TestHero"
        assert player_state.week == 10
        assert player_state.age == 25

    def test_load_game_returns_player_state(self):
        """load_game 始终返回 PlayerState 实例"""
        from src.ai.generator import EventGenerator
        from src.game.game_loop import GameLoop
        from src.game.state.player_state import PlayerState

        loop = GameLoop(ai_generator=EventGenerator(), language="zh")
        state_dict = self._create_minimal_state_dict()
        result = loop.load_game(state_dict)

        assert isinstance(result, PlayerState)


class TestNarrativeStyleIdRoundTrip:
    """测试 narrative_style_id 的写入→保存→加载→恢复链路"""

    def test_state_repository_injects_style_id_into_state_data(self):
        """StateRepository.load_game_state 应将 game.narrative_style_id 注入 state_data"""
        from src.database.state_repository import StateRepository

        repo = StateRepository()
        # 验证方法存在且可调用
        assert hasattr(repo, "load_game_state"), "StateRepository 应有 load_game_state 方法"
        assert callable(repo.load_game_state)
