"""质量级别契约测试 (Layer 3).

验证 HarnessProfile、PROFILES 以及后端模型/API 的字段一致性.
"""

from src.ai.harness.quality_level import PROFILES, QualityLevel
from src.database.models import CharacterPreset, Game


def test_fast_profile_contract():
    """FAST 级别配置契约."""
    profile = PROFILES[QualityLevel.FAST]
    assert profile.max_retries == 0
    assert profile.score_threshold == 0.0
    assert profile.enable_polish is False
    assert profile.skip_preflight is True
    assert profile.skip_ai_consistency_check is True
    assert profile.prompt_constraint_mode == "minimal"


def test_expert_profile_contract():
    """EXPERT 级别配置契约."""
    profile = PROFILES[QualityLevel.EXPERT]
    assert profile.max_retries == 2
    assert profile.score_threshold == 70.0
    assert profile.enable_polish is False
    assert profile.retry_on_high_warnings is False
    assert profile.prompt_constraint_mode == "standard"


def test_master_profile_contract():
    """MASTER 级别配置契约."""
    profile = PROFILES[QualityLevel.MASTER]
    assert profile.max_retries == 9
    assert profile.score_threshold == 85.0
    assert profile.enable_polish is True
    assert profile.polish_score_threshold == 90.0
    assert profile.max_polish_rounds == 2
    assert profile.retry_on_high_warnings is True
    assert profile.prompt_constraint_mode == "strict"


def test_game_model_has_constraint_level_field():
    """Game SQLAlchemy 模型包含 constraint_level 字段."""
    assert hasattr(Game, "constraint_level")


def test_preset_model_has_constraint_level_field():
    """CharacterPreset SQLAlchemy 模型包含 constraint_level 字段."""
    assert hasattr(CharacterPreset, "constraint_level")
