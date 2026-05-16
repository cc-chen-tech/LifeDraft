"""Tests for StyleManager - 场景风格管理器测试

测试颜色调板和视觉风格约束，确保多场景之间的视觉一致性。
"""

from src.services.image.style_manager import (ColorPalette, MoodType,
                                              SceneStyleManager, style_manager)


class TestMoodType:
    """情感基调类型测试"""

    def test_mood_type_values(self):
        """测试所有情感基调值"""
        assert MoodType.WARM_DAILY.value == "warm_daily"
        assert MoodType.TENSE_CONFLICT.value == "tense_conflict"
        assert MoodType.ROMANTIC.value == "romantic"
        assert MoodType.MYSTERIOUS.value == "mysterious"
        assert MoodType.JOYFUL.value == "joyful"
        assert MoodType.MELANCHOLY.value == "melancholy"
        assert MoodType.EPIC.value == "epic"
        assert MoodType.HORROR.value == "horror"

    def test_mood_type_count(self):
        """测试情感基调数量"""
        assert len(MoodType) == 8


class TestColorPalette:
    """颜色调板测试"""

    def test_create_palette(self):
        """测试创建调板"""
        palette = ColorPalette(
            name="测试调板",
            description="用于测试的调板",
            primary_colors=["红色", "蓝色"],
            secondary_colors=["白色", "灰色"],
            lighting="柔和光线",
            saturation="高",
            contrast="中",
            atmosphere="测试氛围",
        )

        assert palette.name == "测试调板"
        assert len(palette.primary_colors) == 2
        assert len(palette.secondary_colors) == 2

    def test_build_prompt_segment_full(self):
        """测试构建完整提示词片段"""
        palette = ColorPalette(
            name="温馨日常",
            description="适合日常生活",
            primary_colors=["米黄色", "橙棕色"],
            secondary_colors=["浅木色", "米色"],
            lighting="柔和的自然光",
            saturation="适中",
            contrast="低到中",
            atmosphere="温馨、舒适",
        )

        prompt = palette.build_prompt_segment()

        # 验证主色调
        assert "米黄色" in prompt
        assert "橙棕色" in prompt

        # 验证辅助色
        assert "浅木色" in prompt
        assert "米色" in prompt

        # 验证其他属性
        assert "柔和的自然光" in prompt
        assert "适中" in prompt
        assert "低到中" in prompt
        assert "温馨、舒适" in prompt

    def test_build_prompt_segment_no_secondary(self):
        """测试无辅助色的提示词片段"""
        palette = ColorPalette(
            name="简约调板",
            description="简约风格",
            primary_colors=["白色"],
            secondary_colors=[],
            lighting="明亮光线",
            saturation="低",
            contrast="高",
            atmosphere="简洁",
        )

        prompt = palette.build_prompt_segment()

        assert "白色" in prompt
        assert "明亮光线" in prompt
        # 不应包含辅助色相关文本
        assert "辅以" not in prompt


