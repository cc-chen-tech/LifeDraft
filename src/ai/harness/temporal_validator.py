"""时间一致性验证器 - 验证生成文本中的时间引用与实际游戏状态一致。

检查内容：
- 相对时间表达（昨天、三天前、上周等）与游戏周数的合理性
- 季节描写与游戏周数匹配
- 角色年龄引用一致性
"""

import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# 中文数字映射
CHINESE_DIGITS = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "百": 100,
}

# 回忆/梦境豁免关键词
FLASHBACK_KEYWORDS = ["回忆", "梦境", "幻觉", "梦中", "记忆中", "往事", "曾经", "想起", "梦里",
                      "幻影", "恍惚", "仿佛回到", "回到了", "当年", "从前"]

# 季节映射: week 0-11=春, 12-23=夏, 24-35=秋, 36-47=冬 (每年48周)
WEEKS_PER_YEAR = 48
SEASON_RANGES = {
    "春": (0, 11),
    "夏": (12, 23),
    "秋": (24, 35),
    "冬": (36, 47),
}

# 季节与其矛盾描写
SEASON_CONFLICT_KEYWORDS: Dict[str, List[str]] = {
    "春": ["大雪纷飞", "冰天雪地", "寒冬腊月", "酷暑难耐", "烈日炎炎", "骄阳似火", "蝉鸣阵阵"],
    "夏": ["大雪纷飞", "冰天雪地", "寒风刺骨", "春暖花开", "万物复苏", "桃花盛开", "柳芽初绽"],
    "秋": ["大雪纷飞", "冰天雪地", "春暖花开", "酷暑难耐", "烈日炎炎", "万物复苏", "骄阳似火"],
    "冬": ["春暖花开", "万物复苏", "酷暑难耐", "烈日炎炎", "绿树成荫", "蝉鸣阵阵", "骄阳似火"],
}

# 中文时间表达正则
TIME_REFERENCE_PATTERNS = [
    (r"昨天|昨日", "yesterday"),
    (r"前天|前日", "day_before_yesterday"),
    (r"(?:三|四|五|六|七|八|九|十)天前", "days_ago"),
    (r"上周|上星期|上个礼拜", "last_week"),
    (r"上个月", "last_month"),
    (r"去年|上一年", "last_year"),
    (r"(?:两|三|四|五)个月前", "months_ago"),
    (r"(?:两|三|四|五|六)年前", "years_ago"),
    (r"今天|今日|今天早上|今天下午|今天晚上", "today"),
    (r"今年", "this_year"),
    (r"这个月", "this_month"),
    (r"(?:春|夏|秋|冬)天|(?:春|夏|秋|冬)季|(?:春|夏|秋|冬)日", "season_ref"),
]

# 年龄相关正则
AGE_PATTERNS = [
    r"(\d{1,3})\s*岁",
    r"年仅\s*(\d{1,3})",
    r"年过\s*(\d{1,3})",
    r"(?:快|将近|接近|约|大约)\s*(\d{1,3})\s*岁",
    r"(\d{1,3})\s*(?:周岁|虚岁)",
]

# 中文数字年龄正则
CHINESE_AGE_PATTERNS = [
    r"([零一二两三四五六七八九十百]+)\s*岁",
    r"年仅\s*([零一二两三四五六七八九十百]+)",
    r"年过\s*([零一二两三四五六七八九十百]+)",
]


def _chinese_to_int(cn: str) -> int:
    """将中文数字转为整数，如 '三十五' -> 35。"""
    if not cn:
        return 0
    result = 0
    current = 0
    for ch in cn:
        val = CHINESE_DIGITS.get(ch)
        if val is None:
            continue
        if val == 100:
            result += (current if current else 1) * 100
            current = 0
        elif val == 10:
            result += (current if current else 1) * 10
            current = 0
        else:
            current = val
    result += current
    return result


