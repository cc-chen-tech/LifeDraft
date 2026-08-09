"""Deterministic public contracts for gameplay state continuity validators."""

from types import SimpleNamespace

from src.ai.harness.character_state_validator import CharacterStateContinuityValidator
from src.ai.harness.commitment_validator import CommitmentFulfillmentValidator
from src.ai.harness.spatial_validator import SpatialMovementValidator


class TestCharacterStateContracts:
    def test_dead_character_cannot_take_an_active_action(self):
        context = {
            "world_model": SimpleNamespace(
                physical_states={"王二": {"status": "dead", "conditions": ["已死亡"]}}
            )
        }

        passed, _, details = CharacterStateContinuityValidator().validate(
            "王二走进客栈，对众人说道：我回来了。", context
        )

        assert passed is False
        assert details["dead_violations"][0]["status"] == "dead"

    def test_dream_exempts_dead_character_action(self):
        context = {
            "world_model": SimpleNamespace(
                physical_states={"王二": {"status": "dead", "conditions": ["已死亡"]}}
            )
        }

        passed, evidence, details = CharacterStateContinuityValidator().validate(
            "梦中，王二走进客栈，对众人说道：我回来了。", context
        )

        assert passed is True
        assert evidence == ""
        assert details["dead_violations"] == []

    def test_severely_injured_character_cannot_take_vigorous_action(self):
        context = {
            "world_model": SimpleNamespace(
                physical_states={"王二": {"conditions": ["左臂骨折"], "severity": "severe"}}
            )
        }

        passed, _, details = CharacterStateContinuityValidator().validate(
            "王二双手抱起巨石，举过头顶。", context
        )

        assert passed is False
        assert details["injury_violations"][0]["status"] == "severe_injury"

    def test_imprisoned_character_cannot_move_freely(self):
        context = {
            "world_model": SimpleNamespace(
                physical_states={"赵灵儿": {"status": "imprisoned", "conditions": ["被关押"]}}
            )
        }

        passed, _, details = CharacterStateContinuityValidator().validate(
            "赵灵儿在市场散步，挑选鲜花。", context
        )

        assert passed is False
        assert details["imprisoned_violations"][0]["status"] == "imprisoned"


class TestCommitmentContracts:
    def test_overdue_critical_commitment_must_be_addressed(self):
        context = {
            "world_model": SimpleNamespace(
                current_week=5,
                active_commitments=[
                    {
                        "description": "答应师父取回灵药",
                        "parties": ["师父"],
                        "deadline_week": 5,
                        "importance": "critical",
                        "status": "pending",
                    }
                ],
            )
        }

        passed, evidence, details = CommitmentFulfillmentValidator().validate(
            "李逍遥在酒楼中品茶。", context
        )

        assert passed is False
        assert "承诺履行违规" in evidence
        assert details["overdue_issues"][0]["commitment"] == "答应师父取回灵药"

    def test_pending_commitment_cannot_be_directly_breached(self):
        context = {
            "world_model": SimpleNamespace(
                current_week=4,
                active_commitments=[
                    {
                        "description": "承诺保护赵灵儿",
                        "parties": ["赵灵儿"],
                        "deadline_week": 8,
                        "importance": "critical",
                        "status": "pending",
                    }
                ],
            )
        }

        passed, _, details = CommitmentFulfillmentValidator().validate(
            "李逍遥攻击赵灵儿，拔剑相向。", context
        )

        assert passed is False
        assert details["contradiction_issues"][0]["party"] == "赵灵儿"

    def test_mentioned_overdue_commitment_is_accepted(self):
        context = {
            "world_model": SimpleNamespace(
                current_week=5,
                active_commitments=[
                    {
                        "description": "答应师父取回灵药",
                        "parties": ["师父"],
                        "deadline_week": 5,
                        "importance": "critical",
                        "status": "pending",
                    }
                ],
            )
        }

        passed, evidence, details = CommitmentFulfillmentValidator().validate(
            "李逍遥想起答应师父取回灵药，立刻出城寻找。", context
        )

        assert passed is True
        assert evidence == ""
        assert details["overdue_issues"] == []


class TestSpatialMovementContracts:
    def _world_model(self):
        return SimpleNamespace(
            character_locations={
                "李逍遥": {"location": "洛阳城", "region": "河南"},
                "赵灵儿": {"location": "苗疆", "region": "云南"},
            },
            location_graph={},
        )

    def test_remote_movement_without_fast_travel_is_rejected(self):
        passed, _, details = SpatialMovementValidator().validate(
            "李逍遥来到了苗疆。", {"world_model": self._world_model()}
        )

        assert passed is False
        assert details["movement_issues"][0]["from"] == "洛阳城"
        assert details["movement_issues"][0]["to"] == "苗疆"

    def test_fast_travel_exempts_remote_movement(self):
        passed, evidence, details = SpatialMovementValidator().validate(
            "李逍遥骑马来到了苗疆。", {"world_model": self._world_model()}
        )

        assert passed is True
        assert evidence == ""
        assert details["has_fast_travel"] is True
