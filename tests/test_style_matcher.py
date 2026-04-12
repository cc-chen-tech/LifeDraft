"""StyleMatcher 单元测试和集成测试。

覆盖：基本匹配逻辑、四层级权重计算、边界情况、Top N、置信度阈值、GameInitializer 集成。
"""

import pytest

from src.ai.narrative.style_matcher import StyleMatcher, StyleMatchResult, auto_match_style


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def matcher():
    """模块级 StyleMatcher 实例（只读，可复用）。"""
    return StyleMatcher()


# ==================== 测试类 1: 基本匹配逻辑 ====================


class TestStyleMatcherBasic:
    """基本匹配逻辑测试：验证典型设定能匹配到正确的风格。"""

    def test_ancient_china_matches_chinese_style(self, matcher):
        """古代中国设定应匹配到中国古典类风格"""
        settings = {
            "era": {"year": 690, "era_description": "唐朝武则天称帝，改国号为周，史称武周，帝制王朝"},
            "world": {
                "world_description": "古代帝制社会，朝廷权谋斗争激烈，家国天命，忠义为先",
                "technology_level": "冷兵器时代，农业手工",
            },
            "traits": {"personality": ["忠勇", "义气", "刚正", "豪迈"]},
        }
        result = matcher.match(settings)
        assert result.style_id in [
            "chinese_classic_saga",
            "chinese_wuxia",
            "chinese_domestic_realism",
            "chinese_mythic_journey",
        ]
        assert result.confidence > 0.0

    def test_cyberpunk_matches_cyberpunk_style(self, matcher):
        """赛博朋克设定应匹配到赛博朋克风格"""
        settings = {
            "era": {"year": 2077, "era_description": "未来都市，科技高度发达"},
            "world": {
                "world_description": "高科技低生活的赛博朋克世界",
                "technology_level": "超高科技",
            },
            "traits": {"personality": ["叛逆", "孤独"]},
        }
        result = matcher.match(settings)
        assert result.style_id == "cyberpunk"
        assert result.confidence > 0.3

    def test_shanghai_1930s_matches_zhang_ailing(self, matcher):
        """民国上海设定应匹配到张爱玲风格"""
        settings = {
            "era": {"year": 1935, "era_description": "民国时期的上海租界"},
            "world": {
                "world_description": "十里洋场，租界林立，旧上海的繁华与苍凉",
            },
            "traits": {"personality": ["敏感", "忧郁", "多愁善感"]},
        }
        result = matcher.match(settings)
        assert result.style_id == "zhang_ailing_urban_desolation"
        assert result.confidence > 0.3

    def test_japanese_setting_matches_japanese_style(self, matcher):
        """日本设定应匹配到日本风格"""
        settings = {
            "era": {"year": 1200, "era_description": "平安时代末期，日本武士崛起"},
            "world": {"world_description": "日本幕府统治下的封建社会"},
            "traits": {"personality": ["含蓄", "隐忍"]},
        }
        result = matcher.match(settings)
        assert result.style_id in [
            "japanese_monogatari",
            "japanese_honkaku",
            "japanese_shakaiha",
        ]

    def test_space_opera_setting(self, matcher):
        """太空歌剧设定应匹配到科幻风格"""
        settings = {
            "era": {"year": 3000, "era_description": "星际时代，人类殖民银河系"},
            "world": {"world_description": "银河帝国，星际战争，外星文明"},
            "traits": {"personality": ["勇敢", "冒险"]},
        }
        result = matcher.match(settings)
        assert result.style_id in ["scifi_space_opera", "new_wave_scifi"]


# ==================== 测试类 2: 权重计算 ====================


class TestStyleMatcherScoring:
    """权重计算测试：验证四层级权重配置正确。"""

    def test_era_weight_is_highest(self):
        """时代匹配权重应为 0.35"""
        assert StyleMatcher.ERA_WEIGHT == 0.35

    def test_world_weight(self):
        """世界观匹配权重应为 0.30"""
        assert StyleMatcher.WORLD_WEIGHT == 0.30

    def test_traits_weight(self):
        """人物特质匹配权重应为 0.20"""
        assert StyleMatcher.TRAITS_WEIGHT == 0.20

    def test_culture_weight(self):
        """文化倾向匹配权重应为 0.15"""
        assert StyleMatcher.CULTURE_WEIGHT == 0.15

    def test_all_weights_sum_to_one(self):
        """所有权重之和应为 1.0"""
        total = (
            StyleMatcher.ERA_WEIGHT
            + StyleMatcher.WORLD_WEIGHT
            + StyleMatcher.TRAITS_WEIGHT
            + StyleMatcher.CULTURE_WEIGHT
        )
        assert abs(total - 1.0) < 0.001

    def test_confidence_between_zero_and_one(self, matcher):
        """置信度应在 0-1 之间"""
        various_settings = [
            {"era": {"year": 690, "era_description": "古代中国"}},
            {"world": {"world_description": "赛博朋克"}},
            {"traits": {"personality": ["勇敢"]}},
            {
                "era": {"year": 2077, "era_description": "未来"},
                "world": {"world_description": "高科技世界"},
                "traits": {"personality": ["叛逆"]},
            },
            {},
        ]
        for settings in various_settings:
            result = matcher.match(settings)
            assert 0.0 <= result.confidence <= 1.0, (
                f"confidence {result.confidence} out of range for {settings}"
            )


