"""Deep coverage tests for character_creation.py."""

import json
from unittest.mock import Mock

# ==================== assign_sexual_orientation Tests ====================


class TestAssignSexualOrientation:
    """Test the sexual orientation probability assignment."""

    def test_returns_valid_orientation(self):
        """Test function returns one of the valid values."""
        from src.game.character_creation import assign_sexual_orientation

        valid = {"heterosexual", "homosexual", "bisexual", "asexual"}
        for _ in range(50):
            result = assign_sexual_orientation()
            assert result in valid

    def test_distribution_mostly_heterosexual(self):
        """Test statistical distribution favors heterosexual."""
        from src.game.character_creation import assign_sexual_orientation

        results = [assign_sexual_orientation() for _ in range(1000)]
        hetero_count = results.count("heterosexual")
        assert hetero_count > 700  # 90% probability, expect 700+ in 1000


# ==================== CharacterCreator Tests ====================


class TestCharacterCreatorGenerateSetting:
    """Test CharacterCreator.generate_setting method."""

    def _make_creator(self, language="zh"):
        from src.game.character_creation import CharacterCreator

        mock_gen = Mock()
        mock_gen.generate_completion = Mock()
        mock_gen.generate_completion_json = Mock()
        return CharacterCreator(ai_generator=mock_gen, language=language)

    def test_generate_era_setting(self):
        """Test generating era setting."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = json.dumps(
            {"year": 2024, "era_description": "现代", "world_context": "现代社会"}
        )
        result = creator.generate_setting("era", "张三", "成功", {})
        assert result["year"] == 2024

    def test_generate_era_honors_explicit_modern_product_manager_life_vision(self):
        """明确现代互联网产品经理愿景不能被时代生成漂移成古代。"""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = json.dumps(
            {
                "year": 713,
                "era_description": "唐代长安，坊市繁华，科举与门第影响人生。",
                "world_context": "大唐盛世，士族与寒门并存。",
            },
            ensure_ascii=False,
        )

        result = creator.generate_setting(
            "era",
            "顾晨曦",
            "2020年代中国互联网公司，成为AI协作工具产品经理",
            {},
        )

        assert result["year"] >= 2020
        combined = f"{result.get('era_description', '')} {result.get('world_context', '')}"
        assert "唐" not in combined
        assert "互联网" in combined
        assert "产品经理" in combined or "产品" in combined

    def test_generate_era_honors_modern_shanghai_game_developer_life_vision(self):
        """现代上海游戏开发者愿景不能被时代生成漂移成北宋。"""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = json.dumps(
            {
                "year": 1100,
                "era_description": "1100年北宋中后期，文化艺术繁荣，理学兴起，市民经济活跃。",
                "world_context": "北宋王朝科举制度完善，文人地位崇高。",
            },
            ensure_ascii=False,
        )

        result = creator.generate_setting(
            "era",
            "许知夏",
            "现代上海，独立游戏开发者，女性，关注叙事设计和音乐创作，不要古代、不要穿越。",
            {},
        )

        assert result["year"] >= 2020
        combined = f"{result.get('era_description', '')} {result.get('world_context', '')}"
        assert "宋" not in combined
        assert "北宋" not in combined
        assert "科举" not in combined
        assert "现代" in combined
        assert "游戏" in combined or "叙事" in combined

    def test_generate_era_feedback_still_aligns_with_modern_life_vision(self):
        """有feedback重生成时也不能回退到古代时代。"""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = json.dumps(
            {
                "year": 713,
                "era_description": "唐代，长安城内，商业繁荣，科举与门第格局严谨。",
                "world_context": "古代官僚与礼法主导的社会。",
            },
            ensure_ascii=False,
        )

        result = creator.generate_setting(
            "era",
            "顾晨曦",
            "2020年代中国互联网公司，成为AI协作工具产品经理",
            {},
            feedback="不喜欢这个年代了，请重新生成。",
        )

        assert result["year"] >= 2020
        combined = f"{result.get('era_description', '')} {result.get('world_context', '')}"
        assert "唐" not in combined
        assert "科举" not in combined
        assert "古代" not in combined
        assert "互联网" in combined
        assert result.get("_aligned_to_life_vision") is True

    def test_generate_era_prefers_modern_on_classical_wording_conflict(self):
        """仅含“现代”语义时，仍可纠偏到现代时代。"""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = json.dumps(
            {
                "year": 700,
                "era_description": "秦汉以前，战车与田猎的边缘社会。",
                "world_context": "古代帝国官僚与城邦竞争。",
            },
            ensure_ascii=False,
        )

        result = creator.generate_setting(
            "era",
            "陈书言",
            "故事背景设定在现代",
            {},
        )

        assert result["year"] >= 2020
        combined = f"{result.get('era_description', '')} {result.get('world_context', '')}"
        assert "秦汉" not in combined
        assert "古代" not in combined
        assert "互联网" in combined or "现代" in combined
        assert result.get("_aligned_to_life_vision") is True

    def test_generate_era_prefers_historical_context_when_life_vision_forbids_modern(self):
        """明确反对现代元素时，时代应纠偏为古代语境。"""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = json.dumps(
            {
                "year": 2026,
                "era_description": "2026年前后数字基础设施发达，互联网与AI协作成为生产核心。",
                "world_context": "现代中国，企业化运营与高速更新。",
            },
            ensure_ascii=False,
        )

        result = creator.generate_setting(
            "era",
            "林清越",
            "成为一名坚持古典世界观的医者，避免现代科技和赛博朋克元素，关注家庭、师承与乡里关系。",
            {},
        )

        assert result["year"] < 1900
        combined = f"{result.get('era_description', '')} {result.get('world_context', '')}"
        assert "互联网" not in combined
        assert "AI" not in combined
        assert "公司" not in combined
        assert "现代" not in combined
        assert "古代" in combined or "古典" in combined
        assert result.get("_aligned_to_life_vision") is True

    def test_generate_age_setting_corrects_birth_year(self):
        """Test age setting auto-corrects birth_year."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = json.dumps(
            {"age": 25, "birth_year": 1990, "age_description": "青年"}
        )
        result = creator.generate_setting("age", "张三", "成功", {"era": {"year": 2024}})
        assert result["birth_year"] == 1999  # 2024 - 25

    def test_generate_wealth_setting_zero_retry(self):
        """Test wealth=0 triggers retry and eventually uses fallback."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = json.dumps(
            {"wealth": 0, "currency": "¥"}
        )
        result = creator.generate_setting("wealth", "张三", "成功", {})
        assert result["wealth"] >= 1000  # Either retried or fallback

    def test_generate_wealth_low_adjusted(self):
        """Test low wealth is adjusted to minimum."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = json.dumps(
            {"wealth": 500, "currency": "¥"}
        )
        result = creator.generate_setting("wealth", "张三", "成功", {})
        assert result["wealth"] >= 1000

    def test_generate_setting_ai_failure_fallback(self):
        """Test fallback when AI fails all retries."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.side_effect = Exception("API Error")
        result = creator.generate_setting("era", "张三", "成功", {})
        assert result["_is_fallback"] is True
        assert result["year"] == 2024

    def test_generate_setting_invalid_json_fallback(self):
        """Test fallback when AI returns invalid JSON."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = "not json at all"
        result = creator.generate_setting("traits", "张三", "成功", {})
        assert "_is_fallback" in result

    def test_family_setting_does_not_keep_placeholder_prefix_as_surname(self):
        """测试类占位名不应让家庭成员继承“测试”伪姓。"""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = json.dumps(
            {
                "family_description": "普通家庭",
                "family_members": [
                    {"name": "测试卫国", "role": "父亲", "relationship": "父亲"},
                    {"name": "测试秀兰", "role": "母亲", "relationship": "母亲"},
                ],
                "family_economy": "中等",
                "family_relationships": "互相关心",
            },
            ensure_ascii=False,
        )

        result = creator.generate_setting("family", "测试小可", "成为产品经理", {})

        names = [member["name"] for member in result["family_members"]]
        assert names == ["卫国", "秀兰"]

    def test_family_setting_preserves_real_chinese_surname(self):
        """真实中文姓氏可以被家庭成员继承。"""
        creator = self._make_creator()
        creator.ai_generator.generate_completion.return_value = json.dumps(
            {
                "family_description": "普通家庭",
                "family_members": [
                    {"name": "张卫国", "role": "父亲", "relationship": "父亲"},
                    {"name": "张秀兰", "role": "母亲", "relationship": "母亲"},
                ],
                "family_economy": "中等",
                "family_relationships": "互相关心",
            },
            ensure_ascii=False,
        )

        result = creator.generate_setting("family", "张三", "成为产品经理", {})

        names = [member["name"] for member in result["family_members"]]
        assert names == ["张卫国", "张秀兰"]

    def test_generate_setting_en_fallback(self):
        """Test English fallback settings."""
        creator = self._make_creator("en")
        creator.ai_generator.generate_completion.side_effect = Exception("fail")
        result = creator.generate_setting("era", "John", "success", {})
        assert result["era_description"] == "Modern era"


