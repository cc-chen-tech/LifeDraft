"""Name Integrity Contract Tests

验证玩家名称在故事生成管道中保持完整，防止拼接/重复/截断错误。
Layer 3: 契约测试 — 玩家名称从输入到 prompt 必须完全一致。
"""

from config.prompts import get_result_generation_prompt, get_story_only_prompt
import pytest

pytestmark = [pytest.mark.unit]



class TestNameIntegrityContract:
    """测试名称完整性契约"""

    def test_player_name_preserved_in_story_prompt(self):
        """故事生成提示词必须完整保留玩家名称"""
        player_state = {
            "age": 25,
            "week": 5,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
        }
        prompt = get_story_only_prompt(
            player_state=player_state,
            language="zh",
            player_name="赵敏敏",
        )
        assert "赵敏敏" in prompt, "故事提示词应完整保留玩家名称 '赵敏敏'"
        assert "赵敏感感" not in prompt, "玩家名称不应被错误拼接"

    def test_player_name_preserved_in_result_prompt(self):
        """结果生成提示词必须完整保留玩家名称（通过角色设定）"""
        prompt = get_result_generation_prompt(
            event_description="赵敏敏面临选择",
            chosen_option="赵敏敏选择了冒险",
            effects={},
            language="zh",
            character_settings={"identity": {"name": "赵敏敏"}},
        )
        assert "赵敏敏" in prompt, "结果提示词应完整保留玩家名称 '赵敏敏'"
        assert "赵敏感感" not in prompt, "玩家名称不应被错误拼接"

    def test_player_name_with_duplicated_character(self):
        """叠字名称（如王小王）应完整保留"""
        player_state = {
            "age": 25,
            "week": 5,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
        }
        prompt = get_story_only_prompt(
            player_state=player_state,
            language="zh",
            player_name="王小王",
        )
        assert "王小王" in prompt, "叠字名称应完整保留"
        assert "王王王" not in prompt, "叠字名称不应被错误重复"
