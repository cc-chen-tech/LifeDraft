"""Provider-free contracts for narrative entity selection in round illustrations."""

from src.game.round.illustration_service import RoundIllustrationService


def _service() -> RoundIllustrationService:
    return RoundIllustrationService.__new__(RoundIllustrationService)


def test_repeated_items_ignore_one_off_and_malformed_dynamic_facts() -> None:
    facts = [
        {"category": "item", "subject": "祖传罗盘", "fact": "祖传罗盘是旧案线索"},
        {"category": "memory", "subject": "旧案", "fact": "祖传罗盘曾指向书院"},
        {"category": "memory", "subject": "雨夜", "fact": "祖传罗盘再次发热"},
    ]
    world_model = {
        "dynamic_facts": [
            {"fact_type": "possession", "subject": "祖传罗盘", "description": "林岚一直携带祖传罗盘"},
            {"fact_type": "possession", "subject": "一次性徽章", "description": "只在今晚出现"},
            None,
        ]
    }

    items = _service()._extract_important_items(
        "林岚把祖传罗盘和一次性徽章放在桌上。", world_model, facts
    )

    assert items == [
        {"name": "祖传罗盘", "type": "item", "description": "祖传罗盘是旧案线索"}
    ]


def test_location_selection_prefers_established_fact_before_recurring_world_location() -> None:
    service = _service()
    world_model = {
        "character_locations": {
            "林岚": {"location": "河畔书店"},
            "文叔": {"location": "河畔书店"},
            "沈青": {"location": "旧码头"},
        }
    }
    story = "林岚从河畔书店走到旧码头。"

    assert service._extract_important_landmarks(story, world_model, None) == [
        {"name": "河畔书店", "type": "location", "description": "重要地标：河畔书店"}
    ]
    assert service._extract_important_landmarks(
        story,
        world_model,
        [{"category": "landmark", "subject": "旧码头", "fact": "旧码头保留着潮湿的仓库"}],
    ) == [{"name": "旧码头", "type": "location", "description": "旧码头保留着潮湿的仓库"}]


def test_mixed_entity_selection_prioritizes_three_characters_then_item_and_location() -> None:
    entities = _service()._extract_involved_entities(
        "林岚、文叔、沈青和阿南在旧书院检查祖传罗盘。",
        {
            "relationships": {
                "key_people": [
                    {"name": "文叔", "relationship": "导师", "age": 54},
                    {"name": "沈青", "relationship": "同事", "gender": "女"},
                    {"name": "阿南", "relationship": "朋友"},
                    {"name": "未出现的人", "relationship": "邻居"},
                ]
            },
            "family": {"family_members": [{"name": "林岚", "relationship": "女儿"}]},
        },
        world_model_data=None,
        established_facts=[
            {"category": "item", "subject": "祖传罗盘", "fact": "祖传罗盘是旧书院的钥匙"},
            {"category": "memory", "subject": "旧案", "fact": "祖传罗盘曾指向旧书院"},
            {"category": "memory", "subject": "雨夜", "fact": "祖传罗盘再次发热"},
            {"category": "location", "subject": "旧书院", "fact": "旧书院收藏着关键档案"},
        ],
    )

    assert [(entity["name"], entity["type"]) for entity in entities] == [
        ("文叔", "character"),
        ("沈青", "character"),
        ("阿南", "character"),
        ("祖传罗盘", "item"),
        ("旧书院", "location"),
    ]
    assert entities[0]["description"] == "54岁，导师"
    assert len(entities) == 5