class TestSceneStyleManager:
    """场景风格管理器测试"""

    def test_init(self):
        """测试初始化"""
        manager = SceneStyleManager()

        assert isinstance(manager._game_palettes, dict)
        assert isinstance(manager._style_reference_urls, dict)

    def test_get_palette_valid(self):
        """测试获取有效调板"""
        manager = SceneStyleManager()

        palette = manager.get_palette(MoodType.WARM_DAILY)

        assert palette.name == "温馨日常"
        assert "米黄色" in palette.primary_colors

    def test_get_palette_invalid(self):
        """测试获取无效调板时返回默认值"""
        manager = SceneStyleManager()

        # 使用不存在的mood，应返回默认调板
        palette = manager.get_palette(None)

        # 默认返回温馨日常
        assert palette.name == "温馨日常"

    def test_detect_mood_from_story_tense_conflict(self):
        """测试检测紧张冲突基调"""
        manager = SceneStyleManager()

        story = "两人发生了激烈的争吵，场面十分紧张，充满了对抗"
        mood = manager.detect_mood_from_story(story)

        assert mood == MoodType.TENSE_CONFLICT

    def test_detect_mood_from_story_romantic(self):
        """测试检测浪漫基调"""
        manager = SceneStyleManager()

        story = "他们在浪漫的月光下约会，心动的感觉让人甜蜜"
        mood = manager.detect_mood_from_story(story)

        assert mood == MoodType.ROMANTIC

    def test_detect_mood_from_story_mysterious(self):
        """测试检测神秘基调"""
        manager = SceneStyleManager()

        story = "一个神秘的夜晚，充满了未知和悬疑，诡异的谜题"
        mood = manager.detect_mood_from_story(story)

        assert mood == MoodType.MYSTERIOUS

    def test_detect_mood_from_story_joyful(self):
        """测试检测欢快基调"""
        manager = SceneStyleManager()

        story = "大家开心地庆祝胜利，派对上充满了欢乐和喜悦"
        mood = manager.detect_mood_from_story(story)

        assert mood == MoodType.JOYFUL

    def test_detect_mood_from_story_melancholy(self):
        """测试检测忧郁基调"""
        manager = SceneStyleManager()

        story = "离别让人感到悲伤和失落，惆怅中带着怀念"
        mood = manager.detect_mood_from_story(story)

        assert mood == MoodType.MELANCHOLY

    def test_detect_mood_from_story_horror(self):
        """测试检测恐怖基调"""
        manager = SceneStyleManager()

        story = "恐怖的夜晚，让人感到害怕和恐惧，仿佛有鬼魂"
        mood = manager.detect_mood_from_story(story)

        assert mood == MoodType.HORROR

    def test_detect_mood_from_story_epic(self):
        """测试检测史诗基调"""
        manager = SceneStyleManager()

        story = "这是一场宏大的决战，英雄书写着伟大的传说"
        mood = manager.detect_mood_from_story(story)

        assert mood == MoodType.EPIC

    def test_detect_mood_default(self):
        """测试默认基调检测"""
        manager = SceneStyleManager()

        story = "这是一个普通的日常故事，没有什么特别的情绪"
        mood = manager.detect_mood_from_story(story)

        # 默认返回温馨日常
        assert mood == MoodType.WARM_DAILY

    def test_detect_mood_multiple_keywords(self):
        """测试多个关键词匹配"""
        manager = SceneStyleManager()

        # 同时包含浪漫和紧张关键词，但浪漫关键词更多
        story = "这是一个浪漫的约会，但也有些紧张的气氛，表白时心动又害怕"
        mood = manager.detect_mood_from_story(story)

        # 根据关键词数量判断
        assert mood in [MoodType.ROMANTIC, MoodType.TENSE_CONFLICT]

    def test_set_game_palette(self):
        """测试设置游戏调板"""
        manager = SceneStyleManager()

        manager.set_game_palette(1, MoodType.ROMANTIC)

        assert 1 in manager._game_palettes
        assert manager._game_palettes[1] == MoodType.ROMANTIC

    def test_get_game_palette_set(self):
        """测试获取已设置的游戏调板"""
        manager = SceneStyleManager()
        manager.set_game_palette(1, MoodType.MYSTERIOUS)

        palette = manager.get_game_palette(1)

        assert palette.name == "神秘"

    def test_get_game_palette_default(self):
        """测试获取未设置的游戏调板"""
        manager = SceneStyleManager()

        palette = manager.get_game_palette(999)

        # 默认返回温馨日常
        assert palette.name == "温馨日常"

    def test_set_style_reference(self):
        """测试设置风格参考图"""
        manager = SceneStyleManager()

        manager.set_style_reference(1, "https://example.com/style.png")

        assert manager._style_reference_urls[1] == "https://example.com/style.png"

    def test_get_style_reference(self):
        """测试获取风格参考图"""
        manager = SceneStyleManager()
        manager.set_style_reference(1, "https://example.com/style.png")

        url = manager.get_style_reference(1)

        assert url == "https://example.com/style.png"

    def test_get_style_reference_not_set(self):
        """测试获取未设置的风格参考图"""
        manager = SceneStyleManager()

        url = manager.get_style_reference(999)

        assert url is None

    def test_build_scene_prompt_with_style(self):
        """测试构建带风格的场景提示词"""
        manager = SceneStyleManager()

        prompt = manager.build_scene_prompt_with_style(
            scene_desc="主角在公园散步",
            era="现代",
            mood=MoodType.JOYFUL,
        )

        assert "电影感故事场景插画" in prompt
        assert "公园散步" in prompt
        assert "现代" in prompt
        assert "明黄色" in prompt or "天蓝色" in prompt  # 欢快调板的颜色

    def test_build_scene_prompt_with_game_id(self):
        """测试使用game_id构建提示词"""
        manager = SceneStyleManager()
        manager.set_game_palette(1, MoodType.EPIC)

        prompt = manager.build_scene_prompt_with_style(
            scene_desc="决战时刻",
            era="古代",
            game_id=1,
        )

        assert "决战时刻" in prompt
        assert "金色" in prompt or "深红色" in prompt  # 史诗调板的颜色

    def test_apply_temporal_progression_early(self):
        """测试早期时序色彩变化（春）"""
        manager = SceneStyleManager()

        palette = manager.apply_temporal_progression(1, week=5, total_weeks=52)

        assert "第5周" in palette.name
        assert "早春" in palette.atmosphere or "嫩绿" in palette.atmosphere

    def test_apply_temporal_progression_summer(self):
        """测试夏季时序色彩变化"""
        manager = SceneStyleManager()

        palette = manager.apply_temporal_progression(1, week=20, total_weeks=52)

        assert "第20周" in palette.name
        assert "盛夏" in palette.atmosphere or "阳光" in palette.atmosphere

    def test_apply_temporal_progression_autumn(self):
        """测试秋季时序色彩变化"""
        manager = SceneStyleManager()

        palette = manager.apply_temporal_progression(1, week=35, total_weeks=52)

        assert "第35周" in palette.name
        assert "深秋" in palette.atmosphere or "金黄" in palette.atmosphere

    def test_apply_temporal_progression_winter(self):
        """测试冬季时序色彩变化"""
        manager = SceneStyleManager()

        palette = manager.apply_temporal_progression(1, week=45, total_weeks=52)

        assert "第45周" in palette.name
        assert "初冬" in palette.atmosphere or "寒意" in palette.atmosphere

    def test_apply_temporal_progression_boundary(self):
        """测试时序边界"""
        manager = SceneStyleManager()

        # 刚好25%
        palette = manager.apply_temporal_progression(1, week=13, total_weeks=52)
        assert "第13周" in palette.name

        # 刚好50%
        palette = manager.apply_temporal_progression(1, week=26, total_weeks=52)
        assert "第26周" in palette.name

        # 刚好75%
        palette = manager.apply_temporal_progression(1, week=39, total_weeks=52)
        assert "第39周" in palette.name