class TestCharacterCreatorRelationships:
    """Test relationship person generation."""

    def _make_creator(self, language="zh"):
        from src.game.character_creation import CharacterCreator

        mock_gen = Mock()
        mock_gen.generate_completion = Mock()
        mock_gen.generate_completion_json = Mock()
        return CharacterCreator(ai_generator=mock_gen, language=language)

    def test_generate_single_person_success(self):
        """Test successful single person generation."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.return_value = {
            "name": "李四",
            "role": "同事",
            "relationship_desc": "工作伙伴",
            "age": 28,
            "gender": "男",
        }
        result = creator.generate_single_relationship_person("张三", "成功", {}, [], 0, 3)
        assert result["name"] == "李四"
        assert result["role"] == "同事"
        assert "affinity" in result
        assert "sexual_orientation" in result

    def test_generate_single_person_defaults(self):
        """Test defaults are applied for missing fields."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.return_value = {
            "name": "Wang",
            "role": "friend",
        }
        result = creator.generate_single_relationship_person("Player", "success", {}, [], 0, 1)
        assert result["age"] == 25
        assert result["temperament"] == "balanced"
        assert result["trust"] == 50

    def test_generate_single_person_backward_compat(self):
        """Test relationship/relationship_desc backward compatibility."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.return_value = {
            "name": "A",
            "role": "B",
            "relationship_desc": "desc text",
        }
        result = creator.generate_single_relationship_person("P", "V", {}, [], 0, 1)
        assert result["relationship"] == "desc text"

    def test_generate_single_person_forbidden_phrase(self):
        """Test forbidden phrases trigger fallback."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.return_value = {
            "name": "A",
            "role": "B",
            "relationship_desc": "有一些朋友在身边",
        }
        result = creator.generate_single_relationship_person("P", "V", {}, [], 0, 1)
        # Fallback person
        assert "人物" in result["name"]

    def test_generate_single_person_failure(self):
        """Test fallback on AI failure."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.side_effect = Exception("fail")
        result = creator.generate_single_relationship_person("张三", "成功", {}, [], 2, 5)
        assert result["name"] == "人物3"
        assert result["role"] == "朋友"

    def test_generate_single_person_en_fallback(self):
        """Test English fallback."""
        creator = self._make_creator("en")
        creator.ai_generator.generate_completion_json.side_effect = Exception("fail")
        result = creator.generate_single_relationship_person("John", "success", {}, [], 0, 1)
        assert result["name"] == "Person1"

    def test_generate_relationships_summary_success(self):
        """Test successful relationship summary generation."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.return_value = {
            "relationships_description": "完整的关系描述文本"
        }
        result = creator.generate_relationships_summary(
            "张三", "成功", {}, [{"name": "李四", "role": "朋友"}]
        )
        assert result == "完整的关系描述文本"

    def test_generate_relationships_summary_fallback_zh(self):
        """Test Chinese fallback for relationship summary."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.side_effect = Exception("fail")
        result = creator.generate_relationships_summary(
            "张三",
            "成功",
            {},
            [{"name": "李四", "role": "朋友"}, {"name": "王五", "role": "同事"}],
        )
        assert "2位" in result
        assert "李四" in result

    def test_generate_relationships_summary_empty_people(self):
        """Test fallback with no key people."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.side_effect = Exception("fail")
        result = creator.generate_relationships_summary("张三", "成功", {}, [])
        assert "多种关系" in result


