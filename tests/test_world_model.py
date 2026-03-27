"""Tests for world_model module - improving coverage from 34%."""

from unittest.mock import MagicMock

import pytest

from src.game.world_model import (CAREER_LEVEL_INDEX, CAREER_LEVELS,
                                  MAX_CAREER_JUMP, MIN_WEEKS_BEFORE_PROMOTION,
                                  CareerInfo, CausalChain, CharacterProfile,
                                  Commitment, LocationInfo, PhysicalState,
                                  WorldModel, _extract_region)


class TestLocationInfo:
    """Tests for LocationInfo dataclass."""

    def test_default_values(self):
        loc = LocationInfo()
        assert loc.location == ""
        assert loc.region == ""
        assert loc.since_week == 0
        assert loc.travel_mode == "resident"

    def test_to_dict(self):
        loc = LocationInfo(
            location="北京市朝阳区", region="北京", since_week=5, travel_mode="visiting"
        )
        d = loc.to_dict()
        assert d["location"] == "北京市朝阳区"
        assert d["region"] == "北京"
        assert d["since_week"] == 5
        assert d["travel_mode"] == "visiting"

    def test_from_dict(self):
        d = {
            "location": "上海浦东新区",
            "region": "上海",
            "since_week": 10,
            "travel_mode": "traveling",
        }
        loc = LocationInfo.from_dict(d)
        assert loc.location == "上海浦东新区"
        assert loc.region == "上海"
        assert loc.since_week == 10
        assert loc.travel_mode == "traveling"

    def test_from_dict_with_defaults(self):
        loc = LocationInfo.from_dict({})
        assert loc.location == ""
        assert loc.travel_mode == "resident"


class TestCareerInfo:
    """Tests for CareerInfo dataclass."""

    def test_default_values(self):
        career = CareerInfo()
        assert career.current_job == ""
        assert career.employer == ""
        assert career.level == "mid"
        assert career.since_week == 0
        assert career.history == []

    def test_to_dict(self):
        career = CareerInfo(
            current_job="产品经理",
            employer="某科技公司",
            level="senior",
            since_week=20,
            history=[{"job": "工程师", "duration": 50}],
        )
        d = career.to_dict()
        assert d["current_job"] == "产品经理"
        assert d["employer"] == "某科技公司"
        assert d["level"] == "senior"
        assert d["history"] == [{"job": "工程师", "duration": 50}]

    def test_from_dict(self):
        d = {
            "current_job": "CEO",
            "employer": "StartupX",
            "level": "executive",
            "since_week": 100,
            "history": [],
        }
        career = CareerInfo.from_dict(d)
        assert career.current_job == "CEO"
        assert career.level == "executive"


class TestCommitment:
    """Tests for Commitment dataclass."""

    def test_default_values(self):
        commit = Commitment()
        assert commit.description == ""
        assert commit.parties == []
        assert commit.deadline_week == -1
        assert commit.status == "pending"
        assert commit.importance == "normal"

    def test_to_dict(self):
        commit = Commitment(
            description="答应周末陪妈妈去医院",
            parties=["妈妈"],
            deadline_week=10,
            status="pending",
            created_week=5,
            importance="critical",
        )
        d = commit.to_dict()
        assert d["description"] == "答应周末陪妈妈去医院"
        assert d["parties"] == ["妈妈"]
        assert d["deadline_week"] == 10
        assert d["importance"] == "critical"

    def test_from_dict(self):
        d = {
            "description": "参加婚礼",
            "parties": ["好友A", "好友B"],
            "deadline_week": 15,
            "status": "fulfilled",
        }
        commit = Commitment.from_dict(d)
        assert commit.description == "参加婚礼"
        assert len(commit.parties) == 2


class TestCausalChain:
    """Tests for CausalChain dataclass."""

    def test_default_values(self):
        cc = CausalChain()
        assert cc.cause == ""
        assert cc.expected_consequence == ""
        assert cc.characters == []
        assert cc.resolved is False

    def test_to_dict(self):
        cc = CausalChain(
            cause="得罪了部门主管",
            expected_consequence="可能影响晋升",
            characters=["李总"],
            created_week=5,
            resolved=False,
        )
        d = cc.to_dict()
        assert d["cause"] == "得罪了部门主管"
        assert d["expected_consequence"] == "可能影响晋升"
        assert d["resolved"] is False

    def test_from_dict(self):
        d = {
            "cause": "投资失败",
            "expected_consequence": "财务紧张",
            "characters": [],
            "resolved": True,
        }
        cc = CausalChain.from_dict(d)
        assert cc.cause == "投资失败"
        assert cc.resolved is True