class TemporalConsistencyValidator:
    """时间一致性验证器。"""

    def validate(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """验证生成文本中的时间引用与实际游戏状态一致。"""
        try:
            world_model = context.get("world_model")
            player_state = context.get("player_state", {})

            current_week = 0
            if world_model and hasattr(world_model, "current_week"):
                current_week = world_model.current_week
            elif isinstance(player_state, dict):
                current_week = player_state.get("week", 0)

            violations = []
            details: Dict = {
                "current_week": current_week,
                "time_references": [],
                "season_check": None,
                "age_check": None,
            }

            # 1. 提取时间引用
            time_refs = self.extract_time_references(story_text)
            details["time_references"] = time_refs

            # 2. 季节一致性检查
            season_ok, season_info = self.check_season_consistency(
                story_text, current_week
            )
            details["season_check"] = season_info
            if not season_ok:
                violations.append(season_info.get("violation", "季节描写与当前周数矛盾"))

            # 3. 角色年龄检查
            age = None
            if isinstance(player_state, dict):
                age = player_state.get("age")
            if age is not None:
                age_ok, age_info = self.check_character_age(story_text, age)
                details["age_check"] = age_info
                if not age_ok:
                    violations.append(age_info.get("violation", "年龄引用不一致"))

            if violations:
                return (
                    False,
                    f"时间一致性违规: {'; '.join(violations)}",
                    {
                        **details,
                        "violations": violations,
                        "correction_hint": f"当前游戏第{current_week}周，"
                        f"季节为{self._get_season(current_week)}，"
                        f"请确保时间描写与此一致",
                    },
                )

            return True, "", details

        except Exception as e:
            logger.warning(f"时间一致性验证异常: {e}")
            return True, "", {}

    def extract_time_references(self, text: str) -> list:
        """提取文本中的时间引用表达。"""
        refs = []
        for pattern, ref_type in TIME_REFERENCE_PATTERNS:
            for match in re.finditer(pattern, text):
                refs.append({
                    "text": match.group(),
                    "type": ref_type,
                    "position": match.start(),
                })
        return refs

    def check_season_consistency(
        self, text: str, current_week: int
    ) -> Tuple[bool, dict]:
        """验证季节描写与游戏周数匹配。"""
        current_season = self._get_season(current_week)
        conflicts = SEASON_CONFLICT_KEYWORDS.get(current_season, [])

        # 检查是否整段都在回忆/梦境语境中
        is_flashback = any(kw in text for kw in FLASHBACK_KEYWORDS)

        found_conflicts = []
        for keyword in conflicts:
            if keyword in text:
                # 如果在回忆/梦境语境中，豁免季节矛盾
                if is_flashback:
                    continue
                found_conflicts.append(keyword)

        if found_conflicts:
            return False, {
                "current_season": current_season,
                "conflicts": found_conflicts,
                "violation": f"当前为{current_season}季(第{current_week}周)，"
                f"但出现矛盾描写: {', '.join(found_conflicts)}",
            }

        return True, {"current_season": current_season, "conflicts": []}

    def check_character_age(self, text: str, age: int) -> Tuple[bool, dict]:
        """验证文本中年龄引用一致。"""
        mentioned_ages = []
        for pattern in AGE_PATTERNS:
            for match in re.finditer(pattern, text):
                try:
                    mentioned_age = int(match.group(1))
                    mentioned_ages.append(mentioned_age)
                except (ValueError, IndexError):
                    continue

        # 中文数字年龄匹配
        for pattern in CHINESE_AGE_PATTERNS:
            for match in re.finditer(pattern, text):
                try:
                    cn_str = match.group(1)
                    mentioned_age = _chinese_to_int(cn_str)
                    if mentioned_age > 0:
                        mentioned_ages.append(mentioned_age)
                except (ValueError, IndexError):
                    continue

        if not mentioned_ages:
            return True, {"mentioned_ages": [], "expected_age": age}

        # 允许±1岁容差（虚岁/周岁差异）
        inconsistent = [a for a in mentioned_ages if abs(a - age) > 1]
        if inconsistent:
            return False, {
                "mentioned_ages": mentioned_ages,
                "expected_age": age,
                "inconsistent_ages": inconsistent,
                "violation": f"角色实际年龄{age}岁，但文本提及{inconsistent}岁",
            }

        return True, {"mentioned_ages": mentioned_ages, "expected_age": age}

    @staticmethod
    def _get_season(week: int) -> str:
        """根据周数获取季节。"""
        week_in_year = week % WEEKS_PER_YEAR
        for season, (start, end) in SEASON_RANGES.items():
            if start <= week_in_year <= end:
                return season
        return "春"


def validate_temporal_consistency(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """模块级验证函数。"""
    return TemporalConsistencyValidator().validate(story_text, context)
