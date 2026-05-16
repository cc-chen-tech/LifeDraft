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

    # ── 章节号约束 contract tests ──

    def test_story_only_prompt_has_chapter_label_first_round(self):
        """get_story_only_prompt 新游戏(week=0,current_round=0)必须包含'第一回'章节标识"""
        player_state = {
            "age": 35,
            "week": 0,
            "current_round": 0,
            "rounds_per_week": 3,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
        }
        prompt = get_story_only_prompt(
            player_state=player_state,
            language="zh",
            player_name="狄仁杰",
        )
        assert (
            "第一回" in prompt
        ), f"prompt 必须包含章节标识 '第一回'，未被找到。prompt 前800字: {prompt[:800]}"

    def test_story_only_prompt_has_chapter_constraint_text(self):
        """get_story_only_prompt 必须包含'章节号约束'或'本段故事'等章节定位文本"""
        player_state = {
            "age": 35,
            "week": 0,
            "current_round": 0,
            "rounds_per_week": 3,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
        }
        prompt = get_story_only_prompt(
            player_state=player_state,
            language="zh",
            player_name="狄仁杰",
        )
        assert (
            "本段故事是整体叙事的" in prompt
        ), f"prompt 必须包含章节定位文本，实际未找到。prompt 前800字: {prompt[:800]}"

    def test_story_only_prompt_chapter_label_week2_round0(self):
        """get_story_only_prompt week=2,current_round=0→第7回 (2*3+0+1=7)"""
        player_state = {
            "age": 35,
            "week": 2,
            "current_round": 0,
            "rounds_per_week": 3,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
        }
        prompt = get_story_only_prompt(
            player_state=player_state,
            language="zh",
            player_name="狄仁杰",
        )
        assert (
            "第七回" in prompt
        ), f"prompt 必须包含章节标识 '第七回'，未被找到。prompt 前800字: {prompt[:800]}"

    def test_story_only_prompt_first_chapter_no_prior_reference(self):
        """新游戏第一章prompt应包含禁止提及前情内容"""
        player_state = {
            "age": 35,
            "week": 0,
            "current_round": 0,
            "rounds_per_week": 3,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
        }
        prompt = get_story_only_prompt(
            player_state=player_state,
            language="zh",
            player_name="狄仁杰",
        )
        assert (
            "之前没有任何情节" in prompt
            or "开篇第一回" in prompt
            or "禁止提及" in prompt
        ), f"第一章prompt必须禁止提及前情内容。prompt前800字: {prompt[:800]}"

    def test_round_event_prompt_chapter_label_consistent(self):
        """get_round_event_prompt week=0,round=0→第一回，验证公式一致性"""
        player_state = {
            "age": 35,
            "week": 0,
            "current_round": 0,
            "rounds_per_week": 3,
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
            player_name="狄仁杰",
        )
        assert (
            "第一回" in prompt
        ), f"round_event_prompt 必须包含章节标识 '第一回'。prompt前800字: {prompt[:800]}"

    def test_round_event_prompt_chapter_week2_round0(self):
        """get_round_event_prompt week=2,round=0→第七回，验证跨周章节号"""
        player_state = {
            "age": 35,
            "week": 2,
            "current_round": 0,
            "rounds_per_week": 3,
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
            player_name="狄仁杰",
        )
        assert (
            "第七回" in prompt
        ), f"week=2,round=0→total_chapter=7，必须包含'第七回'。prompt前800字: {prompt[:800]}"

    def test_round_event_prompt_has_chapter_constraint_block(self):
        """get_round_event_prompt 必须包含章节号约束区块"""
        player_state = {
            "age": 35,
            "week": 0,
            "current_round": 0,
            "rounds_per_week": 3,
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
            player_name="狄仁杰",
        )
        assert "章节号约束" in prompt, f"round_event_prompt 必须包含章节号约束区块。prompt前800字: {prompt[:800]}"
        assert "本段故事是整体叙事的" in prompt, "必须包含章节定位说明"
