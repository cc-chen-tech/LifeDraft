"""Deterministic world-model constraint rendering contracts."""

from src.ai.story_analyzer import DynamicFact
from src.game.world_model import (
    CareerInfo,
    CausalChain,
    CharacterProfile,
    Commitment,
    LocationInfo,
    PhysicalState,
    WorldModel,
)
import pytest

pytestmark = [pytest.mark.unit]



def _populated_world_model() -> WorldModel:
    model = WorldModel()
    model.current_week = 8
    model.character_locations = {
        "林岚": LocationInfo("北京", "华北", travel_mode="resident"),
        "沈砚": LocationInfo("旅途中", "未知", travel_mode="traveling"),
    }
    model.career_records = {"林岚": CareerInfo("记者", "晨报", "senior")}
    model.active_commitments = [
        Commitment("探望母亲", ["林岚", "母亲"], 3, importance="critical"),
        Commitment("交付报道", ["林岚", "编辑"], 9),
        Commitment("整理相册", ["林岚"], 20),
    ]
    model.causal_chains = [
        CausalChain("泄露线索", "引来追查", ["林岚", "沈砚"]),
        CausalChain("已经解决", "不应出现", resolved=True),
    ]
    model.physical_states = {
        "林岚": PhysicalState("手臂受伤", "moderate", expected_recovery_week=8),
        "沈砚": PhysicalState("扭伤脚踝", "minor", expected_recovery_week=10),
    }
    model.dynamic_facts = [
        DynamicFact("minor", constraint_text="普通事实", importance="minor"),
        DynamicFact("critical", constraint_text="档案必须保密", importance="critical"),
    ]
    model.character_profiles = {
        "林岚": CharacterProfile(
            character="林岚",
            constraint_text="遇到压力时先核实证据。",
            behavioral_boundaries=["不会公开指控无辜者"],
            evidence_count=4,
        ),
        "沈砚": CharacterProfile(
            character="沈砚", constraint_text="说话谨慎。", evidence_count=2
        ),
    }
    model.required_cast = [
        {"name": "母亲", "role": "家人"},
        {"name": "编辑", "role": "同事"},
        {"name": "沈砚", "role": "朋友"},
    ]
    return model


def test_chinese_constraints_include_each_persisted_world_state_category() -> None:
    text = _populated_world_model().build_constraints_text("zh")

    assert "林岚 当前位置：北京" in text
    assert "沈砚 目前状态：旅途中" in text
    assert "林岚：记者（晨报），级别=senior" in text
    assert "探望母亲" in text
    assert "其他待兑现承诺" in text
    assert "交付报道" in text
    assert "整理相册" in text
    assert "起因：泄露线索 → 预期后果：引来追查" in text
    assert "已经解决" not in text
    assert "林岚：手臂受伤（moderate）（预计已恢复）" in text
    assert "沈砚：扭伤脚踝（minor）（预计第10周恢复）" in text
    assert "档案必须保密" in text
    assert "遇到压力时先核实证据。" in text
    assert "绝对不会：不会公开指控无辜者" in text
    assert "预设关键人物关系" in text
    assert "母亲、编辑、沈砚至少一位" in text


def test_english_constraints_render_equivalent_world_state_categories() -> None:
    text = _populated_world_model().build_constraints_text("en")

    assert "林岚 current location: 北京" in text
    assert "沈砚 current status: traveling" in text
    assert "林岚: 记者 at 晨报, level=senior" in text
    assert "Other pending commitments" in text
    assert "Cause: 泄露线索 -> Expected: 引来追查" in text
    assert "林岚: 手臂受伤 (moderate) (expected recovered)" in text
    assert "沈砚: 扭伤脚踝 (minor) (recovery ~week 10)" in text
    assert "[MUST follow] 档案必须保密" in text
    assert "[STRICT] 林岚:" in text
    assert "Preset Key People Relationships" in text
    assert "one of 母亲, 编辑, 沈砚" in text