class TestPhysicalState:
    """Tests for PhysicalState dataclass."""

    def test_default_values(self):
        ps = PhysicalState()
        assert ps.condition == ""
        assert ps.severity == "moderate"
        assert ps.expected_recovery_week == -1

    def test_to_dict(self):
        ps = PhysicalState(
            condition="右腿骨折",
            severity="severe",
            since_week=10,
            expected_recovery_week=20,
        )
        d = ps.to_dict()
        assert d["condition"] == "右腿骨折"
        assert d["severity"] == "severe"
        assert d["expected_recovery_week"] == 20

    def test_from_dict(self):
        d = {
            "condition": "感冒",
            "severity": "minor",
            "since_week": 5,
            "expected_recovery_week": 6,
        }
        ps = PhysicalState.from_dict(d)
        assert ps.condition == "感冒"
        assert ps.severity == "minor"


class TestCharacterProfile:
    """Tests for CharacterProfile dataclass."""

    def test_default_values(self):
        cp = CharacterProfile()
        assert cp.character == ""
        assert cp.behavioral_traits == []
        assert cp.speech_style == ""
        assert cp.evidence_count == 0

    def test_to_dict(self):
        cp = CharacterProfile(
            character="李明",
            behavioral_traits=["冲突回避型", "善于倾听"],
            speech_style="直接",
            decision_patterns=["倾向妥协"],
            emotional_tendencies=["压抑情绪"],
            behavioral_boundaries=["绝不公开发怒"],
            constraint_text="李明是一个善于倾听的人...",
            evidence_count=5,
            last_updated_week=20,
        )
        d = cp.to_dict()
        assert d["character"] == "李明"
        assert len(d["behavioral_traits"]) == 2
        assert d["evidence_count"] == 5

    def test_from_dict(self):
        d = {
            "character": "王华",
            "behavioral_traits": ["外向"],
            "speech_style": "幽默",
            "evidence_count": 3,
        }
        cp = CharacterProfile.from_dict(d)
        assert cp.character == "王华"
        assert cp.evidence_count == 3