class TestCharacterCreatorAttributes:
    """Test attribute generation."""

    def _make_creator(self, language="zh"):
        from src.game.character_creation import CharacterCreator

        mock_gen = Mock()
        mock_gen.generate_completion = Mock()
        mock_gen.generate_completion_json = Mock()
        return CharacterCreator(ai_generator=mock_gen, language=language)

    def test_generate_initial_attributes_success(self):
        """Test successful AI attribute generation."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.return_value = {
            "energy": 80,
            "mood": 70,
            "knowledge": 60,
            "wealth": 50000,
        }
        result = creator.generate_initial_attributes(
            {"age": {"age": 22}, "family": {"family_economy": "中等"}}
        )
        assert result["energy"] == 80
        assert result["mood"] == 70

    def test_generate_initial_attributes_clamped(self):
        """Test attribute values are clamped to valid range."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.return_value = {
            "energy": 150,
            "mood": -10,
            "knowledge": 50,
            "wealth": 2000000,
        }
        result = creator.generate_initial_attributes({})
        assert result["energy"] == 100
        assert result["mood"] == 0
        assert result["wealth"] == 1000000

    def test_generate_initial_attributes_fallback(self):
        """Test rule-based fallback when AI fails."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.side_effect = Exception("fail")
        result = creator.generate_initial_attributes(
            {"traits": {"personality": "乐观", "abilities": "聪明"}}
        )
        assert result["mood"] > 60  # Boosted by 乐观
        assert result["knowledge"] > 50  # Boosted by 聪明

    def test_rules_energy_active(self):
        """Test energy boost for active personality."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.side_effect = Exception("fail")
        result = creator.generate_initial_attributes({"traits": {"personality": "活力充沛"}})
        assert result["energy"] >= 80

    def test_rules_energy_weak(self):
        """Test energy penalty for weak personality."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.side_effect = Exception("fail")
        result = creator.generate_initial_attributes({"traits": {"personality": "体弱多病"}})
        assert result["energy"] <= 60

    def test_rules_wealthy_family(self):
        """Test wealth boost for wealthy family."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.side_effect = Exception("fail")
        result = creator.generate_initial_attributes(
            {
                "traits": {},
                "family": {"family_economy": "富裕"},
                "era": {"era_description": "现代"},
                "age": {"age": 30},
            }
        )
        assert result["wealth"] > 30000

    def test_rules_poor_family_ancient(self):
        """Test wealth reduction for poor family in ancient era."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.side_effect = Exception("fail")
        result = creator.generate_initial_attributes(
            {
                "traits": {},
                "family": {"family_economy": "贫困"},
                "era": {"era_description": "古代"},
                "age": {"age": 22},
            }
        )
        assert result["wealth"] < 20000

    def test_rules_list_traits(self):
        """Test rules handle list-format traits."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json.side_effect = Exception("fail")
        result = creator.generate_initial_attributes({"traits": {"personality": ["乐观", "开朗"]}})
        assert result["mood"] > 60


