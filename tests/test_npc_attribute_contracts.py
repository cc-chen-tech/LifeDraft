"""Direct, provider-free NPC profile continuity contracts."""

from types import SimpleNamespace

from src.ai.harness.npc_attribute_validator import NPCAttributeStabilityValidator


def _context():
    return {
        "world_model": SimpleNamespace(
            character_profiles={
                "赵灵儿": {
                    "appearance": "黑发，端庄",
                    "identity": "苗疆圣女",
                    "personality": "温柔善良",
                    "behavioral_boundaries": [],
                },
                "王二": {
                    "appearance": "魁梧壮硕，黑发",
                    "identity": "铁匠",
                    "personality": "豪爽",
                    "behavioral_boundaries": ["绝不在公开场合发怒"],
                },
            }
        )
    }


class TestNPCAttributeContracts:
    def test_known_profiles_without_conflict_pass(self):
        story = "苗疆圣女赵灵儿温柔地安慰众人。" + "山路在暮色中延伸，旅人们陆续离开了城门。" * 3 + "魁梧的铁匠王二安静地打铁。"
        passed, evidence, details = NPCAttributeStabilityValidator().validate(story, _context())

        assert passed is True
        assert evidence == ""
        assert details["npcs_checked"] == 2

    def test_appearance_and_identity_conflicts_are_reported(self):
        passed, _, details = NPCAttributeStabilityValidator().validate(
            "大唐公主赵灵儿披着白发走来，瘦弱矮小的王二跟在身后。", _context()
        )

        assert passed is False
        types = {issue["type"] for issue in details["violations"]}
        assert "appearance_contradiction" in types
        assert "identity_contradiction" in types

    def test_behavior_boundary_and_personality_conflicts_are_reported(self):
        passed, _, details = NPCAttributeStabilityValidator().validate(
            "王二在公开场合发怒。赵灵儿冷酷地命令众人离开。", _context()
        )

        assert passed is False
        types = {issue["type"] for issue in details["violations"]}
        assert "boundary_violation" in types
        assert "personality_contradiction" in types

    def test_self_contradictory_npc_description_is_reported(self):
        passed, _, details = NPCAttributeStabilityValidator().validate(
            "王二一会儿高大魁梧，一会儿又矮小瘦弱。", _context()
        )

        assert passed is False
        assert any(issue["type"] == "self_contradiction" for issue in details["violations"])
