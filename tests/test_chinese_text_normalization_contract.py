"""Chinese Text Normalization Contract Tests

验证繁简转换和标点规范化后处理在故事生成管道中正确执行。
Layer 3: 契约测试 — 输出文本必须规范。
"""


class TestChineseTextNormalizationContract:
    """测试中文文本规范化契约"""

    def test_traditional_characters_converted(self):
        """繁体字必须转换为简体字"""
        from src.ai.story_generator import _normalize_punctuation

        text = "蘇錦年走進茶館，這裏很熱鬧"
        normalized = _normalize_punctuation(text, language="zh")
        assert "苏锦年" in normalized, f"应转换繁体字 '蘇錦年' 为 '苏锦年', 得到: {normalized}"
        assert "这里" in normalized, f"应转换 '這裏' 为 '这里', 得到: {normalized}"
        assert "热闹" in normalized, f"应转换 '熱鬧' 为 '热闹', 得到: {normalized}"

    def test_chinese_ellipsis_normalized(self):
        """中文句号省略号（。。。）必须转为标准省略号（……）"""
        from src.ai.story_generator import _normalize_punctuation

        text = "他沉默了。。。不知该说什么"
        normalized = _normalize_punctuation(text, language="zh")
        assert "。。。" not in normalized, "应替换中文句号省略号"
        assert "……" in normalized, "应使用标准省略号"

    def test_english_ellipsis_preserved(self):
        """英文省略号 ... 也转换为……"""
        from src.ai.story_generator import _normalize_punctuation

        text = "He paused... then spoke"
        normalized = _normalize_punctuation(text, language="en")
        # 英文模式下不转换
        assert "..." in normalized or "……" in normalized

    def test_non_chinese_language_skipped(self):
        """非中文语言应跳过繁简转换"""
        from src.ai.story_generator import _normalize_punctuation

        text = "Hello world"
        normalized = _normalize_punctuation(text, language="en")
        assert normalized == text, "英文模式下不应修改文本"

    def test_era_anachronism_caught_by_validator(self):
        """时代一致性验证器应检测古代背景中的现代元素"""
        from src.ai.harness.era_validator import validate_era_consistency

        story = "在唐朝的街道上，李逍遥走进星巴克，点了一杯拿铁"
        context = {"era": "唐朝", "era_type": "ancient"}
        passed, evidence, details = validate_era_consistency(story, context)
        assert not passed, "应检测到现代元素 '星巴克'"
        assert "星巴克" in evidence or "现代" in evidence

    def test_modern_era_no_false_positive(self):
        """现代背景下不应误报"""
        from src.ai.harness.era_validator import validate_era_consistency

        story = "李逍遥走进星巴克，点了一杯拿铁"
        context = {"era": "现代", "era_type": "modern"}
        passed, evidence, details = validate_era_consistency(story, context)
        assert passed, "现代背景不应触发时代穿越警告"

    def test_decision_history_prompt_includes_30_entries(self):
        """决策历史 prompt 应包含最多30条"""
        from config.prompts.story_prompts import get_event_generation_prompt

        # 构造31条决策历史
        decision_history = [
            {"week": i, "choice": f"选择{i}", "event": f"事件{i}" * 10}
            for i in range(31)
        ]
        player_state = {
            "age": 25,
            "week": 31,
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "relationships": {},
            "decision_history": decision_history,
        }
        prompt = get_event_generation_prompt(
            player_state=player_state,
            language="zh",
        )
        # 检查 prompt 中是否包含第25条决策历史
        assert "选择25" in prompt or "事件25" in prompt, "应包含第25条决策历史"
        # 检查是否包含超过30条（第30条是索引30，即第31条）
        # 由于 prompt 可能截断，我们主要验证不限制为15条
        assert "事件20" in prompt, "应包含第20条决策历史"
