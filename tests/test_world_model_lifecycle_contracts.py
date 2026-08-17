"""Durable lifecycle contracts for world-model state carried between rounds."""

from src.game.state import PlayerState
from src.game.world_model_updater import WorldModelUpdater
import pytest

pytestmark = [pytest.mark.unit]



def test_causal_chain_resolution_survives_state_round_trip_before_expiry() -> None:
    player = PlayerState(week=1)

    WorldModelUpdater.process_causal_updates(
        player,
        [
            {
                "action": "new",
                "cause": "接受创业合伙人的报价",
                "expected_consequence": "现金流在下月改善",
                "characters": ["沈若澜", "陆昊然"],
            }
        ],
    )
    player.week = 2
    WorldModelUpdater.process_causal_updates(
        player,
        [
            {
                "action": "resolved",
                "cause": "合伙人的报价",
                "resolution": "首笔预付款到账",
            }
        ],
    )

    restored = PlayerState.from_dict(player.to_dict())
    restored.week = 21
    WorldModelUpdater.process_causal_updates(
        restored, [{"action": "resolved", "cause": "不存在的因果链"}]
    )

    chains = restored.world_model_data["causal_chains"]
    assert len(chains) == 1
    assert chains[0]["resolved"] is True
    assert chains[0]["resolved_week"] == 2
    assert chains[0]["resolution"] == "首笔预付款到账"
    assert chains[0]["characters"] == ["沈若澜", "陆昊然"]


def test_causal_chain_expires_at_twenty_week_retention_boundary() -> None:
    player = PlayerState(
        week=22,
        world_model_data={
            "causal_chains": [
                {
                    "cause": "接受创业合伙人的报价",
                    "expected_consequence": "现金流改善",
                    "resolved": True,
                    "resolved_week": 2,
                }
            ]
        },
    )

    WorldModelUpdater.process_causal_updates(
        player, [{"action": "resolved", "cause": "不存在的因果链"}]
    )

    assert player.world_model_data["causal_chains"] == []


def test_commitment_cleanup_expires_old_resolution_without_dropping_pending_work() -> None:
    player = PlayerState(
        week=20,
        world_model_data={
            "active_commitments": [
                {
                    "description": "已经完成的融资文件",
                    "status": "fulfilled",
                    "resolved_week": 10,
                },
                {
                    "description": "下周向团队提交产品计划",
                    "status": "pending",
                    "created_week": 18,
                },
            ]
        },
    )

    WorldModelUpdater.process_commitment_updates(
        player, [{"action": "fulfilled", "description": "不存在的承诺"}]
    )

    assert player.world_model_data["active_commitments"] == [
        {
            "description": "下周向团队提交产品计划",
            "status": "pending",
            "created_week": 18,
        }
    ]
