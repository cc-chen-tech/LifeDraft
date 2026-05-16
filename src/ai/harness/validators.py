"""约束验证函数集合。

每个验证函数签名统一为:
    (story_text: str, context: dict) -> tuple[bool, str, dict]
返回值: (是否通过, 失败证据描述, 详细信息dict)

所有函数仅依赖 Python 标准库 + re，不使用外部 NLP 库。
"""

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# CRITICAL 级别验证函数
# ============================================================


def validate_available_people(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """检查故事中是否使用了可用人物列表外的人名。

    通过匹配上下文中提供的已知人名列表，统计哪些人名在故事中被提及。
    基础版本不做 NER（命名实体识别），仅检查已知人名的出现情况。
    """
    available_people = context.get("available_people", [])
    if not available_people:
        return True, "", {"skipped": True, "reason": "no available_people in context"}

    available_set = set(available_people)

    # 统计已知人名在故事中的出现情况
    mentioned_people: list = []
    for person in available_set:
        if person in story_text:
            mentioned_people.append(person)

    # 基础版本：已知人名检查通过即可
    # 完整版本需要 NER 来检测未知人名，此处先返回 True
    return True, "", {"mentioned_people": mentioned_people}


def validate_third_person(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """检查故事是否使用第三人称叙事（不应有大量"我"、"我们"作为主角视角）。

    策略：统计不在引号/对话内的第一人称句子占比，超过阈值则判定失败。
    """
    first_person_count = 0
    sentences = re.split(r"[。！？\n]", story_text)
    total_sentences = len([s for s in sentences if s.strip()])

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        # 排除在引号内的句子（对话中的"我"是合理的）
        if re.match(r'^[""「『]', sentence):
            continue
        # 检查以第一人称动词开头的非对话句
        if re.match(
            r"^[^"
            "「『]*我(?:想|觉得|认为|决定|走|看|说|听|感到|发现|知道|明白|记得|需要|必须|应该|可以|能|会|要|把|被|在|从|向|对|给|跟|和)",
            sentence,
        ):
            first_person_count += 1

    # 非对话中第一人称占比超过 30% 则可能不是第三人称
    if total_sentences > 0 and first_person_count / max(total_sentences, 1) > 0.3:
        return (
            False,
            f"检测到过多第一人称叙事（{first_person_count}处，共{total_sentences}句），"
            f"可能不是第三人称",
            {
                "first_person_count": first_person_count,
                "total_sentences": total_sentences,
            },
        )

    return True, "", {}


def validate_no_meta_narration(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """检查是否存在跳脱叙事（打破第四面墙）。

    检测关键词：提及 AI/系统/游戏机制/作者旁白等元叙述内容。
    """
    meta_patterns = [
        r"作为(?:一个)?AI",
        r"作为(?:一个)?人工智能",
        r"这个故事",
        r"这段故事",
        r"本故事",
        r"根据(?:你的|用户|玩家)(?:要求|指令|设定)",
        r"在(?:这个|我们的)(?:游戏|模拟|系统)",
        r"(?:游戏|系统)(?:设定|规则|机制)",
        r"(?:我|让我)(?:来)?(?:为你|给你)(?:写|生成|创作)",
        r"接下来(?:的故事|我会)",
        r"(?:精力值|情绪值|学识值|财富值|属性值)",
    ]

    violations: list = []
    for pattern in meta_patterns:
        matches = re.finditer(pattern, story_text)
        for match in matches:
            start = max(0, match.start() - 20)
            end = min(len(story_text), match.end() + 20)
            violations.append(story_text[start:end])

    if violations:
        return (
            False,
            f"检测到跳脱叙事：{violations[0]}",
            {"violations": violations[:5]},
        )

    return True, "", {}


def validate_decision_point_ending(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """检查故事结尾是否包含决策点。

    取末尾 300 字，检测是否含有选择/决策/抉择相关词汇。
    """
    ending = story_text[-300:] if len(story_text) > 300 else story_text

    decision_indicators = [
        r"面临",
        r"抉择",
        r"选择",
        r"该如何",
        r"怎么办",
        r"两条路",
        r"两个选择",
        r"犹豫",
        r"权衡",
        r"是.*还是",
        r"要不要",
        r"应该",
        r"能否",
        r"机会",
        r"决定",
        r"何去何从",
        r"十字路口",
        r"两难",
        r"思忖",
        r"考虑着",
        r"盘算",
        r"怎么样",
        r"你说呢",
        r"拿主意",
        r"自己选",
    ]

    found_indicators: list = []
    for pattern in decision_indicators:
        if re.search(pattern, ending):
            found_indicators.append(pattern)

    if len(found_indicators) >= 1:
        return True, "", {"indicators_found": found_indicators}

    return (
        False,
        "故事结尾未检测到明确的决策点或选择时刻",
        {"ending_excerpt": ending[-100:]},
    )


def validate_overdue_storylines(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """检查 overdue 剧情线是否在故事中被提及。

    遍历上下文中的 overdue_storylines，提取每条剧情线的关键词，
    检查这些关键词是否至少有一个出现在故事文本中。
    """
    overdue = context.get("overdue_storylines", [])
    if not overdue:
        return True, "", {"skipped": True, "reason": "no overdue storylines"}

    not_mentioned: list = []
    mentioned: list = []
    for storyline in overdue:
        desc = storyline.get("description", "")
        # 同时考虑关联人物名
        related_chars = storyline.get("related_characters", [])
        keywords = _extract_storyline_keywords(desc)
        keywords.extend(related_chars)

        # 检查是否至少有一个关键词（长度 >= 2）出现在故事中
        found = any(kw in story_text for kw in keywords if len(kw) >= 2)
        if found:
            mentioned.append(desc[:50])
        else:
            not_mentioned.append(desc[:50])

    if not_mentioned:
        return (
            False,
            f"以下overdue剧情线未在故事中提及: {not_mentioned}",
            {"not_mentioned": not_mentioned, "mentioned": mentioned},
        )

    return True, "", {"mentioned": mentioned}


def validate_no_fabrication(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """检查是否编造了未记录的过往事件（基础规则版本）。

    检测故事中是否引用了"上次"、"之前"、"曾经"等回忆性表述。
    基础版本只记录潜在回忆引用，不直接判定失败，需 LLM 二次验证。
    """
    recall_patterns = [
        r"(?:上次|上回|之前|曾经|那次|那天)(?:的|那个)?(?:事|约定|承诺|谈话|会面)",
        r"记得(?:上次|之前|那次)",
        r"(?:上个月|上周|前几天)(?:的|那个)?(?:事|约定|承诺)",
    ]

    recalls: list = []
    for pattern in recall_patterns:
        matches = re.finditer(pattern, story_text)
        for match in matches:
            start = max(0, match.start() - 30)
            end = min(len(story_text), match.end() + 30)
            recalls.append(story_text[start:end])

    # 基础版本：记录潜在回忆引用，不直接判定失败
    # 完整版本需与 established_facts 交叉比对
    if recalls:
        return (
            True,
            "",
            {
                "potential_recalls": recalls[:5],
                "note": "需LLM二次验证",
            },
        )

    return True, "", {}


def validate_established_facts(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """检查故事是否与已建立事实矛盾（基础关键词版本）。

    完整的矛盾检测需要 LLM 语义理解，此处仅提供基础统计。
    """
    facts = context.get("established_facts", [])
    if not facts:
        return True, "", {"skipped": True, "reason": "no established_facts in context"}

    # 基础实现：统计事实数量，完整验证需 LLM 支持
    return (
        True,
        "",
        {
            "facts_count": len(facts),
            "note": "基础版本，完整矛盾验证需LLM支持",
        },
    )


# ============================================================
# HIGH 级别验证函数
# ============================================================


def validate_scene_continuity(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """检查场景是否与上一轮结尾地点连贯。

    检查故事开头 200 字是否提及上一个地点或包含合理的移动/过渡描写。
    """
    last_location = context.get("last_location", "")
    if not last_location:
        return True, "", {"skipped": True, "reason": "no last_location in context"}

    opening = story_text[:200] if len(story_text) > 200 else story_text

    # 检查地点名是否出现在开头
    if last_location in opening:
        return True, "", {"location_found_in_opening": True}

    # 检查是否有移动/过渡描写
    transition_patterns = [
        r"离开",
        r"前往",
        r"来到",
        r"走出",
        r"走进",
        r"回到",
        r"赶往",
        r"踏入",
        r"步入",
        r"抵达",
        r"路上",
        r"途中",
        r"驱车",
        r"骑马",
        r"乘",
    ]
    has_transition = any(re.search(p, opening) for p in transition_patterns)

    if has_transition:
        return True, "", {"has_transition": True}

    return (
        False,
        f"故事开头未提及上一场景地点'{last_location}'且无过渡描述",
        {"last_location": last_location, "opening_excerpt": opening[:100]},
    )


def validate_high_storylines(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """检查高重要性剧情线是否在故事中被涉及。"""
    high_storylines = context.get("high_storylines", [])
    if not high_storylines:
        return True, "", {"skipped": True, "reason": "no high_storylines in context"}

    mentioned: list = []
    not_mentioned: list = []
    for storyline in high_storylines:
        desc = storyline.get("description", "")
        related_chars = storyline.get("related_characters", [])
        keywords = _extract_storyline_keywords(desc)
        keywords.extend(related_chars)

        found = any(kw in story_text for kw in keywords if len(kw) >= 2)
        if found:
            mentioned.append(desc[:50])
        else:
            not_mentioned.append(desc[:50])

    # 至少涉及一条高重要性剧情线即通过
    if mentioned:
        return True, "", {"mentioned": mentioned, "not_mentioned": not_mentioned}

    return (
        False,
        f"未涉及任何高重要性剧情线: {[s[:30] for s in not_mentioned[:3]]}",
        {"not_mentioned": not_mentioned},
    )


def validate_character_consistency(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """检查角色性格一致性（基础版本）。

    完整验证需要 LLM 语义理解，此处仅提供占位实现。
    """
    character_traits = context.get("character_traits", {})
    if not character_traits:
        return True, "", {"skipped": True, "reason": "no character_traits in context"}

    return True, "", {"note": "基础版本，完整性格一致性验证需LLM支持"}


# ============================================================
# MEDIUM 级别验证函数
# ============================================================


def validate_character_habits(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """检查人物习惯是否在故事中有所体现（基础版本）。"""
    habits = context.get("character_habits", [])
    if not habits:
        return True, "", {"skipped": True, "reason": "no character_habits in context"}

    # 基础检查：统计习惯关键词出现情况
    reflected_count = 0
    for habit in habits:
        habit_text = habit.get("habit", "")
        keywords = _extract_storyline_keywords(habit_text)
        if any(kw in story_text for kw in keywords if len(kw) >= 2):
            reflected_count += 1

    return (
        True,
        "",
        {
            "total_habits": len(habits),
            "reflected_count": reflected_count,
            "note": "基础版本，仅统计关键词匹配",
        },
    )


def validate_foreshadowing(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """检查伏笔回响是否被编织进故事（基础版本）。"""
    activated_seed = context.get("activated_seed")
    if not activated_seed:
        return True, "", {"skipped": True, "reason": "no activated_seed in context"}

    desc = activated_seed.get("description", "")
    keywords = _extract_storyline_keywords(desc)
    related_chars = activated_seed.get("related_characters", [])
    keywords.extend(related_chars)

    found_keywords = [kw for kw in keywords if len(kw) >= 2 and kw in story_text]

    if found_keywords:
        return True, "", {"found_keywords": found_keywords}

    return (
        False,
        f"伏笔'{desc[:30]}'的相关关键词未在故事中出现",
        {"seed_description": desc[:50], "keywords_checked": keywords},
    )


def validate_medium_storylines(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """检查中重要性剧情线涉及情况（仅统计，不判定失败）。"""
    medium_storylines = context.get("medium_storylines", [])
    if not medium_storylines:
        return True, "", {"skipped": True, "reason": "no medium_storylines in context"}

    mentioned: list = []
    for storyline in medium_storylines:
        desc = storyline.get("description", "")
        keywords = _extract_storyline_keywords(desc)
        if any(kw in story_text for kw in keywords if len(kw) >= 2):
            mentioned.append(desc[:50])

    # 中等优先级：仅统计，不判定失败
    return (
        True,
        "",
        {
            "total": len(medium_storylines),
            "mentioned_count": len(mentioned),
            "mentioned": mentioned,
        },
    )


def validate_logic_constraints(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """检查时间逻辑一致性（基础版本）。

    检测明显的季节/时间矛盾。
    """
    season = context.get("season", "")
    if not season:
        return True, "", {"skipped": True, "reason": "no season in context"}

    # 季节与描写矛盾检测
    season_conflicts = {
        "春": [r"大雪纷飞", r"寒风刺骨", r"冰天雪地", r"酷暑难耐", r"烈日炎炎"],
        "夏": [r"大雪纷飞", r"寒风刺骨", r"冰天雪地", r"春暖花开", r"万物复苏"],
        "秋": [r"大雪纷飞", r"冰天雪地", r"春暖花开", r"酷暑难耐", r"烈日炎炎"],
        "冬": [r"春暖花开", r"万物复苏", r"酷暑难耐", r"烈日炎炎", r"绿树成荫"],
    }

    conflicts = season_conflicts.get(season, [])
    found_conflicts: list = []
    for pattern in conflicts:
        if re.search(pattern, story_text):
            found_conflicts.append(pattern)

    if found_conflicts:
        return (
            False,
            f"季节为{season}季，但出现了矛盾描写: {found_conflicts}",
            {"season": season, "conflicts": found_conflicts},
        )

    return True, "", {"season": season}


# ============================================================
# LOW 级别验证函数
# ============================================================


def validate_anti_repetition(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """检查故事内部是否有明显的重复段落。"""
    # 按句子切分，检查是否有完全相同的长句重复出现
    sentences = [
        s.strip() for s in re.split(r"[。！？\n]", story_text) if len(s.strip()) >= 15
    ]

    seen: dict = {}
    duplicates: list = []
    for s in sentences:
        if s in seen:
            seen[s] += 1
            if seen[s] == 2:  # 只记录首次发现重复
                duplicates.append(s[:40])
        else:
            seen[s] = 1

    if duplicates:
        return (
            False,
            f"故事中存在重复段落: {duplicates[0]}...",
            {"duplicates": duplicates[:5]},
        )

    return True, "", {}


def validate_vector_context(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """检查历史上下文参考情况（仅统计，不判定失败）。"""
    vector_context = context.get("vector_context", "")
    if not vector_context:
        return True, "", {"skipped": True, "reason": "no vector_context in context"}

    # 仅统计是否有向量检索上下文
    return True, "", {"has_vector_context": True, "context_length": len(vector_context)}


# ============================================================
# 辅助函数
# ============================================================


def _extract_storyline_keywords(description: str) -> List[str]:
    """从剧情线描述中提取关键词。

    移除常见虚词，保留有意义的名词和动词短语。
    """
    stop_words = {
        "的",
        "了",
        "在",
        "是",
        "和",
        "与",
        "被",
        "将",
        "要",
        "会",
        "到",
        "从",
        "对",
        "向",
        "把",
        "让",
        "给",
        "也",
        "都",
        "又",
        "已",
        "还",
        "就",
        "而",
        "但",
        "却",
        "只",
        "更",
        "很",
        "最",
        "不",
    }

    # 按标点和空格分割
    segments = re.split(r"[，。！？、；：\s]+", description)
    keywords: list = []
    for seg in segments:
        if len(seg) >= 2 and seg not in stop_words:
            keywords.append(seg)

    return keywords
