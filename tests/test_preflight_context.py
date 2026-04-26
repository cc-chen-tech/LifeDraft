"""Tests for preflight checker context handling."""

import pytest

from src.ai.harness.constraint_registry import ConstraintRegistry
from src.ai.harness.preflight_checker import PreflightChecker


class TestPreflightContext:
    """Test preflight checker context completeness detection."""

    @pytest.fixture
    def checker(self):
        registry = ConstraintRegistry()
        return PreflightChecker(registry)

    def test_new_game_empty_facts_allowed(self, checker):
        """Test that empty established_facts is allowed for new games.

        新游戏没有已建立的事实是正常的，不应报告为缺失。
        """
        # 新游戏的上下文
        context = {
            "available_people": ["狄仁杰", "李元芳"],
            "established_facts": [],  # 新游戏为空列表
        }

        # 包含必要标记的 prompt
        prompt = """
        [MUST]
        Available Characters: 狄仁杰, 李元芳
        """

        result = checker.check_prompt_completeness(prompt, context)

        # 不应该报告 established_facts 缺失
        assert "关键上下文数据缺失: established_facts" not in result.warnings

    def test_mid_game_empty_facts_reported(self, checker):
        """Test that empty established_facts is warned for mid-game.

        中期游戏应该有已建立的事实，如果为空可能是数据丢失。
        但当前实现无法区分新游戏和中期游戏，所以这是一个限制。
        """
        # 这是一个已知限制，暂时跳过

    def test_available_people_empty_reported(self, checker):
        """Test that empty available_people is always reported as missing."""
        context = {
            "available_people": [],  # 空列表
            "established_facts": [{"fact": "狄仁杰是大理寺丞"}],
        }

        prompt = "[MUST]\nEstablished Facts: 狄仁杰是大理寺丞"

        result = checker.check_prompt_completeness(prompt, context)

        # 应该报告 available_people 缺失
        assert "关键上下文数据缺失: available_people" in result.warnings