class TestWorldModel:
    """Tests for WorldModel class."""

    def test_init(self):
        wm = WorldModel()
        assert wm.character_locations == {}
        assert wm.career_records == {}
        assert wm.active_commitments == []
        assert wm.causal_chains == []
        assert wm.physical_states == {}
        assert wm.current_week == 0

    def test_from_player_state_empty(self):
        player_state = MagicMock()
        player_state.week = 10
        player_state.character_settings = {}
        player_state.world_model_data = None
        player_state.established_facts = []
        player_state.player_name = "Hero"

        wm = WorldModel.from_player_state(player_state)
        assert wm.current_week == 10
        assert wm.era == "modern"

    def test_from_player_state_with_data(self):
        player_state = MagicMock()
        player_state.week = 15
        player_state.character_settings = {
            "era": {"era_description": "科幻未来"},
            "occupation": {
                "occupation": "工程师",
                "employer": "TechCorp",
                "level": "senior",
            },
        }
        player_state.world_model_data = {
            "character_locations": {
                "Hero": {
                    "location": "北京",
                    "region": "北京",
                    "since_week": 0,
                    "travel_mode": "resident",
                }
            },
            "career_records": {
                "Hero": {"current_job": "工程师", "level": "senior", "since_week": 0}
            },
            "active_commitments": [
                {"description": "完成项目", "parties": ["老板"], "deadline_week": 20}
            ],
            "causal_chains": [
                {"cause": "加班", "expected_consequence": "升职", "resolved": False}
            ],
            "physical_states": {"Hero": {"condition": "疲劳", "severity": "minor"}},
            "character_profiles": {
                "李明": {
                    "character": "李明",
                    "evidence_count": 5,
                    "constraint_text": "Test",
                }
            },
        }
        player_state.established_facts = []
        player_state.player_name = "Hero"

        wm = WorldModel.from_player_state(player_state)
        assert wm.current_week == 15
        assert wm.era == "科幻未来"
        assert "Hero" in wm.character_locations
        assert "Hero" in wm.career_records
        assert len(wm.active_commitments) == 1
        assert len(wm.causal_chains) == 1
        assert "Hero" in wm.physical_states
        assert "李明" in wm.character_profiles

    def test_from_player_state_legacy_facts(self):
        player_state = MagicMock()
        player_state.week = 5
        player_state.character_settings = {}
        player_state.world_model_data = {}
        player_state.established_facts = [
            {
                "category": "location",
                "subject": "Hero",
                "fact": "北京市朝阳区",
                "established_week": 1,
            },
            {
                "category": "role",
                "subject": "Hero",
                "fact": "软件工程师",
                "established_week": 1,
            },
        ]
        player_state.player_name = "Hero"

        wm = WorldModel.from_player_state(player_state)
        assert "Hero" in wm.character_locations
        assert wm.character_locations["Hero"].location == "北京市朝阳区"
        assert "Hero" in wm.career_records
        assert wm.career_records["Hero"].current_job == "软件工程师"

    def test_check_geographic_feasibility_no_conflict(self):
        wm = WorldModel()
        wm.character_locations["A"] = LocationInfo(location="北京", region="北京")
        wm.character_locations["B"] = LocationInfo(location="北京朝阳", region="北京")

        issues = wm.check_geographic_feasibility(["A", "B"])
        assert len(issues) == 0

    def test_check_geographic_feasibility_with_conflict(self):
        wm = WorldModel()
        wm.character_locations["A"] = LocationInfo(location="北京", region="北京")
        wm.character_locations["B"] = LocationInfo(location="上海", region="上海")

        issues = wm.check_geographic_feasibility(["A", "B"])
        assert len(issues) == 1
        assert "地理冲突" in issues[0]

    def test_check_geographic_feasibility_insufficient_data(self):
        wm = WorldModel()
        wm.character_locations["A"] = LocationInfo(location="北京", region="北京")

        issues = wm.check_geographic_feasibility(["A", "B"])  # B has no location
        assert len(issues) == 0  # Not enough data to validate

    def test_check_career_plausibility_no_record(self):
        wm = WorldModel()
        issues = wm.check_career_plausibility("Unknown", "CEO", "executive")
        assert len(issues) == 0  # No record = no validation

    def test_check_career_plausibility_valid_promotion(self):
        wm = WorldModel()
        wm.current_week = 100
        wm.career_records["Hero"] = CareerInfo(
            current_job="工程师", level="senior", since_week=0
        )

        issues = wm.check_career_plausibility("Hero", "技术主管", "lead")
        assert len(issues) == 0  # Valid single-level jump

    def test_check_career_plausibility_too_fast_promotion(self):
        wm = WorldModel()
        wm.current_week = 10  # Only 10 weeks since start
        wm.career_records["Hero"] = CareerInfo(
            current_job="工程师", level="junior", since_week=5
        )

        issues = wm.check_career_plausibility("Hero", "技术主管", "senior")
        # Should flag promotion as too fast (5 weeks in junior role)
        assert len(issues) >= 1

    def test_check_career_plausibility_big_jump(self):
        wm = WorldModel()
        wm.current_week = 200
        wm.career_records["Hero"] = CareerInfo(
            current_job="实习生", level="intern", since_week=0
        )

        issues = wm.check_career_plausibility("Hero", "CEO", "executive")
        assert len(issues) >= 1
        assert "职业跳跃过大" in issues[0]

    def test_get_pending_commitments(self):
        wm = WorldModel()
        wm.active_commitments = [
            Commitment(description="Task 1", deadline_week=5, status="pending"),
            Commitment(description="Task 2", deadline_week=15, status="pending"),
            Commitment(description="Task 3", deadline_week=3, status="fulfilled"),
            Commitment(
                description="Task 4", deadline_week=-1, status="pending"
            ),  # No deadline
        ]

        pending = wm.get_pending_commitments(10)
        assert len(pending) == 1
        assert pending[0].description == "Task 1"

    def test_get_expiring_commitments(self):
        wm = WorldModel()
        wm.active_commitments = [
            Commitment(description="Soon", deadline_week=12, status="pending"),
            Commitment(description="Later", deadline_week=20, status="pending"),
            Commitment(description="Now", deadline_week=10, status="pending"),
        ]

        expiring = wm.get_expiring_commitments(10, lookahead=3)
        assert len(expiring) == 2  # Deadline 10 and 12

    def test_get_active_causal_chains(self):
        wm = WorldModel()
        wm.causal_chains = [
            CausalChain(cause="A", resolved=False),
            CausalChain(cause="B", resolved=True),
            CausalChain(cause="C", resolved=False),
        ]

        active = wm.get_active_causal_chains()
        assert len(active) == 2

    def test_get_established_profile_names(self):
        wm = WorldModel()
        wm.character_profiles = {
            "Established": CharacterProfile(
                character="Established", evidence_count=5, constraint_text="Test"
            ),
            "New": CharacterProfile(
                character="New", evidence_count=2, constraint_text="Test"
            ),
            "Empty": CharacterProfile(
                character="Empty", evidence_count=5, constraint_text=""
            ),
        }

        names = wm.get_established_profile_names()
        assert "Established" in names
        assert "New" not in names  # evidence_count < 4
        assert "Empty" not in names  # No constraint_text

    def test_build_constraints_text_empty(self):
        wm = WorldModel()
        text = wm.build_constraints_text("zh")
        assert text == ""

    def test_build_constraints_text_chinese(self):
        wm = WorldModel()
        wm.current_week = 10
        wm.character_locations["Hero"] = LocationInfo(
            location="北京市朝阳区", region="北京"
        )
        wm.career_records["Hero"] = CareerInfo(
            current_job="工程师", employer="TechCorp", level="senior"
        )
        wm.active_commitments = [
            Commitment(description="完成项目", parties=["老板"], deadline_week=12)
        ]
        wm.causal_chains = [
            CausalChain(cause="加班", expected_consequence="疲劳", resolved=False)
        ]
        wm.physical_states["Hero"] = PhysicalState(condition="疲劳", severity="minor")

        text = wm.build_constraints_text("zh")
        assert "世界模型约束" in text
        assert "人物地理位置" in text
        assert "北京" in text
        assert "人物职业" in text
        assert "工程师" in text

    def test_build_constraints_text_english(self):
        wm = WorldModel()
        wm.character_locations["Hero"] = LocationInfo(
            location="Beijing", region="Beijing"
        )
        wm.career_records["Hero"] = CareerInfo(current_job="Engineer", level="senior")

        text = wm.build_constraints_text("en")
        assert "World Model Constraints" in text
        assert "CHARACTER LOCATION CONSTRAINTS" in text

    def test_to_dict(self):
        wm = WorldModel()
        wm.character_locations["Hero"] = LocationInfo(location="北京", region="北京")
        wm.career_records["Hero"] = CareerInfo(current_job="工程师")
        wm.active_commitments = [Commitment(description="Task")]
        wm.causal_chains = [CausalChain(cause="Action")]
        wm.physical_states["Hero"] = PhysicalState(condition="健康")
        wm.character_profiles["李明"] = CharacterProfile(character="李明")

        d = wm.to_dict()
        assert "character_locations" in d
        assert "Hero" in d["character_locations"]
        assert "career_records" in d
        assert "active_commitments" in d
        assert len(d["active_commitments"]) == 1
        assert "character_profiles" in d