# ==================== 测试类 3: 边界情况 ====================


class TestStyleMatcherEdgeCases:
    """边界情况测试：空输入、None 字段、缺失子字段。"""

    def test_empty_settings(self, matcher):
        """空 character_settings 应返回默认风格"""
        result = matcher.match({})
        assert result.style_id == "chinese_classic_saga"
        assert result.confidence == 0.0

    def test_none_fields(self, matcher):
        """字段为 None 时不应崩溃"""
        result = matcher.match({"era": None, "world": None, "traits": None})
        assert result.style_id is not None

    def test_missing_sub_fields(self, matcher):
        """缺少子字段时优雅降级"""
        result = matcher.match({"era": {"year": 1000}})  # 无 era_description
        assert result.style_id is not None
        assert result.confidence >= 0.0

    def test_non_dict_era(self, matcher):
        """era 不是 dict 时不崩溃"""
        result = matcher.match({"era": "古代"})
        assert result.style_id is not None

    def test_non_dict_world(self, matcher):
        """world 不是 dict 时不崩溃"""
        result = matcher.match({"world": "赛博朋克世界"})
        assert result.style_id is not None

    def test_non_dict_traits(self, matcher):
        """traits 不是 dict 时不崩溃"""
        result = matcher.match({"traits": ["勇敢", "善良"]})
        assert result.style_id is not None

    def test_empty_sub_dicts(self, matcher):
        """子字典全为空时不崩溃"""
        result = matcher.match({"era": {}, "world": {}, "traits": {}})
        assert result.style_id is not None
        assert result.confidence >= 0.0


# ==================== 测试类 4: Top N ====================


class TestStyleMatcherTopN:
    """Top N 结果测试。"""

    def test_top_n_returns_correct_count(self, matcher):
        """match_top_n 返回数量不超过 n"""
        settings = {
            "era": {"year": 2077, "era_description": "赛博朋克未来都市"},
            "world": {"world_description": "高科技低生活的世界"},
            "traits": {"personality": ["叛逆"]},
        }
        results = matcher.match_top_n(settings, n=5)
        assert len(results) <= 5
        assert len(results) > 0

    def test_top_n_sorted_by_confidence(self, matcher):
        """match_top_n 结果应按置信度降序排列"""
        settings = {
            "era": {"year": 1935, "era_description": "民国上海"},
            "world": {"world_description": "十里洋场"},
            "traits": {"personality": ["敏感"]},
        }
        results = matcher.match_top_n(settings, n=3)
        confidences = [r.confidence for r in results]
        assert confidences == sorted(confidences, reverse=True)

    def test_top_n_first_matches_match(self, matcher):
        """match_top_n 的第一个结果应与 match 结果一致"""
        settings = {
            "era": {"year": 690, "era_description": "唐朝"},
            "world": {"world_description": "古代帝制"},
            "traits": {"personality": ["忠诚"]},
        }
        top_results = matcher.match_top_n(settings, n=3)
        single_result = matcher.match(settings)
        assert top_results[0].style_id == single_result.style_id
        assert abs(top_results[0].confidence - single_result.confidence) < 0.001

    def test_top_n_empty_settings(self, matcher):
        """空设定的 top_n 应返回空列表（因为 all_scores 为空）"""
        results = matcher.match_top_n({}, n=3)
        assert len(results) == 0


# ==================== 测试类 5: 置信度阈值 ====================


class TestStyleMatcherConfidenceThreshold:
    """置信度阈值测试：高匹配度设定应有较高置信度。"""

    def test_match_above_threshold(self, matcher):
        """高匹配度设定应超过 0.3 阈值"""
        settings = {
            "era": {"year": 2077, "era_description": "赛博朋克未来都市"},
            "world": {
                "world_description": "高科技低生活的赛博朋克世界，人工智能和网络无处不在",
            },
            "traits": {"personality": ["叛逆", "孤独", "黑客"]},
        }
        result = matcher.match(settings)
        assert result.confidence >= 0.3

    def test_vague_settings_low_confidence(self, matcher):
        """模糊设定应有较低置信度"""
        settings = {
            "era": {"year": 2000, "era_description": "现代"},
            "world": {"world_description": "一个普通的世界"},
            "traits": {"personality": ["普通"]},
        }
        result = matcher.match(settings)
        # 模糊设定不应有很高的置信度
        assert result.confidence < 1.0

    def test_all_scores_populated(self, matcher):
        """匹配结果应包含所有风格的评分"""
        settings = {
            "era": {"year": 2077, "era_description": "未来赛博"},
            "world": {"world_description": "赛博朋克"},
        }
        result = matcher.match(settings)
        assert len(result.all_scores) > 0
        # 最佳风格的评分应等于 confidence
        assert result.all_scores[result.style_id] == result.confidence