class TestCharacterCreatorMisc:
    """Test miscellaneous CharacterCreator methods."""

    def test_format_family_members_empty(self):
        from src.game.character_creation import CharacterCreator

        assert CharacterCreator._format_family_members([], "zh") == "无"
        assert CharacterCreator._format_family_members([], "en") == "None"

    def test_format_family_members_dict_format(self):
        from src.game.character_creation import CharacterCreator

        members = [{"name": "张父", "role": "父亲"}, {"name": "张母", "role": "母亲"}]
        result = CharacterCreator._format_family_members(members, "zh")
        assert "张父" in result
        assert "父亲" in result

    def test_format_family_members_string_format(self):
        from src.game.character_creation import CharacterCreator

        result = CharacterCreator._format_family_members(["父母", "弟弟"], "zh")
        assert "父母" in result
        assert "弟弟" in result

    def test_get_fallback_setting_all_types(self):
        from src.game.character_creation import CharacterCreator

        mock_gen = Mock()
        mock_gen.generate_completion = Mock()
        mock_gen.generate_completion_json = Mock()
        creator = CharacterCreator(ai_generator=mock_gen, language="zh")
        for setting_type in [
            "era",
            "age",
            "gender",
            "world",
            "family",
            "relationships",
            "traits",
            "wealth",
        ]:
            fallback = creator._get_fallback_setting(setting_type)
            assert isinstance(fallback, dict)
            assert len(fallback) > 0

    def test_get_fallback_setting_en_all_types(self):
        from src.game.character_creation import CharacterCreator

        mock_gen = Mock()
        mock_gen.generate_completion = Mock()
        mock_gen.generate_completion_json = Mock()
        creator = CharacterCreator(ai_generator=mock_gen, language="en")
        for setting_type in [
            "era",
            "age",
            "gender",
            "world",
            "family",
            "relationships",
            "traits",
            "wealth",
        ]:
            fallback = creator._get_fallback_setting(setting_type)
            assert isinstance(fallback, dict)

    def test_get_fallback_setting_unknown_type(self):
        from src.game.character_creation import CharacterCreator

        mock_gen = Mock()
        mock_gen.generate_completion = Mock()
        mock_gen.generate_completion_json = Mock()
        creator = CharacterCreator(ai_generator=mock_gen, language="zh")
        fallback = creator._get_fallback_setting("unknown_type")
        assert fallback == {}