class TestExtractRegion:
    """Tests for _extract_region helper function."""

    def test_beijing(self):
        assert _extract_region("北京市朝阳区") == "北京"

    def test_shanghai(self):
        assert _extract_region("上海浦东新区") == "上海"

    def test_guangzhou(self):
        assert _extract_region("广州市天河区") == "广州"

    def test_shenzhen(self):
        assert _extract_region("深圳南山区") == "深圳"

    def test_unknown_city(self):
        # Falls back to first 2 chars
        assert _extract_region("小城镇中心") == "小城"

    def test_short_string(self):
        assert _extract_region("京") == "京"

    def test_empty_string(self):
        assert _extract_region("") == ""


class TestCareerLevelSystem:
    """Tests for career level constants."""

    def test_career_levels_order(self):
        assert CAREER_LEVELS == [
            "intern",
            "junior",
            "mid",
            "senior",
            "lead",
            "executive",
        ]

    def test_career_level_index(self):
        assert CAREER_LEVEL_INDEX["intern"] == 0
        assert CAREER_LEVEL_INDEX["junior"] == 1
        assert CAREER_LEVEL_INDEX["executive"] == 5

    def test_max_career_jump(self):
        assert MAX_CAREER_JUMP == 2

    def test_min_weeks_before_promotion(self):
        assert MIN_WEEKS_BEFORE_PROMOTION["intern"] == 12
        assert MIN_WEEKS_BEFORE_PROMOTION["junior"] == 24