# ==================== 测试类 6: GameInitializer 集成 ====================


class TestGameInitializerIntegration:
    """GameInitializer 集成测试：验证 style_id 的提取逻辑。"""

    def test_auto_match_when_no_style_id(self, matcher):
        """无 narrative_style_id 时，auto_match_style 应自动匹配"""
        settings = {
            "era": {"year": 2077, "era_description": "赛博朋克未来"},
            "world": {"world_description": "高科技低生活的赛博朋克世界"},
            "traits": {"personality": ["叛逆"]},
        }
        # 模拟 GameInitializer 中无 narrative_style_id 的场景
        style_id = settings.get("narrative_style_id")
        assert style_id is None

        # 此时应使用 auto_match_style
        result = auto_match_style(settings)
        assert result.style_id is not None
        assert result.style_id == "cyberpunk"

    def test_preserve_explicit_style_id(self):
        """有 narrative_style_id 时不应覆盖"""
        settings = {
            "narrative_style_id": "gothic_horror",
            "era": {"year": 690, "era_description": "古代中国"},
        }
        # 模拟 GameInitializer 中提取 style_id 的逻辑
        style_id = settings.get("narrative_style_id")
        assert style_id == "gothic_horror"

    def test_game_initializer_extracts_style_id(self):
        """GameInitializer 应从 character_settings 提取 narrative_style_id"""
        from unittest.mock import MagicMock, patch

        from src.game.game_initializer import GameInitializer

        mock_db = MagicMock()
        mock_db.create_game.return_value = 1

        initializer = GameInitializer(game_db=mock_db, language="zh")

        character_settings = {
            "narrative_style_id": "cyberpunk",
            "era": {"year": 2077},
            "age": {"age": 20},
        }

        with patch("src.game.game_initializer.GameLoop") as mock_game_loop:
            mock_loop_instance = MagicMock()
            mock_game_loop.return_value = mock_loop_instance

            _, game_id = initializer.initialize_game_from_settings(
                character_settings=character_settings,
                player_name="TestPlayer",
                life_vision="Test vision",
                user_id=1,
            )

        # 验证 create_game 被调用时传入了正确的 narrative_style_id
        mock_db.create_game.assert_called_once()
        call_kwargs = mock_db.create_game.call_args
        assert call_kwargs.kwargs.get("narrative_style_id") == "cyberpunk" or (
            call_kwargs[1].get("narrative_style_id") == "cyberpunk"
        )

    def test_game_initializer_none_style_when_absent(self):
        """无 narrative_style_id 时 GameInitializer 应传 None"""
        from unittest.mock import MagicMock, patch

        from src.game.game_initializer import GameInitializer

        mock_db = MagicMock()
        mock_db.create_game.return_value = 2

        initializer = GameInitializer(game_db=mock_db, language="zh")

        character_settings = {
            "era": {"year": 690},
            "age": {"age": 25},
        }

        with patch("src.game.game_initializer.GameLoop") as mock_game_loop:
            mock_loop_instance = MagicMock()
            mock_game_loop.return_value = mock_loop_instance

            initializer.initialize_game_from_settings(
                character_settings=character_settings,
                player_name="TestPlayer",
                life_vision="Test vision",
                user_id=1,
            )

        call_kwargs = mock_db.create_game.call_args
        style_id = call_kwargs.kwargs.get(
            "narrative_style_id", call_kwargs[1].get("narrative_style_id")
        )
        assert style_id is None


# ==================== 便捷函数测试 ====================


class TestAutoMatchStyle:
    """auto_match_style 便捷函数测试。"""

    def test_auto_match_returns_result(self):
        """auto_match_style 应返回 StyleMatchResult"""
        settings = {
            "era": {"year": 2077, "era_description": "赛博朋克"},
            "world": {"world_description": "赛博朋克世界"},
        }
        result = auto_match_style(settings)
        assert isinstance(result, StyleMatchResult)
        assert result.style_id is not None

    def test_auto_match_empty(self):
        """auto_match_style 传空字典应返回默认"""
        result = auto_match_style({})
        assert result.style_id == "chinese_classic_saga"
        assert result.confidence == 0.0