class TestCheckAndFixMissingAttributes:
    """Test check_and_fix_missing_attributes method."""

    def _make_creator(self):
        from src.game.character_creation import CharacterCreator

        mock_gen = Mock()
        mock_gen.generate_completion = Mock()
        mock_gen.generate_completion_json = Mock()
        return CharacterCreator(ai_generator=mock_gen, language="zh")

    def test_fix_missing_birth_year(self):
        """Test birth_year is calculated when missing."""
        creator = self._make_creator()
        state = Mock()
        state.character_settings = {"era": {"year": 2024}, "age": {"age": 25}}
        state.player_name = "张三"
        state.relationships = {}
        creator.check_and_fix_missing_attributes(state)
        assert state.character_settings["age"]["birth_year"] == 1999

    def test_fix_old_format_family_members(self):
        """Test old format family members are upgraded."""
        creator = self._make_creator()
        creator.ai_generator.generate_completion_json = Mock(
            return_value={
                "members": [{"name": "张父", "role": "父亲", "relationship": "严厉的父亲"}]
            }
        )
        state = Mock()
        state.character_settings = {"family": {"family_members": ["父亲"]}}
        state.player_name = "张三"
        state.relationships = {}
        creator.check_and_fix_missing_attributes(state)
        assert isinstance(state.character_settings["family"]["family_members"][0], dict)

    def test_no_fix_needed(self):
        """Test no changes when nothing is missing."""
        creator = self._make_creator()
        state = Mock()
        state.character_settings = {
            "age": {"age": 22, "birth_year": 2002},
            "family": {"family_members": [{"name": "Mom", "role": "母亲"}]},
        }
        state.player_name = "张三"
        creator.check_and_fix_missing_attributes(state)
        # No crash

    def test_none_state_no_crash(self):
        """Test no crash with None state."""
        creator = self._make_creator()
        creator.check_and_fix_missing_attributes(None)

    def test_no_settings_no_crash(self):
        """Test no crash when character_settings is None."""
        creator = self._make_creator()
        state = Mock()
        state.character_settings = None
        creator.check_and_fix_missing_attributes(state)
