"""Quick rule-based validator for story consistency.

This validator performs fast checks without AI calls, reducing latency
before the optional AI-based consistency validation.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class QuickValidationResult:
    """Result of quick validation."""

    passed: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0


class QuickValidator:
    """
    Fast rule-based validator for story consistency.

    Performs checks without AI calls:
    1. Character name validation
    2. Forbidden word detection (meta-references)
    3. Basic temporal/logical checks
    """

    # 违禁词列表：打破第四面墙的词汇
    FORBIDDEN_WORDS_ZH = [
        "游戏",
        "模拟",
        "系统",
        "属性值",
        "精力值",
        "情绪值",
        "玩家",
        "NPC",
        "任务",
        "等级",
        "经验值",
        "技能点",
        "存档",
        "读档",
        "重启",
        "回合",
        "选项",
        "剧情线",
    ]

    FORBIDDEN_WORDS_EN = [
        "game",
        "simulation",
        "system",
        "stats",
        "energy points",
        "mood value",
        "player",
        "NPC",
        "quest",
        "level",
        "XP",
        "save",
        "load",
        "restart",
        "turn",
        "option",
        "storyline",
    ]

    # 故事中可能出现的合理词汇（避免误判）
    ALLOWED_CONTEXTS = [
        # "游戏" 在某些上下文中是合理的
        "做游戏",
        "玩游戏",
        "游戏厅",
        "游戏机",
        "电子游戏",
        "游乐园",
        "游戏规则",
        "游戏公司",
    ]

    def __init__(self):
        self._forbidden_pattern_zh = self._build_forbidden_pattern("zh")
        self._forbidden_pattern_en = self._build_forbidden_pattern("en")

    def _build_forbidden_pattern(self, language: str) -> re.Pattern:
        """Build regex pattern for forbidden words."""
        words = self.FORBIDDEN_WORDS_ZH if language == "zh" else self.FORBIDDEN_WORDS_EN
        # 匹配独立词汇，避免部分匹配
        pattern = (
            r"(?:^|[^\w])(" + "|".join(re.escape(w) for w in words) + r")(?:[^\w]|$)"
        )
        return re.compile(pattern, re.IGNORECASE)

    def validate(
        self,
        story_text: str,
        character_settings: Optional[Dict[str, Any]] = None,
        available_people: Optional[List[str]] = None,
        language: str = "zh",
    ) -> QuickValidationResult:
        """
        Perform quick validation on story text.

        Args:
            story_text: The story text to validate
            character_settings: Character settings for context
            available_people: List of allowed character names
            language: Language code ('zh' or 'en')

        Returns:
            QuickValidationResult with pass/fail status and issues
        """
        issues: List[str] = []
        warnings: List[str] = []

        if not story_text:
            return QuickValidationResult(passed=True, issues=issues, warnings=warnings)

        # 1. 检查违禁词
        forbidden_issues = self._check_forbidden_words(story_text, language)
        issues.extend(forbidden_issues)

        # 2. 检查人物名是否在允许列表中
        if available_people:
            name_issues = self._check_character_names(
                story_text, available_people, language
            )
            warnings.extend(name_issues)  # 作为警告，不阻止生成

        # 3. 检查人称一致性
        perspective_issues = self._check_perspective_consistency(story_text, language)
        issues.extend(perspective_issues)

        passed = len(issues) == 0
        result = QuickValidationResult(passed=passed, issues=issues, warnings=warnings)

        if issues:
            logger.info(f"Quick validation found {len(issues)} issues: {issues}")
        if warnings:
            logger.info(f"Quick validation warnings: {warnings}")

        return result

    def _check_forbidden_words(self, text: str, language: str) -> List[str]:
        """Check for forbidden meta-reference words."""
        issues = []
        pattern = (
            self._forbidden_pattern_zh
            if language == "zh"
            else self._forbidden_pattern_en
        )

        matches = pattern.findall(text)

        # 过滤掉合理的上下文
        for match in matches:
            if isinstance(match, tuple):
                match = match[0] if match[0] else match[1] if len(match) > 1 else ""

            match_lower = match.lower()

            # 检查是否在允许的上下文中
            is_allowed = False
            for allowed in self.ALLOWED_CONTEXTS:
                if allowed in text and match in allowed:
                    is_allowed = True
                    break

            if not is_allowed:
                if language == "zh":
                    issues.append(f"检测到违禁词「{match}」，可能打破第四面墙")
                else:
                    issues.append(
                        f"Forbidden word '{match}' detected, may break fourth wall"
                    )

        return issues

    def _check_character_names(
        self, text: str, available_people: List[str], language: str
    ) -> List[str]:
        """Check if character names in text are in the allowed list.

        ★ 中文人名识别非常困难，规则方法误报率极高。
        所以这里只做最基本的检查，不做复杂的启发式检测。
        """
        warnings: list[str] = []
        # 不再尝试从文本中提取人名，因为误报率太高
        # 只检查 available_people 中的人名是否出现在文本中（用于其他用途）
        return warnings

    def _check_perspective_consistency(self, text: str, language: str) -> List[str]:
        """Check for consistent third-person perspective."""
        issues = []

        if language == "zh":
            # 检查是否混用了第一人称
            first_person_pattern = re.compile(r"(?:^|[^\w])(我)(?:[^\w]|$)")
            second_person_pattern = re.compile(r"(?:^|[^\w])(你)(?:[^\w]|$)")

            # 排除对话中的第一/第二人称
            # 简单方法：检查非引号部分
            # 使用更安全的方式移除引号内容
            text_without_quotes = text
            for quote_pair in [('"', '"'), ("'", "'"), ("「", "」"), ("『", "』")]:
                # 简单移除配对引号内的内容
                pattern = re.escape(quote_pair[0]) + r".*?" + re.escape(quote_pair[1])
                text_without_quotes = re.sub(
                    pattern, "", text_without_quotes, flags=re.DOTALL
                )

            if first_person_pattern.search(text_without_quotes):
                issues.append("故事中使用了第一人称「我」，应使用第三人称")
            if second_person_pattern.search(text_without_quotes):
                issues.append("故事中使用了第二人称「你」，应使用第三人称")
        else:
            # 英文检查
            text_without_quotes = re.sub(r'"[^"]*"', "", text)

            first_person_pattern = re.compile(r"\bI\b")
            second_person_pattern = re.compile(r"\byou\b", re.IGNORECASE)

            if first_person_pattern.search(text_without_quotes):
                issues.append("Story uses first-person 'I', should use third-person")
            if second_person_pattern.search(text_without_quotes):
                issues.append("Story uses second-person 'you', should use third-person")

        return issues


# 便捷函数
def quick_validate_story(
    story_text: str,
    character_settings: Optional[Dict[str, Any]] = None,
    available_people: Optional[List[str]] = None,
    language: str = "zh",
) -> QuickValidationResult:
    """
    Convenience function for quick story validation.

    Args:
        story_text: The story text to validate
        character_settings: Character settings for context
        available_people: List of allowed character names
        language: Language code

    Returns:
        QuickValidationResult
    """
    validator = QuickValidator()
    return validator.validate(
        story_text=story_text,
        character_settings=character_settings,
        available_people=available_people,
        language=language,
    )
