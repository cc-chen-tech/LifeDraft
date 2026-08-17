"""Player Name in Story Prompts Contract Tests

验证故事生成 prompt 中包含主角名称，防止 AI 编造名字导致重复/错乱。
Layer 3: 契约测试 — prompt 输出必须包含 player_name。
"""

from config.prompts import (
    get_event_generation_prompt,
    get_round_event_prompt,
    get_story_only_prompt,
)
from src.ai.story_generator import StoryGenerator
import pytest

pytestmark = [pytest.mark.unit]



class TestPlayerNameInPrompts:
    """测试故事生成 prompt 包含主角名称"""

    def test_modern_chinese_prompts_use_week_timeline_not_classical_chapter_title(self):
        """现代/当代背景不应强制章回体“第X回 + 七字对仗标题”."""
        player_state = {
            "age": 22,
            "week": 1,
            "current_round": 1,
            "rounds_per_week": 3,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 50000,
            "relationships": {},
        }
        modern_settings = {
            "era": {
                "year": 2024,
                "era_description": "2020年代中国互联网职场",
                "world_context": "现代社会",
            },
            "world": {"world_description": "现代都市产品经理成长故事"},
            "wealth": {"currency": "¥", "currency_name": "元"},
        }

        prompts = [
            get_event_generation_prompt(
                player_state=player_state,
                language="zh",
                character_settings=modern_settings,
            ),
            get_story_only_prompt(
                player_state=player_state,
                language="zh",
                character_settings=modern_settings,
                player_name="林小夏",
            ),
            get_round_event_prompt(
                player_state=player_state,
                language="zh",
                round_number=1,
                round_context="",
                character_settings=modern_settings,
                player_name="林小夏",
            ),
        ]

        for prompt in prompts:
            assert "第2周·周中" in prompt
            assert "7字对仗标题" not in prompt
            assert "故事开头必须使用\"第" not in prompt
            assert "回\"作为章节标识" not in prompt

    def test_realistic_age_and_career_settings_default_to_modern_timeline_title(self):
        """普通年龄/职业设定缺少现代关键词时，也不应回退到古风章回体。"""
        player_state = {
            "age": 28,
            "week": 2,
            "current_round": 0,
            "rounds_per_week": 3,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 50000,
            "relationships": {},
        }
        realistic_settings = {
            "basic": {"name": "张若虚", "age": 28},
            "career": {"job_title": "产品经理", "company": "创业公司"},
            "wealth": {"currency": "¥", "currency_name": "元"},
        }

        prompts = [
            get_event_generation_prompt(
                player_state=player_state,
                language="zh",
                character_settings=realistic_settings,
            ),
            get_story_only_prompt(
                player_state=player_state,
                language="zh",
                character_settings=realistic_settings,
                player_name="张若虚",
            ),
            get_round_event_prompt(
                player_state=player_state,
                language="zh",
                round_number=0,
                round_context="",
                character_settings=realistic_settings,
                player_name="张若虚",
            ),
        ]

        for prompt in prompts:
            assert "第3周·周一" in prompt
            assert "第七回" not in prompt
            assert "7字对仗标题" not in prompt
            assert "章回体" in prompt and "禁止使用章回体" in prompt

    def test_explicit_ancient_settings_keep_classical_chapter_title(self):
        """明确古代/江湖设定仍可使用章回体标题。"""
        player_state = {
            "age": 28,
            "week": 2,
            "current_round": 0,
            "rounds_per_week": 3,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 50000,
            "relationships": {},
        }
        ancient_settings = {
            "era": {"era_description": "唐朝江湖", "world_context": "古代中国"},
            "world": {"world_description": "长安城外的武侠故事"},
        }

        prompt = get_story_only_prompt(
            player_state=player_state,
            language="zh",
            character_settings=ancient_settings,
            player_name="狄仁杰",
        )

        assert "第七回" in prompt
        assert "7字对仗标题" in prompt
        assert "第3周·周一" not in prompt

    def test_main_event_prompt_injects_required_cast_authority(self):
        """主事件 prompt 必须注入预设关键人物关系网硬约束，不能只给松散名单。"""
        player_state = {
            "player_name": "林小夏",
            "age": 22,
            "week": 1,
            "current_round": 0,
            "rounds_per_week": 3,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 50000,
            "relationships": {"陆昊然": 50, "陈晓雨": 70, "林一凡": 45},
        }
        character_settings = {
            "era": {"year": 2024, "era_description": "2020年代中国互联网职场"},
            "world": {"world_description": "现代都市产品经理成长故事"},
            "relationships": {
                "key_people": [
                    {"name": "陆昊然", "role": "导师", "relationship": "产品负责人导师"},
                    {"name": "陈晓雨", "role": "闺蜜", "relationship": "大学闺蜜"},
                    {"name": "林一凡", "role": "同期", "relationship": "同届入职的产品新人"},
                ]
            },
        }

        prompt = get_event_generation_prompt(
            player_state=player_state,
            language="zh",
            character_settings=character_settings,
        )

        assert "预设关键人物关系" in prompt
        assert "canonical name 必须严格使用" in prompt
        assert "本轮必须至少使用1位预设关键人物" in prompt
        assert "至少80%的预设关系网参与推进" in prompt
        assert "不得把这些人物的身份、关系或剧情功能转移给新命名人物" in prompt
        assert "陆昊然：导师" in prompt
        assert "陈晓雨：闺蜜" in prompt
        assert "林一凡：同期" in prompt

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
        assert has_instruction, f"prompt 必须包含主角名称使用指令。prompt 前800字: {prompt[:800]}"

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

    def test_marked_player_role_name_overrides_generated_session_name(self):
        """角色设定明确标记玩家角色时，不应把测试会话名写入叙事主角约束。"""
        player_state = {
            "player_name": "心跳测试0737",
            "age": 28,
            "week": 3,
            "current_round": 0,
            "rounds_per_week": 3,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 500000,
            "relationships": {"王思远": 45},
        }
        character_settings = {
            "era": {"year": 2025, "era_description": "当代中国人工智能创业环境"},
            "world": {"world_description": "深圳 AI 创业公司融资与产品交付压力并存"},
            "relationships": {
                "key_people": [
                    {
                        "name": "王思远",
                        "role": "合伙人",
                        "relationship": "赵谦（玩家角色）的大学同学和创业搭档",
                    }
                ]
            },
            "traits": {"traits_description": "赵谦是一位谨慎但愿意承担风险的 AI 创业者"},
            "wealth": {"currency": "¥", "currency_name": "元"},
        }

        story_prompt = get_story_only_prompt(
            player_state=player_state,
            language="zh",
            character_settings=character_settings,
        )
        round_prompt = get_round_event_prompt(
            player_state=player_state,
            language="zh",
            round_number=0,
            round_context="",
            character_settings=character_settings,
        )

        for prompt in (story_prompt, round_prompt):
            assert "主角名称是：赵谦" in prompt
            assert "主角名称是：心跳测试0737" not in prompt

    def test_round_story_fallback_uses_marked_player_role_name(self):
        """模型失败走兜底故事时，也必须使用角色设定里的玩家角色名。"""
        player_state = {
            "player_name": "心跳测试0737",
            "age": 28,
            "week": 3,
            "current_round": 0,
        }
        character_settings = {
            "relationships": {
                "key_people": [
                    {
                        "name": "王思远",
                        "relationship": "赵谦（玩家角色）的大学同学和创业搭档",
                    }
                ]
            },
            "traits": {"traits_description": "赵谦是一位谨慎但愿意承担风险的 AI 创业者"},
        }

        fallback_story = StoryGenerator._build_round_story_fallback(
            player_state=player_state,
            character_settings=character_settings,
            language="zh",
            round_number=0,
        )

        assert "赵谦没有遇到突发的巨大转折" in fallback_story
        assert "心跳测试0737" not in fallback_story

    def test_world_model_uses_marked_player_role_name_for_protagonist_records(self):
        """世界模型从字典状态构建时，也不应把测试会话名当作主角职业记录名。"""
        player_state = {
            "player_name": "心跳测试0737",
            "week": 3,
            "character_settings": {
                "relationships": {
                    "key_people": [
                        {
                            "name": "王思远",
                            "relationship": "赵谦（玩家角色）的大学同学和创业搭档",
                        }
                    ]
                },
                "occupation": {
                    "occupation": "AI 创业者",
                    "employer": "星链智能",
                    "level": "lead",
                },
            },
        }

        world_model = StoryGenerator._build_world_model_from_state_dict(player_state)

        assert world_model is not None
        assert "赵谦" in world_model.career_records
        assert "心跳测试0737" not in world_model.career_records

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

    # ── 默认现代标题 contract tests ──

    def test_story_only_prompt_without_settings_uses_modern_timeline_first_round(self):
        """无 character_settings 时默认现代青年，不应回退到古风“第一回”标题。"""
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
        assert "第1周·周一" in prompt, f"prompt 必须包含现代时间线标题。prompt 前800字: {prompt[:800]}"
        assert "第一回" not in prompt
        assert "7字对仗标题" not in prompt

    def test_story_only_prompt_has_chapter_constraint_text(self):
        """get_story_only_prompt 必须包含章节定位文本"""
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

    def test_story_only_prompt_without_settings_uses_modern_timeline_week2_round0(self):
        """无 character_settings 时 week=2,current_round=0 应使用第3周·周一，不应使用第七回。"""
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
        assert "第3周·周一" in prompt, f"prompt 必须包含现代时间线标题。prompt 前800字: {prompt[:800]}"
        assert "第七回" not in prompt
        assert "7字对仗标题" not in prompt

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
            "之前没有任何情节" in prompt and "禁止提及" in prompt
        ), f"第一章prompt必须禁止提及前情内容。prompt前800字: {prompt[:800]}"

    def test_round_event_prompt_without_settings_uses_modern_timeline_first_round(self):
        """get_round_event_prompt 无 character_settings 时 week=0,round=0 应使用第1周·周一。"""
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
        assert "第1周·周一" in prompt, f"round_event_prompt 必须包含现代时间线标题。prompt前800字: {prompt[:800]}"
        assert "第一回" not in prompt
        assert "7字对仗标题" not in prompt

    def test_round_event_prompt_without_settings_uses_modern_timeline_week2_round0(self):
        """get_round_event_prompt 无 character_settings 时 week=2,round=0 应使用第3周·周一。"""
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
        assert "第3周·周一" in prompt, f"round_event_prompt 必须包含现代时间线标题。prompt前800字: {prompt[:800]}"
        assert "第七回" not in prompt
        assert "7字对仗标题" not in prompt

    def test_round_event_prompt_has_chapter_constraint_block(self):
        """get_round_event_prompt 必须包含时间线/章节定位区块"""
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
            "时间线标题约束" in prompt
        ), f"round_event_prompt 必须包含现代时间线约束区块。prompt前800字: {prompt[:800]}"
        assert "本段故事是整体叙事的" in prompt, "必须包含章节定位说明"
