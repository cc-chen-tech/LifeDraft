"""Player Name in Story Prompts Contract Tests

验证故事生成 prompt 中包含主角名称，防止 AI 编造名字导致重复/错乱。
Layer 3: 契约测试 — prompt 输出必须包含 player_name。
"""

from config.prompts import get_round_event_prompt, get_story_only_prompt


class TestPlayerNameInPrompts:
    """测试故事生成 prompt 包含主角名称"""

    def test_story_only_prompt_includes_player_name(self):
        """get_story_only_prompt 输出必须包含传入的 player_name"""
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
            player_name="赵敏",
        )
        assert (
            "赵敏" in prompt
        ), f"prompt 必须包含主角名称 '赵敏'，实际未找到。prompt 前500字: {prompt[:500]}"

    def test_story_only_prompt_has_name_usage_instruction(self):
        """get_story_only_prompt 必须包含使用主角名称的明确指令"""
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
            player_name="赵敏",
        )
        # 指令中应包含要求 AI 始终使用指定名称的表述
        has_instruction = "主角" in prompt and (
            "始终" in prompt or "一直" in prompt or "禁止" in prompt or "不要" in prompt
        )
        assert (
            has_instruction
        ), f"prompt 必须包含主角名称使用指令。prompt 前800字: {prompt[:800]}"

    def test_story_only_prompt_english_includes_player_name(self):
        """英文版 get_story_only_prompt 也必须包含 player_name"""
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
            language="en",
            player_name="Alice",
        )
        assert "Alice" in prompt, "English prompt must contain player name 'Alice'"

    def test_round_event_prompt_includes_player_name(self):
        """get_round_event_prompt 输出必须包含传入的 player_name"""
        player_state = {
            "age": 25,
            "week": 5,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
        }
        prompt = get_round_event_prompt(
            player_state=player_state,
            language="zh",
            round_number=0,
            round_context="",
            player_name="赵敏",
        )
        assert (
            "赵敏" in prompt
        ), f"round prompt 必须包含主角名称 '赵敏'，实际未找到。prompt 前500字: {prompt[:500]}"

    def test_round_event_prompt_has_name_usage_instruction(self):
        """get_round_event_prompt 必须包含使用主角名称的明确指令"""
        player_state = {
            "age": 25,
            "week": 5,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
        }
        prompt = get_round_event_prompt(
            player_state=player_state,
            language="zh",
            round_number=0,
            round_context="",
            player_name="赵敏",
        )
        has_instruction = "主角" in prompt and (
            "始终" in prompt or "一直" in prompt or "禁止" in prompt or "不要" in prompt
        )
        assert (
            has_instruction
        ), f"round prompt 必须包含主角名称使用指令。prompt 前800字: {prompt[:800]}"

    def test_player_name_empty_does_not_break(self):
        """player_name 为空字符串时不应导致错误"""
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
            player_name="",
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0
