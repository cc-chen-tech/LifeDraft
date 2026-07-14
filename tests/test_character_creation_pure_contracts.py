"""Provider-free contracts for deterministic character-creation helpers."""

from src.game.character_creation import (
    CharacterCreator,
    _align_era_setting_with_life_vision,
    _strip_placeholder_surname_from_family_members,
)


class TestCharacterCreationPureContracts:
    def test_modern_life_vision_replaces_historical_era_with_game_industry_profile(self):
        era = {
            "year": 713,
            "era_description": "唐代长安与科举制度",
            "world_context": "王朝与门第",
        }

        aligned = _align_era_setting_with_life_vision(
            era,
            "2026年在上海成为独立游戏开发者，关注叙事设计和音乐创作，不要古代",
        )

        assert aligned["year"] == 2026
        assert aligned["_aligned_to_life_vision"] is True
        assert "独立游戏行业" in aligned["era_name"]
        assert "唐" not in f"{aligned['era_description']} {aligned['world_context']}"
        assert era["year"] == 713

    def test_classical_life_vision_replaces_modern_era_and_bounds_year(self):
        era = {
            "year": 2400,
            "era_description": "现代互联网公司和AI协作",
            "world_context": "科技创业环境",
        }

        aligned = _align_era_setting_with_life_vision(
            era, "成为坚持古典世界观的医者，避免现代科技，关注师承和乡里"
        )

        assert aligned["year"] == 1899
        assert aligned["_aligned_to_life_vision"] is True
        assert "古代中国" in aligned["era_name"]
        assert "互联网" not in f"{aligned['era_description']} {aligned['world_context']}"

    def test_non_conflicting_era_is_preserved_without_alignment_marker(self):
        era = {"year": 2024, "era_description": "现代都市", "world_context": "互联网行业"}

        aligned = _align_era_setting_with_life_vision(era, "希望过平静而充实的人生")

        assert aligned is era
        assert "_aligned_to_life_vision" not in aligned

    def test_placeholder_prefix_is_removed_only_from_matching_family_members(self):
        family = {
            "family_members": [
                {"name": "测试卫国", "role": "父亲"},
                {"name": "测试秀兰", "role": "母亲"},
                {"name": "王阿姨", "role": "邻居"},
                "未结构化成员",
            ]
        }

        normalized = _strip_placeholder_surname_from_family_members(family, "测试小明")

        assert [member["name"] for member in normalized["family_members"][:3]] == [
            "卫国",
            "秀兰",
            "王阿姨",
        ]
        assert normalized["family_members"][3] == "未结构化成员"
        assert family["family_members"][0]["name"] == "测试卫国"

    def test_rule_attributes_reflect_positive_traits_and_character_background(self):
        creator = CharacterCreator.__new__(CharacterCreator)

        attributes = creator._generate_attributes_from_traits_rules(
            {
                "personality": ["活力", "乐观"],
                "abilities": ["聪明", "商业"],
                "strengths": "自信",
            },
            {
                "family": {"family_economy": "富裕"},
                "era": {"era_description": "现代都市"},
                "age": {"age": 30},
            },
        )

        assert attributes == {"energy": 80, "mood": 85, "knowledge": 70, "wealth": 105000}

    def test_rule_attributes_apply_lower_bounds_for_adverse_traits_and_background(self):
        creator = CharacterCreator.__new__(CharacterCreator)

        attributes = creator._generate_attributes_from_traits_rules(
            {"personality": "weak pessimistic", "abilities": "ignorant", "weaknesses": "lack of experience"},
            {
                "family": {"family_economy": "poor"},
                "era": {"era_description": "ancient"},
                "age": {"age": 18},
            },
        )

        assert attributes == {"energy": 55, "mood": 45, "knowledge": 30, "wealth": 0}

    def test_family_member_formatter_handles_structured_plain_and_empty_lists(self):
        assert CharacterCreator._format_family_members([], "zh") == "无"
        assert CharacterCreator._format_family_members([], "en") == "None"
        assert CharacterCreator._format_family_members(
            [{"name": "卫国", "role": "父亲"}, {"name": "秀兰", "role": "母亲"}], "zh"
        ) == "卫国（父亲）、秀兰（母亲）"
        assert CharacterCreator._format_family_members(["Parents", "Sibling"], "en") == "Parents, Sibling"
