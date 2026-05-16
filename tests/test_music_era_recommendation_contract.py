"""音乐推荐时代匹配契约测试。

验证音乐推荐系统能正确接收和使用角色设定中的时代信息，
确保古代故事不会匹配到现代流行歌曲。
"""

import inspect
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


class TestMusicRecommendationRequestContract:
    """MusicRecommendationRequest 模型契约。"""

    def test_request_model_has_character_settings_field(self):
        """推荐请求模型必须包含 character_settings 字段。"""
        from src.api.routers.music import MusicRecommendationRequest

        fields = MusicRecommendationRequest.model_fields
        assert "character_settings" in fields, (
            "MusicRecommendationRequest 缺少 character_settings 字段，"
            "导致前端无法传递时代背景信息"
        )

    def test_character_settings_is_optional(self):
        """character_settings 应为 Optional[dict]，向后兼容。"""
        from src.api.routers.music import MusicRecommendationRequest

        # 无 character_settings 时应能正常实例化
        req = MusicRecommendationRequest(story_text="测试故事")
        assert req.character_settings is None

    def test_character_settings_accepts_dict(self):
        """character_settings 应接受包含 era 信息的字典。"""
        from src.api.routers.music import MusicRecommendationRequest

        settings = {"era": {"era_name": "明朝", "era_description": "永乐三年，大明盛世"}}
        req = MusicRecommendationRequest(story_text="测试故事", character_settings=settings)
        assert req.character_settings == settings


class TestAnalyzeStorySignatureContract:
    """analyze_story_for_music 接口签名契约。"""

    def test_analyze_story_accepts_character_settings(self):
        """analyze_story_for_music 必须接受 character_settings 参数。"""
        from src.services.music_service import MusicService

        sig = inspect.signature(MusicService.analyze_story_for_music)
        params = list(sig.parameters.keys())
        assert (
            "character_settings" in params
        ), "MusicService.analyze_story_for_music() 缺少 character_settings 参数"

    def test_analyze_story_accepts_refresh_flag_from_router(self):
        """音乐推荐刷新请求不得因 service 签名漂移返回 500。"""
        from src.services.music_service import MusicService

        sig = inspect.signature(MusicService.analyze_story_for_music)
        params = list(sig.parameters.keys())
        assert "refresh" in params, "MusicService.analyze_story_for_music() 缺少 refresh 参数"


class TestBuildSearchKeywordsEraAwareness:
    """_build_search_keywords 时代感知契约。"""

    def _get_build_search_keywords_func(self):
        """获取 _build_search_keywords 函数。"""
        from src.services.music_service import MusicService

        service = MusicService.__new__(MusicService)
        return service._build_search_keywords

    def test_ancient_era_produces_chinese_style_keywords(self):
        """古代时代设定应产生古风/中国风相关搜索关键词。"""
        build_keywords = self._get_build_search_keywords_func()

        # 模拟 AI 分析结果，包含古代时代信息
        analysis = {
            "mood": "忧伤",
            "energy": "低",
            "keywords": ["月夜", "思念"],
            "music_style": "抒情",
            "environment": "古风",
            "instruments": ["古琴"],
            "story_style": "古代",
        }
        character_settings = {"era": {"era_name": "明朝", "era_description": "永乐三年，汴州码头"}}

        keywords = build_keywords(analysis, character_settings=character_settings)

        # 验证包含至少一个古代风格关键词
        ancient_keywords = {"古风", "中国风", "古典", "民乐", "传统", "古琴", "国风"}
        found = set(keywords) & ancient_keywords
        assert found, f"古代时代设定未产生古风关键词。" f"实际关键词: {keywords}"

    def test_ancient_era_keywords_in_top_positions(self):
        """古代时代关键词应在搜索列表的前部（高优先级）。"""
        build_keywords = self._get_build_search_keywords_func()

        analysis = {
            "mood": "紧张",
            "energy": "高",
            "keywords": ["战场", "烽火"],
            "music_style": "史诗",
            "environment": "古风",
            "instruments": ["鼓", "琵琶"],
            "story_style": "武侠",
        }
        character_settings = {"era": {"era_name": "唐朝", "era_description": "安史之乱，烽火连天"}}

        keywords = build_keywords(analysis, character_settings=character_settings)

        # 前 3 个关键词中至少有 1 个是时代相关
        ancient_keywords = {
            "古风",
            "中国风",
            "古典",
            "民乐",
            "传统",
            "国风",
            "武侠",
            "古琴",
            "琵琶",
        }
        top_3 = set(keywords[:3])
        found_in_top = top_3 & ancient_keywords
        assert found_in_top, f"古代关键词未出现在搜索列表前 3 位。" f"前 3 个关键词: {keywords[:3]}"

    def test_modern_era_does_not_add_ancient_keywords(self):
        """现代时代设定不应添加古风关键词。"""
        build_keywords = self._get_build_search_keywords_func()

        analysis = {
            "mood": "愉快",
            "energy": "高",
            "keywords": ["都市", "霓虹"],
            "music_style": "流行",
            "environment": "现代",
            "instruments": ["吉他", "钢琴"],
            "story_style": "都市",
        }
        character_settings = {"era": {"era_name": "现代", "era_description": "2024年，上海陆家嘴"}}

        keywords = build_keywords(analysis, character_settings=character_settings)

        # 现代场景不应以古风关键词为主
        ancient_only = {"古风", "古典", "民乐", "传统", "古琴"}
        top_3 = set(keywords[:3])
        assert not (top_3 <= ancient_only), f"现代时代不应全部使用古代关键词。前 3: {keywords[:3]}"