class TestStyleManagerIntegration:
    """风格管理器集成测试"""

    def test_full_workflow(self):
        """测试完整工作流"""
        manager = SceneStyleManager()

        # 1. 从故事检测情感
        story = "这是一个神秘的故事，充满了未知"
        mood = manager.detect_mood_from_story(story)
        assert mood == MoodType.MYSTERIOUS

        # 2. 为游戏设置调板
        manager.set_game_palette(game_id=1, mood=mood)

        # 3. 获取游戏调板
        palette = manager.get_game_palette(1)
        assert palette.name == "神秘"

        # 4. 构建场景提示词
        prompt = manager.build_scene_prompt_with_style(
            scene_desc="主角探索古宅",
            era="现代",
            game_id=1,
        )

        assert "探索古宅" in prompt
        assert "青蓝色" in prompt or "深紫色" in prompt

        # 5. 应用时序变化
        temporal_palette = manager.apply_temporal_progression(game_id=1, week=10, total_weeks=52)
        assert "第10周" in temporal_palette.name


class TestGlobalStyleManager:
    """全局风格管理器实例测试"""

    def test_global_instance_exists(self):
        """测试全局实例存在"""
        assert isinstance(style_manager, SceneStyleManager)

    def test_global_instance_has_palettes(self):
        """测试全局实例包含预定义调板"""
        assert len(style_manager.PALETTES) == 8

    def test_global_instance_palette_access(self):
        """测试全局实例调板访问"""
        palette = style_manager.get_palette(MoodType.WARM_DAILY)

        assert palette.name == "温馨日常"
        assert "米黄色" in palette.primary_colors
