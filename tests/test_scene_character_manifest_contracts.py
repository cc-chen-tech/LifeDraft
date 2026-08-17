from src.services.image.scene_service import SceneImageService
import pytest

pytestmark = [pytest.mark.unit]



def _service() -> SceneImageService:
    return SceneImageService.__new__(SceneImageService)


def test_story_character_extraction_includes_only_mentioned_known_people_once():
    service = _service()
    settings = {
        "age": {"age": 29},
        "gender": {"gender": "女"},
        "appearance": {"face": "鹅蛋脸", "hair": "短发", "eyes": "明亮"},
        "relationships": {
            "key_people": [
                {"name": "沈砚", "relationship": "同事", "occupation": "记者"},
                {"name": "未提及", "relationship": "朋友"},
            ]
        },
        "family": {
            "family_members": [
                {"name": "母亲", "relationship": "母女", "personality": "坚韧"},
                {"name": "沈砚", "relationship": "远亲"},
            ]
        },
    }

    characters = service._extract_story_characters(
        "林见微与沈砚在雨中拜访母亲，随后离开。", settings, "林见微"
    )

    assert [character["name"] for character in characters] == ["林见微", "沈砚", "母亲"]
    assert characters[0]["description"] == "29岁，女，鹅蛋脸，短发，明亮"
    assert characters[1]["description"] == "同事，记者"
    assert characters[2]["description"] == "母女，坚韧"


def test_scene_character_helpers_support_legacy_fields_and_multi_person_layout():
    service = _service()
    info = service._build_char_info(
        {
            "era": {"era_description": "一段超过三十个字符的现代都市背景描述，用于验证安全截断行为，并确保测试样本明显超过限制"},
            "gender": "男",
            "age": 31,
        },
        "顾川",
    )

    assert info["name"] == "顾川"
    assert info["gender"] == "男"
    assert info["age"] == "31"
    assert len(info["era"]) == 30
    assert SceneImageService._build_character_desc({}) == "一个普通人"
    assert SceneImageService._build_character_desc_from_settings({}, "顾川") == "顾川"
    assert [SceneImageService._get_character_position_hint(index, 4) for index in range(4)] == [
        "画面左侧前景",
        "画面右侧前景",
        "画面左侧背景",
        "画面右侧背景",
    ]

    manifest = service._build_character_manifest(
        [
            {"name": "顾川", "description": "31岁，男"},
            {"name": "沈砚", "description": "同事，记者"},
            {"name": "母亲", "description": "母女，坚韧"},
            {"name": "邻居", "description": "朋友"},
        ],
        player_name="顾川",
    )

    assert "- 顾川（画面左侧前景）：31岁，男" in manifest
    assert "- 沈砚（画面右侧前景）：同事，记者" in manifest
    assert "- 母亲（画面左侧背景）：母女，坚韧" in manifest
    assert "人物区分要求" in manifest
