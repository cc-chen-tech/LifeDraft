"""DB integration tests for player state submodules.

Tests the 6 player state mixin submodules via save/load round-trip
with a real in-memory SQLite database. No mocks.
"""

from copy import deepcopy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Game, SessionLocal, User
from src.database.state_repository import StateRepository
from src.game.scheduled_events import ScheduledEvent
from src.game.state import PlayerState
from src.game.state.character_state import CharacterState
from src.game.state.item_state import ItemState
from src.game.state.landmark_state import LandmarkState


@pytest.fixture(autouse=True)
def patch_session_local():
    """Replace global SessionLocal with in-memory test database."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    original = SessionLocal
    import src.database.models as models
    import src.database.state_repository as repo_module

    models.SessionLocal = TestSessionLocal
    repo_module.SessionLocal = TestSessionLocal
    yield engine
    models.SessionLocal = original
    repo_module.SessionLocal = original


@pytest.fixture
def db(patch_session_local):
    """Create a fresh test session using the shared engine."""
    engine = patch_session_local
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_user(db):
    """Create a test user."""
    user = User(private_id="SUB-USER-1", public_id="SUBMOD1")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def sample_game(db, sample_user):
    """Create a test game."""
    game = Game(user_id=sample_user.user_id, language="zh")
    db.add(game)
    db.commit()
    return game


@pytest.fixture
def repo():
    """Create a StateRepository."""
    return StateRepository()


def _save_and_load(repo, game_id, player_state):
    """Helper: save state, load it back, and reconstruct PlayerState."""
    repo.save_state(game_id, player_state)
    loaded_dict = repo.load_game_state(game_id)
    assert loaded_dict is not None
    return PlayerState.from_dict(loaded_dict)


# ================================================================
# PlayerCharactersMixin tests
# ================================================================


class TestPlayerCharactersDB:
    """DB round-trip tests for PlayerCharactersMixin."""

    def test_add_character_survives_round_trip(self, repo, sample_game):
        """Characters added via add_character should survive save/load."""
        state = PlayerState()
        char = CharacterState(name="张三", role="同事", affinity=70)

        state.add_character(char)
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert "张三" in loaded.characters
        assert loaded.characters["张三"]["role"] == "同事"
        assert loaded.characters["张三"]["affinity"] == 70
        # relationships should be synced
        assert loaded.relationships.get("张三") == 70

    def test_add_character_updates_relationships(self, repo, sample_game):
        """add_character must sync affinity to relationships dict."""
        state = PlayerState()
        char = CharacterState(name="李四", role="朋友", affinity=85)

        state.add_character(char)
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert "李四" in loaded.relationships
        assert loaded.relationships["李四"] == 85

    def test_get_character_after_round_trip(self, repo, sample_game):
        """get_character should return correct CharacterState after load."""
        state = PlayerState()
        state.add_character(
            CharacterState(
                name="王五",
                role="导师",
                affinity=60,
                personality_traits=["严厉", "睿智"],
            )
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        char = loaded.get_character("王五")
        assert char is not None
        assert char.name == "王五"
        assert char.role == "导师"
        assert char.affinity == 60
        assert "严厉" in char.personality_traits

    def test_get_character_missing_returns_none(self, repo, sample_game):
        """get_character should return None for non-existent character."""
        state = PlayerState()
        state.add_character(CharacterState(name="赵六", role="邻居"))

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.get_character("不存在") is None

    def test_get_all_characters_after_round_trip(self, repo, sample_game):
        """get_all_characters should return all characters after load."""
        state = PlayerState()
        state.add_character(CharacterState(name="A", role="角色A"))
        state.add_character(CharacterState(name="B", role="角色B"))
        state.add_character(CharacterState(name="C", role="角色C"))

        loaded = _save_and_load(repo, sample_game.game_id, state)

        all_chars = loaded.get_all_characters()
        assert len(all_chars) == 3
        names = {c.name for c in all_chars}
        assert names == {"A", "B", "C"}

    def test_update_character_survives_round_trip(self, repo, sample_game):
        """update_character changes should persist across save/load."""
        state = PlayerState()
        state.add_character(CharacterState(name="钱七", role="商人", affinity=40))

        state.update_character("钱七", affinity=60, mood=80)
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.characters["钱七"]["affinity"] == 60
        assert loaded.characters["钱七"]["mood"] == 80
        # relationships should also be updated
        assert loaded.relationships.get("钱七") == 60

    def test_update_character_missing_returns_false(self, repo, sample_game):
        """update_character on non-existent character returns False."""
        state = PlayerState()
        result = state.update_character("不存在", affinity=50)
        assert result is False

    def test_remove_character_survives_round_trip(self, repo, sample_game):
        """Removed characters should not appear after save/load."""
        state = PlayerState()
        state.add_character(CharacterState(name="待删除", role="路人"))

        assert state.remove_character("待删除") is True
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert "待删除" not in loaded.characters
        assert "待删除" not in loaded.relationships

    def test_remove_character_missing_returns_false(self, repo, sample_game):
        """remove_character on non-existent character returns False."""
        state = PlayerState()
        result = state.remove_character("不存在")
        assert result is False

    def test_sync_relationships_to_characters(self, repo, sample_game):
        """sync_relationships_to_characters propagates relationship to character."""
        state = PlayerState()
        state.add_character(CharacterState(name="孙八", role="同事", affinity=50))
        # Modify relationship externally
        state.relationships["孙八"] = 90

        state.sync_relationships_to_characters()
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.characters["孙八"]["affinity"] == 90

    def test_sync_characters_to_relationships(self, repo, sample_game):
        """sync_characters_to_relationships propagates character affinity to relationships."""
        state = PlayerState()
        state.add_character(CharacterState(name="周九", role="朋友", affinity=75))
        # Clear relationship to test sync
        state.relationships = {}

        state.sync_characters_to_relationships()
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.relationships.get("周九") == 75


# ================================================================
# PlayerDataMixin tests
# ================================================================


class TestPlayerDataDB:
    """DB round-trip tests for PlayerDataMixin."""

    def test_to_dict_includes_all_core_fields(self):
        """to_dict should serialize all core state fields."""
        state = PlayerState(
            player_name="测试玩家",
            life_vision="成为伟大的冒险者",
            energy=80,
            mood=70,
            knowledge=60,
            age=25,
            week=10,
            current_round=1,
        )
        d = state.to_dict()

        assert d["player_name"] == "测试玩家"
        assert d["life_vision"] == "成为伟大的冒险者"
        assert d["energy"] == 80
        assert d["mood"] == 70
        assert d["knowledge"] == 60
        assert "wealth" not in d
        assert d["age"] == 25
        assert d["week"] == 10
        assert d["current_round"] == 1

    def test_defaults_versioned_world_projection_watermarks(self):
        """New states begin with an empty, independently-owned projection layer."""
        state = PlayerState()

        assert state.world_projection_state == {
            "version": 1,
            "projected_through_day_index": -1,
            "applied_through_day_index": -1,
            "pending_from_day_index": None,
            "oldest_pending_at": None,
            "applied_sources": [],
            "world": {
                "fact_updates": [],
                "foreshadowing_seeds": [],
                "habit_updates": [],
                "location_updates": [],
                "career_updates": [],
                "commitment_updates": [],
                "causal_updates": [],
            },
        }

    def test_loading_legacy_state_adds_missing_projection_keys_without_mutating_input(
        self,
    ):
        """Old saves retain their projection data while receiving safe v1 defaults."""
        legacy = {
            "player_name": "旧存档玩家",
            "world_projection_state": {
                "applied_through_day_index": 3,
                "world": {"location_updates": [{"name": "花果山"}]},
            },
        }

        state = PlayerState.from_dict(legacy)

        assert legacy["world_projection_state"] == {
            "applied_through_day_index": 3,
            "world": {"location_updates": [{"name": "花果山"}]},
        }
        assert state.world_projection_state["version"] == 1
        assert state.world_projection_state["applied_through_day_index"] == 3
        assert state.world_projection_state["projected_through_day_index"] == -1
        assert state.world_projection_state["world"]["location_updates"] == [
            {"name": "花果山"}
        ]
        assert state.world_projection_state["world"]["commitment_updates"] == []

    def test_loading_malformed_projection_state_keeps_only_safe_typed_values(self):
        """Malformed legacy projection fields cannot become downstream world inputs."""
        legacy = {
            "world_projection_state": {
                "version": 2,
                "projected_through_day_index": -2,
                "applied_through_day_index": True,
                "pending_from_day_index": "-1",
                "oldest_pending_at": {"not": "a scalar"},
                "applied_sources": [
                    {"event_id": "evt-7", "revision": 2, "day_index": 7},
                    ["evt-list", 3, 8],
                    {
                        "event_id": "evt-nested",
                        "revision": {"not": "an integer"},
                        "day_index": 8,
                    },
                ],
                "world": {
                    "fact_updates": {"not": "a-list"},
                    "foreshadowing_seeds": "not-a-list",
                    "habit_updates": None,
                    "location_updates": [
                        {"name": "花果山"},
                        "not-a-mapping",
                        3,
                        ["nested", "list"],
                    ],
                    "career_updates": {"not": "a-list"},
                    "commitment_updates": "not-a-list",
                    "causal_updates": 3,
                },
            }
        }
        before = deepcopy(legacy)

        state = PlayerState.from_dict(legacy)

        assert legacy == before
        assert state.world_projection_state["version"] == 1
        assert state.world_projection_state["projected_through_day_index"] == -1
        assert state.world_projection_state["applied_through_day_index"] == -1
        assert state.world_projection_state["pending_from_day_index"] is None
        assert state.world_projection_state["oldest_pending_at"] is None
        assert state.world_projection_state["applied_sources"] == [
            {"event_id": "evt-7", "revision": 2, "day_index": 7}
        ]
        assert state.world_projection_state["world"] == {
            "fact_updates": [],
            "foreshadowing_seeds": [],
            "habit_updates": [],
            "location_updates": [{"name": "花果山"}],
            "career_updates": [],
            "commitment_updates": [],
            "causal_updates": [],
        }

    def test_to_dict_includes_collection_fields(self, repo, sample_game):
        """to_dict should serialize characters, items, landmarks."""
        state = PlayerState()
        state.add_character(CharacterState(name="NPC1", role="朋友"))
        state.add_item(ItemState(name="古剑", category="weapon"))
        state.add_landmark(LandmarkState(name="洛阳城", category="area"))

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert len(loaded.characters) == 1
        assert len(loaded.items) == 1
        assert len(loaded.landmarks) == 1

    def test_from_dict_creates_valid_state(self):
        """from_dict should create a properly initialized PlayerState."""
        data = {
            "player_name": "重构玩家",
            "energy": 90,
            "mood": 85,
            "knowledge": 75,
            "wealth": 8000,
            "age": 30,
            "week": 20,
            "current_round": 2,
            "characters": {},
            "items": {},
            "landmarks": {},
            "relationships": {},
            "decision_history": [],
            "story_history": [],
            "round_history": [],
        }
        state = PlayerState.from_dict(data)

        assert state.player_name == "重构玩家"
        assert state.energy == 90
        assert state.mood == 85
        assert state.week == 20

    def test_from_dict_handles_none_string_fields(self):
        """from_dict should convert None string fields to empty strings."""
        data = {
            "player_name": "测试",
            "last_round_full_story": None,
        }
        state = PlayerState.from_dict(data)

        assert state.last_round_full_story == ""

    def test_validate_state_passes_for_valid_data(self):
        """validate_state should return True for valid state."""
        state = PlayerState(
            week=0, age=25, energy=50, mood=50, knowledge=50, wealth=100
        )

        assert state.validate_state() is True

    def test_validate_state_raises_for_out_of_bounds_energy(self):
        """validate_state should raise ValueError when energy is set out of bounds post-construction."""
        state = PlayerState(
            week=0, age=25, energy=50, mood=50, knowledge=50, wealth=100
        )
        # Bypass Pydantic construction validation by setting attribute directly
        object.__setattr__(state, "energy", 150)

        with pytest.raises(ValueError, match="Energy"):
            state.validate_state()

    def test_relationships_validator_clamps_values(self):
        """The relationships field validator should clamp values to 0-100."""
        state = PlayerState(relationships={"A": -10, "B": 150, "C": 50})
        assert state.relationships["A"] == 0
        assert state.relationships["B"] == 100
        assert state.relationships["C"] == 50

    def test_weekly_summaries_and_story_history_serialize(self, repo, sample_game):
        """List fields like weekly_summaries and story_history should survive round-trip."""
        state = PlayerState(
            weekly_summaries=[
                {"week": 0, "summary": "一切开始的一周", "bonus_effects": {}}
            ],
            story_history=["第一周故事文本"],
            four_week_summaries=[{"weeks": "0-3", "summary": "首月总结"}],
            yearly_summaries=[{"year": 1, "summary": "第一年总结"}],
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert len(loaded.weekly_summaries) == 1
        assert loaded.weekly_summaries[0]["summary"] == "一切开始的一周"
        assert len(loaded.story_history) == 1
        assert len(loaded.four_week_summaries) == 1
        assert len(loaded.yearly_summaries) == 1

    def test_world_model_data_survives_round_trip(self, repo, sample_game):
        """world_model_data dict should survive save/load."""
        wm_data = {
            "character_locations": {
                "主角": {
                    "location": "长安",
                    "region": "长安",
                    "since_week": 5,
                    "travel_mode": "resident",
                }
            },
            "career_records": {},
            "active_commitments": [],
            "causal_chains": [],
            "physical_states": {},
            "dynamic_facts": [],
            "character_profiles": {},
        }
        state = PlayerState(world_model_data=wm_data)

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert "character_locations" in loaded.world_model_data
        assert (
            loaded.world_model_data["character_locations"]["主角"]["location"] == "长安"
        )


# ================================================================
# PlayerEventsMixin tests
# ================================================================


class TestPlayerEventsDB:
    """DB round-trip tests for PlayerEventsMixin."""

    def test_add_scheduled_event_survives_round_trip(self, repo, sample_game):
        """Scheduled events should survive save/load."""
        state = PlayerState(week=5, current_round=1)
        event = ScheduledEvent(
            description="与张三约定周末见面",
            parties=["张三"],
            scheduled_week=5,
            scheduled_round=2,
            importance="normal",
        )
        state.add_scheduled_event(event)

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert len(loaded.scheduled_events) == 1
        assert loaded.scheduled_events[0]["description"] == "与张三约定周末见面"
        assert loaded.scheduled_events[0]["scheduled_week"] == 5
        assert loaded.scheduled_events[0]["scheduled_round"] == 2
        assert loaded.scheduled_events[0]["status"] == "pending"

    def test_add_scheduled_event_dedup_by_id(self, repo, sample_game):
        """Adding same event_id twice should not duplicate."""
        state = PlayerState(week=5, current_round=1)
        event = ScheduledEvent(
            event_id="EVT-001",
            description="去图书馆还书",
            scheduled_week=5,
            scheduled_round=1,
            importance="normal",
        )
        state.add_scheduled_event(event)
        state.add_scheduled_event(event)  # duplicate

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert len(loaded.scheduled_events) == 1

    def test_get_pending_scheduled_events_filters_by_time(self, repo, sample_game):
        """get_pending_scheduled_events should only return events matching current week/round."""
        state = PlayerState(week=5, current_round=1)
        # Event at current time
        state.add_scheduled_event(
            ScheduledEvent(
                description="当前事件",
                scheduled_week=5,
                scheduled_round=1,
                importance="critical",
            )
        )
        # Event in the future
        state.add_scheduled_event(
            ScheduledEvent(
                description="未来事件",
                scheduled_week=6,
                scheduled_round=0,
                importance="normal",
            )
        )
        # Event in the past (already triggered)
        past = ScheduledEvent(
            description="过去事件",
            scheduled_week=4,
            scheduled_round=0,
            importance="normal",
        )
        past.status = "triggered"
        state.scheduled_events.append(past.to_dict())

        loaded = _save_and_load(repo, sample_game.game_id, state)

        pending = loaded.get_pending_scheduled_events()
        assert len(pending) == 1
        assert pending[0]["description"] == "当前事件"

    def test_get_pending_scheduled_events_uses_explicit_params(self, repo, sample_game):
        """get_pending_scheduled_events should use explicit week/round when provided."""
        state = PlayerState(week=5, current_round=1)
        state.add_scheduled_event(
            ScheduledEvent(
                description="未来事件",
                scheduled_week=6,
                scheduled_round=2,
                importance="critical",
            )
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        # Query with explicit params matching the future event
        pending = loaded.get_pending_scheduled_events(week=6, round_num=2)
        assert len(pending) == 1
        assert pending[0]["description"] == "未来事件"

    def test_mark_scheduled_event_triggered(self, repo, sample_game):
        """mark_scheduled_event_triggered should update status."""
        state = PlayerState(week=5, current_round=1)
        state.add_scheduled_event(
            ScheduledEvent(
                event_id="EVT-MARK",
                description="标记事件",
                scheduled_week=5,
                scheduled_round=1,
            )
        )

        state.mark_scheduled_event_triggered("EVT-MARK")
        loaded = _save_and_load(repo, sample_game.game_id, state)

        for e in loaded.scheduled_events:
            if e["event_id"] == "EVT-MARK":
                assert e["status"] == "triggered"
                break
        else:
            pytest.fail("Event not found after marking triggered")

    def test_mark_scheduled_event_triggered_missing(self, repo, sample_game):
        """mark_scheduled_event_triggered for non-existent id returns False."""
        state = PlayerState()
        result = state.mark_scheduled_event_triggered("NONEXISTENT")
        assert result is False

    def test_get_overdue_scheduled_events(self, repo, sample_game):
        """get_overdue_scheduled_events returns pending events before current time."""
        state = PlayerState(week=5, current_round=2)
        # Past event (earlier week)
        state.add_scheduled_event(
            ScheduledEvent(
                description="上周事件",
                scheduled_week=4,
                scheduled_round=0,
                importance="normal",
            )
        )
        # Past event (earlier round same week)
        state.add_scheduled_event(
            ScheduledEvent(
                description="本周早先事件",
                scheduled_week=5,
                scheduled_round=0,
                importance="normal",
            )
        )
        # Current event (not overdue)
        state.add_scheduled_event(
            ScheduledEvent(
                description="当前事件",
                scheduled_week=5,
                scheduled_round=2,
                importance="normal",
            )
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        overdue = loaded.get_overdue_scheduled_events()
        assert len(overdue) == 2
        overdue_descs = {e["description"] for e in overdue}
        assert "上周事件" in overdue_descs
        assert "本周早先事件" in overdue_descs

    def test_scheduled_event_manager_round_trip(self, repo, sample_game):
        """get_scheduled_event_manager should reconstruct manager from saved state."""
        state = PlayerState(week=5, current_round=1)
        state.add_scheduled_event(
            ScheduledEvent(
                event_id="EVT-MGR-1",
                description="事件一",
                scheduled_week=5,
                scheduled_round=1,
            )
        )
        state.add_scheduled_event(
            ScheduledEvent(
                event_id="EVT-MGR-2",
                description="事件二",
                scheduled_week=6,
                scheduled_round=0,
            )
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        manager = loaded.get_scheduled_event_manager()
        assert len(manager.events) == 2

    def test_sync_scheduled_events_from_manager(self, repo, sample_game):
        """sync_scheduled_events_from_manager should update state from manager."""
        state = PlayerState(week=5, current_round=1)
        state.add_scheduled_event(
            ScheduledEvent(
                event_id="EVT-SYNC",
                description="原始事件",
                scheduled_week=5,
                scheduled_round=1,
            )
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        # Get manager, mark event as triggered, sync back
        manager = loaded.get_scheduled_event_manager()
        manager.mark_triggered("EVT-SYNC")
        loaded.sync_scheduled_events_from_manager(manager)

        # Verify synced
        for e in loaded.scheduled_events:
            if e["event_id"] == "EVT-SYNC":
                assert e["status"] == "triggered"
                break
        else:
            pytest.fail("Event not found after sync")


# ================================================================
# PlayerInventoryMixin tests
# ================================================================


class TestPlayerInventoryDB:
    """DB round-trip tests for PlayerInventoryMixin."""

    def test_add_item_survives_round_trip(self, repo, sample_game):
        """Items added via add_item should survive save/load."""
        state = PlayerState()
        item = ItemState(
            name="古剑",
            description="一把传世的古剑",
            category="weapon",
            importance="important",
            is_key_item=True,
        )
        state.add_item(item)

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert "古剑" in loaded.items
        assert loaded.items["古剑"]["description"] == "一把传世的古剑"
        assert loaded.items["古剑"]["category"] == "weapon"
        assert loaded.items["古剑"]["is_key_item"] is True

    def test_get_item_after_round_trip(self, repo, sample_game):
        """get_item should return correct ItemState after load."""
        state = PlayerState()
        state.add_item(
            ItemState(
                name="藏宝图", category="document", acquired_week=3, is_key_item=True
            )
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        item = loaded.get_item("藏宝图")
        assert item is not None
        assert item.name == "藏宝图"
        assert item.category == "document"
        assert item.acquired_week == 3
        assert item.is_key_item is True

    def test_get_item_missing_returns_none(self, repo, sample_game):
        """get_item for non-existent item should return None."""
        state = PlayerState()
        state.add_item(ItemState(name="存在物品", category="other"))

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.get_item("不存在物品") is None

    def test_get_all_items_after_round_trip(self, repo, sample_game):
        """get_all_items should return all items after load."""
        state = PlayerState()
        state.add_item(ItemState(name="物品A", category="weapon"))
        state.add_item(ItemState(name="物品B", category="tool"))
        state.add_item(ItemState(name="物品C", category="keepsake"))

        loaded = _save_and_load(repo, sample_game.game_id, state)

        all_items = loaded.get_all_items()
        assert len(all_items) == 3
        names = {i.name for i in all_items}
        assert names == {"物品A", "物品B", "物品C"}

    def test_get_key_items_filters_correctly(self, repo, sample_game):
        """get_key_items should only return items with is_key_item=True."""
        state = PlayerState()
        state.add_item(
            ItemState(name="关键物品", category="treasure", is_key_item=True)
        )
        state.add_item(ItemState(name="普通物品", category="other", is_key_item=False))

        loaded = _save_and_load(repo, sample_game.game_id, state)

        key_items = loaded.get_key_items()
        assert len(key_items) == 1
        assert key_items[0].name == "关键物品"

    def test_update_item_survives_round_trip(self, repo, sample_game):
        """update_item changes should persist across save/load."""
        state = PlayerState()
        state.add_item(
            ItemState(name="旧剑", description="一把旧剑", category="weapon")
        )

        state.update_item("旧剑", description="打磨后的宝剑", importance="critical")
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.items["旧剑"]["description"] == "打磨后的宝剑"
        assert loaded.items["旧剑"]["importance"] == "critical"

    def test_update_item_missing_returns_false(self, repo, sample_game):
        """update_item on non-existent item should return False."""
        state = PlayerState()
        result = state.update_item("不存在", description="新描述")
        assert result is False

    def test_remove_item_survives_round_trip(self, repo, sample_game):
        """Removed items should not appear after save/load."""
        state = PlayerState()
        state.add_item(ItemState(name="待丢弃", category="other"))

        assert state.remove_item("待丢弃") is True
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert "待丢弃" not in loaded.items

    def test_remove_item_missing_returns_false(self, repo, sample_game):
        """remove_item on non-existent item should return False."""
        state = PlayerState()
        result = state.remove_item("不存在")
        assert result is False

    def test_get_items_context_generates_string(self, repo, sample_game):
        """get_items_context should generate a non-empty context string."""
        state = PlayerState()
        state.add_item(
            ItemState(
                name="传家宝",
                description="珍贵的传家宝物",
                category="keepsake",
                is_key_item=True,
                acquired_context="从祖宅中发现",
            )
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        context = loaded.get_items_context()
        assert len(context) > 0
        assert "传家宝" in context
        assert "传家宝物" in context

    def test_get_items_context_empty_returns_default(self, repo, sample_game):
        """get_items_context with no items should return default message."""
        state = PlayerState()
        loaded = _save_and_load(repo, sample_game.game_id, state)

        context = loaded.get_items_context()
        assert "无重要物品" in context


# ================================================================
# PlayerLandmarksMixin tests
# ================================================================


class TestPlayerLandmarksDB:
    """DB round-trip tests for PlayerLandmarksMixin."""

    def test_add_landmark_survives_round_trip(self, repo, sample_game):
        """Landmarks added via add_landmark should survive save/load."""
        state = PlayerState()
        landmark = LandmarkState(
            name="洛阳城",
            description="繁华的古都",
            category="area",
            importance="important",
            is_key_location=True,
        )
        state.add_landmark(landmark)

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert "洛阳城" in loaded.landmarks
        assert loaded.landmarks["洛阳城"]["description"] == "繁华的古都"
        assert loaded.landmarks["洛阳城"]["category"] == "area"
        assert loaded.landmarks["洛阳城"]["is_key_location"] is True

    def test_get_landmark_after_round_trip(self, repo, sample_game):
        """get_landmark should return correct LandmarkState after load."""
        state = PlayerState()
        state.add_landmark(
            LandmarkState(
                name="白鹿书院",
                category="building",
                first_appear_week=1,
                appear_count=3,
            )
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        landmark = loaded.get_landmark("白鹿书院")
        assert landmark is not None
        assert landmark.name == "白鹿书院"
        assert landmark.category == "building"
        assert landmark.first_appear_week == 1
        assert landmark.appear_count == 3

    def test_get_landmark_missing_returns_none(self, repo, sample_game):
        """get_landmark for non-existent landmark should return None."""
        state = PlayerState()
        state.add_landmark(LandmarkState(name="存在地点", category="other"))

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.get_landmark("不存在地点") is None

    def test_get_all_landmarks_after_round_trip(self, repo, sample_game):
        """get_all_landmarks should return all landmarks after load."""
        state = PlayerState()
        state.add_landmark(LandmarkState(name="地点A", category="building"))
        state.add_landmark(LandmarkState(name="地点B", category="nature"))
        state.add_landmark(LandmarkState(name="地点C", category="room"))

        loaded = _save_and_load(repo, sample_game.game_id, state)

        all_landmarks = loaded.get_all_landmarks()
        assert len(all_landmarks) == 3
        names = {l.name for l in all_landmarks}
        assert names == {"地点A", "地点B", "地点C"}

    def test_get_key_landmarks_filters_correctly(self, repo, sample_game):
        """get_key_landmarks should only return landmarks with is_key_location=True."""
        state = PlayerState()
        state.add_landmark(
            LandmarkState(name="关键地点", category="area", is_key_location=True)
        )
        state.add_landmark(
            LandmarkState(name="普通地点", category="other", is_key_location=False)
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        key_landmarks = loaded.get_key_landmarks()
        assert len(key_landmarks) == 1
        assert key_landmarks[0].name == "关键地点"

    def test_update_landmark_survives_round_trip(self, repo, sample_game):
        """update_landmark changes should persist across save/load."""
        state = PlayerState()
        state.add_landmark(
            LandmarkState(name="旧房", description="破旧的房子", category="building")
        )

        state.update_landmark("旧房", description="修缮后的新房", importance="critical")
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.landmarks["旧房"]["description"] == "修缮后的新房"
        assert loaded.landmarks["旧房"]["importance"] == "critical"

    def test_update_landmark_missing_returns_false(self, repo, sample_game):
        """update_landmark on non-existent landmark should return False."""
        state = PlayerState()
        result = state.update_landmark("不存在", description="新描述")
        assert result is False

    def test_remove_landmark_survives_round_trip(self, repo, sample_game):
        """Removed landmarks should not appear after save/load."""
        state = PlayerState()
        state.add_landmark(LandmarkState(name="待拆除", category="building"))

        assert state.remove_landmark("待拆除") is True
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert "待拆除" not in loaded.landmarks

    def test_remove_landmark_missing_returns_false(self, repo, sample_game):
        """remove_landmark on non-existent landmark should return False."""
        state = PlayerState()
        result = state.remove_landmark("不存在")
        assert result is False

    def test_get_landmarks_context_generates_string(self, repo, sample_game):
        """get_landmarks_context should generate a non-empty context string."""
        state = PlayerState()
        state.add_landmark(
            LandmarkState(
                name="长安城",
                description="大唐都城",
                category="area",
                is_key_location=True,
                context="繁华的古代都市",
                appear_count=5,
            )
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        context = loaded.get_landmarks_context()
        assert len(context) > 0
        assert "长安城" in context
        assert "大唐都城" in context

    def test_get_landmarks_context_empty_returns_default(self, repo, sample_game):
        """get_landmarks_context with no landmarks should return default message."""
        state = PlayerState()
        loaded = _save_and_load(repo, sample_game.game_id, state)

        context = loaded.get_landmarks_context()
        assert "无重要地点" in context


# ================================================================
# PlayerLogicMixin tests
# ================================================================


class TestPlayerLogicDB:
    """DB round-trip tests for PlayerLogicMixin."""

    def test_update_stats_survives_round_trip(self, repo, sample_game):
        """Stat updates should persist across save/load."""
        state = PlayerState(energy=80, mood=60, knowledge=50)

        state.update(energy=-10, mood=15, knowledge=20)
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.energy == 70
        assert loaded.mood == 75
        assert loaded.knowledge == 70

    def test_update_clamps_bounds(self, repo, sample_game):
        """update should clamp values to valid ranges."""
        state = PlayerState(energy=5, mood=5)

        state.update(energy=-100, mood=-100)
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.energy == 0  # clamped to MIN_RESOURCE
        assert loaded.mood == 0

        state.energy = 95
        state.update(energy=100)
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.energy == 100  # clamped to MAX_RESOURCE

    def test_update_with_relationships(self, repo, sample_game):
        """update should apply relationship changes."""
        state = PlayerState(relationships={"NPC-A": 50, "NPC-B": 50})

        state.update(relationships={"NPC-A": 20, "NPC-B": -15})
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.relationships["NPC-A"] == 70
        assert loaded.relationships["NPC-B"] == 35

    def test_advance_week_survives_round_trip(self, repo, sample_game):
        """advance_week should increment week, reset round, update age."""
        state = PlayerState(
            week=5, age=25, current_round=2, character_settings={"age": {"age": 22}}
        )

        state.advance_week()
        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.week == 6
        assert loaded.current_round == 0

    def test_advance_round_returns_correctly(self, repo, sample_game):
        """advance_round should return True when all rounds complete."""
        state = PlayerState(week=0, current_round=0, rounds_per_week=3)

        # Round 0 -> 1 (not complete)
        assert state.advance_round() is False
        # Round 1 -> 2 (not complete)
        assert state.advance_round() is False
        # Round 2 -> 3 (complete!)
        assert state.advance_round() is True

        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.current_round == 3

    def test_is_week_complete_with_full_rounds(self, repo, sample_game):
        """is_week_complete should return True when round_history has enough rounds."""
        state = PlayerState(week=2, current_round=2, rounds_per_week=3)
        state.round_history = [
            {"week": 2, "round": 0, "summary": "周一", "choice": "开始"},
            {"week": 2, "round": 1, "summary": "周中", "choice": "继续"},
            {"week": 2, "round": 2, "summary": "周末", "choice": "结束"},
        ]

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.is_week_complete() is True

    def test_is_week_complete_with_incomplete_rounds(self, repo, sample_game):
        """is_week_complete should return False when not enough rounds."""
        state = PlayerState(week=2, current_round=1, rounds_per_week=3)
        state.round_history = [
            {"week": 2, "round": 0, "summary": "周一", "choice": "开始"},
        ]

        loaded = _save_and_load(repo, sample_game.game_id, state)

        assert loaded.is_week_complete() is False

    def test_get_current_week_rounds_filters_correctly(self, repo, sample_game):
        """get_current_week_rounds should only return rounds for current week."""
        state = PlayerState(week=3, current_round=2)
        state.round_history = [
            {"week": 2, "round": 0, "summary": "上周", "choice": "..."},
            {"week": 3, "round": 0, "summary": "本周一", "choice": "开始"},
            {"week": 3, "round": 1, "summary": "本周中", "choice": "继续"},
        ]

        loaded = _save_and_load(repo, sample_game.game_id, state)

        week_rounds = loaded.get_current_week_rounds()
        assert len(week_rounds) == 2
        for r in week_rounds:
            assert r["week"] == 3

    def test_get_game_date_info(self, repo, sample_game):
        """get_game_date_info should compute correct date from week."""
        state = PlayerState(week=0, age=22, character_settings={"era": {"year": 2024}})

        loaded = _save_and_load(repo, sample_game.game_id, state)

        info = loaded.get_game_date_info()
        assert info["year"] == 2024
        assert info["month"] == 1
        assert info["week_in_month"] == 1
        assert info["total_week"] == 1  # week 0 -> display as week 1
        assert info["age"] == 22

    def test_get_game_date_info_later_week(self, repo, sample_game):
        """get_game_date_info should compute correctly for later weeks."""
        state = PlayerState(week=26, age=22, character_settings={"era": {"year": 2024}})

        loaded = _save_and_load(repo, sample_game.game_id, state)

        info = loaded.get_game_date_info()
        assert info["year"] == 2024  # 26 < 52, still year 1
        assert info["total_week"] == 27  # display week = 26 + 1

    def test_get_game_date_info_uses_year_from_era_text_when_year_field_missing(
        self, repo, sample_game
    ):
        """Modern 2026 settings without era.year should not summarize as 2024."""
        state = PlayerState(
            week=1,
            age=28,
            character_settings={
                "era": {
                    "era_name": "2026年中国AI创业浪潮",
                    "era_description": "2026年的上海，AI工具和创业团队快速迭代。",
                    "world_context": "主角在2026年加入一家AI产品团队。",
                }
            },
        )

        loaded = _save_and_load(repo, sample_game.game_id, state)

        info = loaded.get_game_date_info()
        assert info["year"] == 2026
        assert info["date_string"].startswith("2026年")

    def test_is_game_over(self, repo, sample_game):
        """is_game_over should return True when week >= TOTAL_WEEKS."""
        from config.settings import settings

        state = PlayerState(week=0)
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.is_game_over() is False

        state.week = settings.TOTAL_WEEKS
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.is_game_over() is True

    def test_get_current_phase(self, repo, sample_game):
        """get_current_phase should return correct phase by week."""
        state = PlayerState(week=10)
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.get_current_phase() == "early_career"

        state.week = 30
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.get_current_phase() == "establishing"

        state.week = 50
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.get_current_phase() == "growth"

        state.week = 80
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.get_current_phase() == "consolidation"

    def test_get_round_name(self, repo, sample_game):
        """get_round_name should return correct Chinese round names."""
        state = PlayerState(current_round=0)
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.get_round_name("zh") == "周一"

        state.current_round = 1
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.get_round_name("zh") == "周中"

        state.current_round = 2
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.get_round_name("zh") == "周末"

    def test_get_round_name_english(self, repo, sample_game):
        """get_round_name should return correct English round names."""
        state = PlayerState(current_round=0)
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.get_round_name("en") == "Monday"

        state.current_round = 1
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.get_round_name("en") == "Midweek"

        state.current_round = 2
        loaded = _save_and_load(repo, sample_game.game_id, state)
        assert loaded.get_round_name("en") == "Weekend"

    def test_get_round_context_generates_string(self, repo, sample_game):
        """get_round_context should generate context from round_history.

        Note: get_round_context skips the last round (covered by continuation_mandate),
        so we need at least 2 rounds in the current week to get non-empty output.
        """
        state = PlayerState(week=5, current_round=2)
        state.round_history = [
            {
                "week": 5,
                "round": 0,
                "event_description": "清晨醒来发现窗外有奇异的光芒。",
                "story_continuation": "你走近窗边，看到了一个悬浮的水晶球。",
                "choice": "伸手触摸水晶球",
                "event_concluded": True,
            },
            {
                "week": 5,
                "round": 1,
                "event_description": "水晶球中浮现出古老的文字。",
                "story_continuation": "文字渐渐清晰，揭示了一段预言。",
                "choice": "仔细阅读文字",
                "event_concluded": True,
            },
        ]

        loaded = _save_and_load(repo, sample_game.game_id, state)

        context = loaded.get_round_context()
        assert len(context) > 0
        assert "水晶球" in context

    def test_get_round_context_empty_history(self, repo, sample_game):
        """get_round_context with no round history should return empty string."""
        state = PlayerState(week=0, current_round=0)
        loaded = _save_and_load(repo, sample_game.game_id, state)

        context = loaded.get_round_context()
        assert context == ""
