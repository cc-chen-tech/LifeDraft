"""Quick rule-based validator for story consistency.

This validator performs fast checks without AI calls, reducing latency
before the optional AI-based consistency validation.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.ai.harness.era_validator import validate_era_consistency
from src.game.relationship_authority import extract_required_key_people

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
            required_key_people = self._extract_required_key_people_names(character_settings)
            cast_drift_issues = self._check_key_people_cast_drift(
                story_text,
                available_people,
                language,
                required_key_people=required_key_people,
            )
            issues.extend(cast_drift_issues)

        # 3. 检查人称一致性
        perspective_issues = self._check_perspective_consistency(story_text, language)
        issues.extend(perspective_issues)

        # 4. 检查时代一致性，包括现代设定被漂移成古代叙事的反向错误。
        era_context = self.extract_era_context(character_settings)
        if era_context.get("era") or era_context.get("era_type"):
            era_passed, era_evidence, _ = validate_era_consistency(story_text, era_context)
            if not era_passed and era_evidence:
                issues.append(era_evidence)

        # 5. 检查现代故事标题是否回退到章回体。
        title_issues = self._check_modern_chapter_title(story_text, era_context, language)
        issues.extend(title_issues)

        passed = len(issues) == 0
        result = QuickValidationResult(passed=passed, issues=issues, warnings=warnings)

        if issues:
            logger.info(f"Quick validation found {len(issues)} issues: {issues}")
        if warnings:
            logger.info(f"Quick validation warnings: {warnings}")

        return result

    @classmethod
    def extract_era_context(
        cls,
        character_settings: Optional[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Extract a compact era validation context from character settings."""
        if not isinstance(character_settings, dict):
            return {"era": "", "era_type": ""}

        era_value = character_settings.get("era")
        era_text = cls._first_text(
            era_value,
            [
                "era_description",
                "era_name",
                "name",
                "description",
                "world_context",
                "period",
                "year",
            ],
        )
        era_context_text = cls._joined_text(era_value)
        world_context_text = cls._joined_text(character_settings.get("world"))
        combined = " ".join(
            part
            for part in [
                era_text,
                era_context_text,
                world_context_text,
                cls._joined_text(character_settings),
            ]
            if part
        )
        return {
            "era": era_text or combined[:80],
            "era_type": cls._infer_era_type(combined),
        }

    @staticmethod
    def _first_text(value: Any, keys: List[str]) -> str:
        if isinstance(value, dict):
            for key in keys:
                item = value.get(key)
                if item is not None and str(item).strip():
                    return str(item).strip()
            return ""
        if value is not None and str(value).strip():
            return str(value).strip()
        return ""

    @classmethod
    def _joined_text(cls, value: Any) -> str:
        if isinstance(value, dict):
            return " ".join(cls._joined_text(item) for item in value.values() if item is not None)
        if isinstance(value, list):
            return " ".join(cls._joined_text(item) for item in value if item is not None)
        if value is not None:
            return str(value)
        return ""

    @staticmethod
    def _infer_era_type(text: str) -> str:
        cyberpunk_keywords = [
            "赛博朋克",
            "cyberpunk",
            "高科技低生活",
        ]
        lowered_text = text.lower()
        if any(keyword in lowered_text for keyword in cyberpunk_keywords):
            return "cyberpunk"

        ancient_keywords = [
            "古代",
            "唐",
            "宋",
            "元",
            "明",
            "清",
            "汉",
            "秦",
            "周",
            "长安",
            "洛阳",
            "南宋",
            "北宋",
            "medieval",
            "ancient",
            "dynasty",
            "historic",
        ]
        modern_keywords = [
            "现代",
            "当代",
            "未来",
            "2020",
            "2021",
            "2022",
            "2023",
            "2024",
            "2025",
            "2026",
            "互联网",
            "公司",
            "职场",
            "创业",
            "都市",
            "上海",
            "游戏制作",
            "独立游戏",
            "modern",
            "contemporary",
            "startup",
        ]

        if any(keyword in text for keyword in ancient_keywords):
            return "ancient"
        if any(keyword in text for keyword in modern_keywords):
            return "modern"
        return ""

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
        self,
        text: str,
        available_people: List[str],
        language: str,
        required_key_people: Optional[List[str]] = None,
    ) -> List[str]:
        """Detect severe drift where key people disappear and a new named cast appears."""
        allowed_names = [name.strip() for name in available_people if name and name.strip()]
        key_people_names = [
            name.strip()
            for name in (required_key_people or allowed_names)
            if name and name.strip()
        ]
        if len(key_people_names) < 2:
            return []

        present_key_people = [name for name in key_people_names if name in text]

        if language != "zh":
            if present_key_people:
                return []
            return [
                "上一版故事完全没有使用预设关键人物；请至少使用一个可用人物列表中的关键人物，并避免凭空替换关系网络。"
            ]

        invented_names = self._extract_likely_chinese_person_names(text, allowed_names)
        if present_key_people:
            key_people_ratio = len(present_key_people) / len(key_people_names)
            required_network_count = (len(key_people_names) * 4 + 4) // 5
            if (
                len(key_people_names) >= 3
                and len(invented_names) >= 3
                and len(present_key_people) < required_network_count
            ):
                return [
                    "上一版故事预设关键人物使用不足，预设关系网使用不足"
                    f"（已使用{len(present_key_people)}/{len(key_people_names)}，要求多人关系戏至少80%）"
                    "，反而让名单外人物主导剧情"
                    f"（{ '、'.join(invented_names[:5]) }）；请围绕预设关键人物关系网重写。"
                ]
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

    def _extract_required_key_people_names(
        self,
        character_settings: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Return preset relationship key people, excluding family/background people."""
        if not isinstance(character_settings, dict):
            return []
        return [
            person["name"]
            for person in extract_required_key_people(character_settings)
            if person.get("name")
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

    def _check_modern_chapter_title(
        self,
        text: str,
        era_context: Dict[str, str],
        language: str,
    ) -> List[str]:
        """Reject classical chapter-title openings in modern Chinese stories."""
        if language != "zh" or era_context.get("era_type") != "modern":
            return []

        opening = text.lstrip()[:80]
        match = re.match(r"第[一二三四五六七八九十百千万两0-9]+回(?:\s|[，。！？：:、]|$)", opening)
        if not match:
            return []

        return [
            "现代故事开头使用了章回体标题"
            f"「{match.group(0).strip()}」；请使用现代时间线标题"
            "（如“第3周·周一 会议室复盘”），不要使用“第X回”。"
        ]


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
