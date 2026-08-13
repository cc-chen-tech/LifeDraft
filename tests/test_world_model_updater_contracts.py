"""Deterministic state contracts for world-model maintenance."""

from src.game.state import PlayerState
from src.game.world_model_updater import WorldModelUpdater


def test_causal_updates_resolve_related_chain_and_prune_old_resolved_history():
    state = PlayerState(week=30)
    state.world_model_data["causal_chains"] = [
        {
            "cause": "过期承诺",
            "expected_consequence": "旧后果",
            "resolved": True,
            "resolved_week": 5,
        },
        {
            "cause": "开店合同",
            "expected_consequence": "开始经营",
            "resolved": False,
        },
    ]

    WorldModelUpdater.process_causal_updates(
        state,
        [
            {
                "action": "new",
                "cause": "辞去旧工作",
                "expected_consequence": "现金流收紧",
                "characters": ["林岚"],
            },
            {
                "action": "resolved",
                "cause": "开店合同已经签署",
                "resolution": "门店按期营业",
            },
        ],
    )

    chains = state.world_model_data["causal_chains"]
    assert [chain["cause"] for chain in chains] == ["开店合同", "辞去旧工作"]
    resolved_chain = chains[0]
    assert resolved_chain["resolved"] is True
    assert resolved_chain["resolved_week"] == 30
    assert resolved_chain["resolution"] == "门店按期营业"
    assert chains[1] == {
        "cause": "辞去旧工作",
        "expected_consequence": "现金流收紧",
        "characters": ["林岚"],
        "created_week": 30,
        "resolved": False,
    }


def test_scheduled_commitments_dedupe_and_cleanup_use_real_player_state():
    state = PlayerState(week=12, current_round=1)
    state.scheduled_events = [
        {
            "event_id": "old-triggered",
            "description": "旧约定",
            "scheduled_week": 1,
            "scheduled_round": 0,
            "status": "triggered",
        }
    ]
    commitments = [
        {
            "description": "下周和母亲通话",
            "parties": ["林岚", "母亲"],
            "scheduled_week": 13,
            "scheduled_round": 2,
            "importance": "critical",
            "event_hint": "确认住院手续",
        },
        {"description": "无效约定", "scheduled_week": -1, "scheduled_round": 1},
    ]

    WorldModelUpdater.process_scheduled_events(state, commitments, current_round=1)
    WorldModelUpdater.process_scheduled_events(state, commitments, current_round=1)

    pending = state.get_pending_scheduled_events(week=13, round_num=2)
    assert len(pending) == 1
    assert pending[0]["description"] == "下周和母亲通话"
    assert pending[0]["parties"] == ["林岚", "母亲"]
    assert pending[0]["created_week"] == 12
    assert pending[0]["created_round"] == 1
    assert WorldModelUpdater.cleanup_triggered_scheduled_events(state) == 1
    assert [event["event_id"] for event in state.scheduled_events] == [pending[0]["event_id"]]


def test_story_character_sync_creates_settings_and_relationship_state_together():
    state = PlayerState(relationships={}, character_settings={})

    WorldModelUpdater.sync_story_characters_to_settings(
        state,
        story_text="Ada 在旧书院门口交给林岚一份档案。",
        relationships_in_effects={"Ada": 77, "同事": 10},
    )

    key_people = state.character_settings["relationships"]["key_people"]
    assert key_people == [
        {
            "name": "Ada",
            "role": "故事中结识",
            "affinity": 77,
            "relationship_desc": "在故事中相遇",
            "how_we_met": "在故事中自然出现",
        }
    ]
    assert state.relationships == {"Ada": 77}
