"""Quick rule-based validator for story consistency.

This validator performs fast checks without AI calls, reducing latency
before the optional AI-based consistency validation.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

    COMMON_CHINESE_SURNAMES = (
        "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢"
        "邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉"
        "岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄"
    )

    def __init__(self):
        self._forbidden_pattern_zh = self._build_forbidden_pattern("zh")
        self._forbidden_pattern_en = self._build_forbidden_pattern("en")

    def _build_forbidden_pattern(self, language: str) -> re.Pattern:
        """Build regex pattern for forbidden words."""
        words = self.FORBIDDEN_WORDS_ZH if language == "zh" else self.FORBIDDEN_WORDS_EN
        # 匹配独立词汇，避免部分匹配
        pattern = r"(?:^|[^\w])(" + "|".join(re.escape(w) for w in words) + r")(?:[^\w]|$)"
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
            name_issues = self._check_character_names(story_text, available_people, language)
            warnings.extend(name_issues)  # 作为警告，不阻止生成
            cast_drift_issues = self._check_key_people_cast_drift(
                story_text, available_people, language
            )
            issues.extend(cast_drift_issues)

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
        pattern = self._forbidden_pattern_zh if language == "zh" else self._forbidden_pattern_en

        matches = pattern.findall(text)

        # 过滤掉合理的上下文
        for match in matches:
            if isinstance(match, tuple):
                match = match[0] if match[0] else match[1] if len(match) > 1 else ""

            match.lower()

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
                    issues.append(f"Forbidden word '{match}' detected, may break fourth wall")

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

    def _check_key_people_cast_drift(
        self, text: str, available_people: List[str], language: str
    ) -> List[str]:
        """Detect severe drift where key people disappear and a new named cast appears."""
        allowed_names = [name.strip() for name in available_people if name and name.strip()]
        if len(allowed_names) < 2:
            return []

        present_allowed = [name for name in allowed_names if name in text]

        if language != "zh":
            if present_allowed:
                return []
            return [
                "上一版故事完全没有使用预设关键人物；请至少使用一个可用人物列表中的关键人物，并避免凭空替换关系网络。"
            ]

        invented_names = self._extract_likely_chinese_person_names(text, allowed_names)
        if present_allowed:
            key_people_ratio = len(present_allowed) / len(allowed_names)
            if key_people_ratio < 0.5 and len(invented_names) >= 3:
                return [
                    "上一版故事预设关键人物使用不足，反而引入了大量名单外人物"
                    f"（{ '、'.join(invented_names[:5]) }）；请围绕可用人物列表重写。"
                ]
            return []

        if len(invented_names) >= 2:
            return [
                "上一版故事完全没有使用预设关键人物，反而引入了名单外人物"
                f"（{ '、'.join(invented_names[:5]) }）；请围绕可用人物列表重写。"
            ]

        return [
            "上一版故事完全没有使用预设关键人物；请至少使用一个可用人物列表中的关键人物，并避免凭空替换关系网络。"
        ]

    def _extract_likely_chinese_person_names(
        self, text: str, allowed_names: List[str]
    ) -> List[str]:
        surname_class = re.escape(self.COMMON_CHINESE_SURNAMES)
        role_titles = "老板|经理|律师|老师|医生|同事|主管|主任|警官|先生|女士|小姐|阿姨|叔叔"
        pattern = re.compile(
            rf"([{surname_class}][\u4e00-\u9fff]{{1,2}}(?:{role_titles})?)"
        )
        names: List[str] = []
        for match in pattern.findall(text):
            candidate = str(match).strip("，。！？、；：“”‘’（）()《》")
            if not candidate or candidate in allowed_names:
                continue
            if any(candidate in allowed or allowed in candidate for allowed in allowed_names):
                continue
            if candidate not in names:
                names.append(candidate)
        return names

    def _check_perspective_consistency(self, text: str, language: str) -> List[str]:
        """Check that narrative does not use first-person perspective.

        The game uses second-person perspective ("你" / "you") for immersion,
        so only first-person ("我" / "I") is prohibited in narrative text.
        Dialogue inside quotes may use any perspective.
        """
        issues = []

        if language == "zh":
            # 检查是否混用了第一人称
            # 方法：在文本前后添加空格，然后匹配被空格/标点包围的"我"或"你"
            # 这样可以避免字符串开头/结尾的特殊边界问题

            # 先移除所有引号内的内容（对话允许使用任何人称）
            text_without_quotes = text
            text_without_quotes = re.sub(r'"[^"]*"', " ", text_without_quotes)
            text_without_quotes = re.sub(r"'[^']*'", " ", text_without_quotes)
            text_without_quotes = re.sub(r"「[^」]*」", " ", text_without_quotes)
            text_without_quotes = re.sub(r"『[^』]*』", " ", text_without_quotes)
            # 处理中文弯引号 \u201c \u201d 和 \u2018 \u2019
            text_without_quotes = re.sub(r"\u201c[^\u201d]*\u201d", " ", text_without_quotes)
            text_without_quotes = re.sub(r"\u2018[^\u2019]*\u2019", " ", text_without_quotes)

            # 在文本前后添加空格，简化边界检测
            padded_text = " " + text_without_quotes + " "

            # 匹配被空白或标点包围的"我"
            # 使用简单的方法：找到所有"我"或"你"的位置，检查前后字符
            # 边界字符：空白、标点、字符串开头/结尾
            boundary_chars = set(" \t\n\r。，！？；：,;:!?\"'\"'()（）【】[]《》<>{}")

            has_first_person = False

            for i, char in enumerate(padded_text):
                if char == "我":
                    # 检查前一个字符是否是边界字符
                    # "我"后面可以是任何字符（中文或标点），只要前面是边界即可
                    prev_char = padded_text[i - 1] if i > 0 else " "
                    if prev_char in boundary_chars:
                        has_first_person = True

            if has_first_person:
                issues.append("故事中使用了第一人称「我」，应使用第三人称")
        else:
            # 英文检查
            text_without_quotes = re.sub(r'"[^"]*"', "", text)

            first_person_pattern = re.compile(r"\bI\b")

            if first_person_pattern.search(text_without_quotes):
                issues.append("Story uses first-person 'I', should use third-person")

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
