"""Quality Level MASTER Retries Contract Test

验证 MASTER 质量级别的 max_retries 配置值。
Layer 3: 契约测试 — 配置值约定。
"""

from src.ai.harness.quality_level import PROFILES, QualityLevel
import pytest

pytestmark = [pytest.mark.unit]



class TestQualityLevelMasterRetriesContract:
    """MASTER 质量级别重试次数契约测试"""

    def test_master_max_retries_is_nine(self):
        """MASTER 模式 max_retries 应为 9（共 10 次尝试）"""
        profile = PROFILES[QualityLevel.MASTER]
        assert profile.max_retries == 9

    def test_expert_max_retries_is_two(self):
        """EXPERT 模式 max_retries 应为 2（共 3 次尝试）"""
        profile = PROFILES[QualityLevel.EXPERT]
        assert profile.max_retries == 2

    def test_fast_max_retries_is_zero(self):
        """FAST 模式 max_retries 应为 0（共 1 次尝试）"""
        profile = PROFILES[QualityLevel.FAST]
        assert profile.max_retries == 0

    def test_master_score_threshold(self):
        """MASTER 模式 score_threshold 应为 85.0"""
        profile = PROFILES[QualityLevel.MASTER]
        assert profile.score_threshold == 85.0

    def test_master_enable_polish(self):
        """MASTER 模式应启用事后精修"""
        profile = PROFILES[QualityLevel.MASTER]
        assert profile.enable_polish is True

    def test_master_polish_score_threshold(self):
        """MASTER 模式 polish_score_threshold 应为 90.0"""
        profile = PROFILES[QualityLevel.MASTER]
        assert profile.polish_score_threshold == 90.0

    def test_master_max_polish_rounds(self):
        """MASTER 模式 max_polish_rounds 应为 2"""
        profile = PROFILES[QualityLevel.MASTER]
        assert profile.max_polish_rounds == 2

    def test_master_retry_on_high_warnings(self):
        """MASTER 模式 HIGH 级别警告应触发重试"""
        profile = PROFILES[QualityLevel.MASTER]
        assert profile.retry_on_high_warnings is True

    def test_expert_retry_on_high_warnings(self):
        """EXPERT 模式 HIGH 级别警告不应触发重试"""
        profile = PROFILES[QualityLevel.EXPERT]
        assert profile.retry_on_high_warnings is False
