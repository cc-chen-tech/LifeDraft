from typing import Any

from src.api.schemas import CharacterCollectionItem, ItemCollectionItem, LandmarkCollectionItem
from src.game.state import PlayerState
from src.services.collection_service import CollectionService


class _EmptyQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return []

    def first(self):
        return None

    def count(self):
        return 0


class _FakeDb:
    def query(self, *_):
        return _EmptyQuery()

    def close(self):
        return None


class TestCollectionRecognitionHelpersContracts:
    """Contract tests for collection recognition helper behavior."""

    def test_eligible_recognition_excludes_player_and_dedupes_across_structured_inputs(self):
        from src.api.routers.collection import _build_eligible_recognition_characters

        player_state = PlayerState(
            player_name="主角",
            characters={},
            items={},
            landmarks={},
            relationships={"赵钱": 60, "周先生": 55},
            character_settings={
                "relationships": {
                    "key_people": [
                        {"name": "赵钱"},
                        {"name": "秘书长"},
                    ],
                    "important_people": [
                        {"name": "周先生"},
                    ],
                },
                "family": {
                    "family_members": [
                        {"name": "母亲"},
                        {"name": "秘书长"},
                    ]
                },
            },
            round_history=[
                {"effects": {"relationships": {"赵钱": 3, "法官": 2}}},
            ],
            current_event_data={
                "options": [
                    {"effects": {"relationships": {"法官": 1, "总经理": 4}}}
                ]
            },
            pending_storylines=[{"related_characters": ["局长", "赵钱"]}],
            foreshadowing_seeds=[{"related_characters": ["学友"]}],
            character_habits=[{"character": "秘书长"}],
            character_arc_state={"阿明": {"phase": "rise"}},
            world_breathing_events=[{"affected_npcs": ["法官", "局长"]}],
        )

        names = _build_eligible_recognition_characters(player_state)

        assert names == [
            "赵钱",
            "秘书长",
            "周先生",
            "母亲",
            "法官",
            "总经理",
            "局长",
            "学友",
            "阿明",
        ]
        assert "主角" not in names

    def test_eligible_recognition_handles_nonstandard_relationship_shapes_without_crash(self):
        from src.api.routers.collection import _build_eligible_recognition_characters

        player_state = PlayerState(
            player_name="玩家A",
            character_settings={
                "relationships": "legacy-string-not-a-structure",
                "family": ["not", "dict"],
            },
            relationships={"老友": 10},
            characters={},
            items={},
            landmarks={},
            round_history=[],
            pending_storylines=[],
            foreshadowing_seeds=[],
            character_habits=[],
            current_event_data=None,
            world_breathing_events=[],
            character_arc_state={},
        )

        names = _build_eligible_recognition_characters(player_state)

        assert names == ["老友"]

    def test_recognition_history_appends_event_description_when_current_round_story_missing(self):
        from src.api.routers.collection import _build_entity_recognition_history

        player_state = type(
            "State",
            (),
            {
                "round_history": [],
                "week": 9,
                "current_round": 2,
                "current_event_data": {
                    "event_description": "主角在古镇发现一张卷轴。",
                    "options": ["A"],
                },
            },
        )

        history = _build_entity_recognition_history(player_state())

        assert history == [
            {
                "week": 9,
                "round": 2,
                "event_description": "主角在古镇发现一张卷轴。",
            }
        ]

    def test_recognition_history_falls_back_to_story_text(self):
        from src.api.routers.collection import _build_entity_recognition_history

        player_state = type(
            "State",
            (),
            {
                "round_history": [],
                "week": 1,
                "current_round": 3,
                "current_event_data": {
                    "story_text": "旧档案被重新打开。",
                    "options": ["A"],
                },
            },
        )

        history = _build_entity_recognition_history(player_state())

        assert history == [
            {
                "week": 1,
                "round": 3,
                "event_description": "旧档案被重新打开。",
            }
        ]

    def test_recognition_history_keeps_existing_current_round_story(self):
        from src.api.routers.collection import _build_entity_recognition_history

        player_state = type(
            "State",
            (),
            {
                "round_history": [
                    {
                        "week": 2,
                        "round": 1,
                        "event_description": "上轮已展示剧情。",
                        "story_continuation": "故事结尾。",
                    }
                ],
                "week": 2,
                "current_round": 1,
                "current_event_data": {
                    "event_description": "不应重复追加。",
                    "story_text": "备用文本。",
                },
            },
        )

        history = _build_entity_recognition_history(player_state())

        assert len(history) == 1
        assert history[0]["event_description"] == "上轮已展示剧情。"

    def test_recognition_history_returns_history_for_invalid_current_event_shape(self):
        from src.api.routers.collection import _build_entity_recognition_history

        player_state = type(
            "State",
            (),
            {
                "round_history": [
                    {"week": 1, "round": 0, "event_description": "已有历史"}
                ],
                "week": 2,
                "current_round": 0,
                "current_event_data": None,
            },
        )

        history = _build_entity_recognition_history(player_state())

        assert history == [{"week": 1, "round": 0, "event_description": "已有历史"}]


class TestCollectionServiceContractCoverage:
    """Contract tests for collection response shape and totals."""

    def _make_service(self) -> CollectionService:
        return CollectionService(db=_FakeDb())

    def test_collection_response_counts_match_payload_sections(self, monkeypatch):
        service = self._make_service()

        def fake_image_batch(_: int, _type: str):
            return {}

        monkeypatch.setattr(service, "_get_entity_images_batch", fake_image_batch)

        player_state = PlayerState(
            player_name="主角",
            character_settings={
                "relationships": {"key_people": [{"name": "书生"}]},
                "family": {"family_members": [{"name": "母亲"}]},
            },
            characters={"友人": {"relationship_desc": "旧友", "affinity": 88}},
            items={
                "令牌": {"description": "铜制令牌", "importance": "important", "category": "treasure"}
            },
            landmarks={
                "古桥": {
                    "description": "古色古香",
                    "importance": "critical",
                    "category": "building",
                }
            },
        )

        result = service.get_collection(game_id=77, player_state=player_state)

        assert isinstance(result.characters[0], CharacterCollectionItem)
        assert isinstance(result.items[0], ItemCollectionItem)
        assert isinstance(result.landmarks[0], LandmarkCollectionItem)

        assert len(result.characters) == result.total_characters == 4
        assert len(result.items) == result.total_items == 1
        assert len(result.landmarks) == result.total_landmarks == 1
        assert [c.name for c in result.characters] == ["主角", "友人", "书生", "母亲"]
