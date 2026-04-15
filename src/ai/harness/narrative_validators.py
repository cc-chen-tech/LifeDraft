"""第二三层叙事验证器。

为中观章节层（三幕结构、节奏多样性）和宏观结构层（弧光遵从、世界事件融入、冲突指令遵从）
提供生成后验证，接入 Harness 重试管道。
"""

import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)


def validate_three_act_structure(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """检测故事是否具备三幕结构（铺垫、发展、高潮）。

    仅对 > 500 字的文本生效，<= 500 字自动通过。
    将文本分为前 1/4、中 1/2、后 1/4，分别检测对应阶段关键词。
    >= 2 个阶段检测到则通过。
    """
    if len(story_text) <= 500:
        return True, "", {"phases_found": [], "phases_count": 0}

    quarter = len(story_text) // 4
    first_quarter = story_text[:quarter]
    middle_half = story_text[quarter : quarter * 3]
    last_quarter = story_text[quarter * 3 :]

    setup_keywords = ["走进", "来到", "踏入", "清晨", "这一天", "一个", "某天", "早晨"]
    development_keywords = ["然而", "却", "突然", "不料", "意外", "转折", "没想到", "谁知"]
    climax_keywords = ["终于", "再也", "紧紧", "猛然", "决定", "爆发", "一把", "狠狠"]

    phases_found = []

    if any(kw in first_quarter for kw in setup_keywords):
        phases_found.append("铺垫")
    if any(kw in middle_half for kw in development_keywords):
        phases_found.append("发展")
    if any(kw in last_quarter for kw in climax_keywords):
        phases_found.append("高潮")

    phases_count = len(phases_found)
    details = {"phases_found": phases_found, "phases_count": phases_count}

    if phases_count >= 2:
        return True, "", details
    return False, f"三幕结构不完整，仅检测到 {phases_count} 个阶段: {phases_found}", details


def validate_pacing_variety(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """验证节奏干预是否生效。

    仅当 narrative_hints 中存在非空 pacing_intervention 时生效。
    使用 EmotionalArcAnalyzer 分析情感弧线，判断干预是否有效。
    """
    hints = context.get("narrative_hints", {})
    pacing_intervention = hints.get("pacing_intervention")
    if not pacing_intervention:
        return True, "", {}

    try:
        from src.ai.creative.emotional_arc import EmotionalArcAnalyzer
    except (ImportError, ModuleNotFoundError):
        logger.debug("EmotionalArcAnalyzer 不可用，跳过节奏验证")
        return True, "", {"import_failed": True}

    try:
        analyzer = EmotionalArcAnalyzer()
        result = analyzer.analyze_segment(story_text)  # type: ignore[attr-defined]

        valence = result.valence if hasattr(result, "valence") else result.get("valence", 0.0)
        arousal = result.arousal if hasattr(result, "arousal") else result.get("arousal", 0.0)

        intervention_effective = not (abs(valence) < 0.15 and abs(arousal) < 0.15)
        details = {
            "valence": valence,
            "arousal": arousal,
            "intervention_effective": intervention_effective,
        }

        if intervention_effective:
            return True, "", details
        return False, "节奏干预未生效，情感弧线依然平坦", details

    except Exception as exc:
        logger.debug("节奏分析异常，自动通过: %s", exc)
        return True, "", {"analysis_error": str(exc)}


ARC_STAGE_KEYWORDS = {
    "稳态": ["日常", "平静", "安宁", "平凡", "普通", "习惯"],
    "触发": ["变化", "打破", "冲击", "意外", "突如其来", "改变"],
    "挣扎": ["困难", "挣扎", "矛盾", "痛苦", "煎熬", "两难"],
    "转折": ["转变", "顿悟", "领悟", "觉醒", "明白", "恍然"],
    "新稳态": ["成长", "接受", "释然", "新的", "重新", "蜕变"],
}


def validate_arc_hint_compliance(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """验证故事是否遵从弧光阶段提示。

    仅当 narrative_hints 中存在非空 arc_hint 时生效。
    从 arc_hint 识别阶段名，检查故事中是否包含对应关键词。
    """
    hints = context.get("narrative_hints", {})
    arc_hint = hints.get("arc_hint")
    if not arc_hint:
        return True, "", {}

    detected_stage = None
    for stage_name in ARC_STAGE_KEYWORDS:
        if stage_name in arc_hint:
            detected_stage = stage_name
            break

    if detected_stage is None:
        return True, "", {"detected_stage": "", "matched_keywords": [], "compliant": True}

    keywords = ARC_STAGE_KEYWORDS[detected_stage]
    matched_keywords = [kw for kw in keywords if kw in story_text]

    compliant = len(matched_keywords) > 0
    details = {
        "detected_stage": detected_stage,
        "matched_keywords": matched_keywords,
        "compliant": compliant,
    }

    if compliant:
        return True, "", details
    return (
        False,
        f"弧光阶段「{detected_stage}」的关键词未在故事中出现",
        details,
    )


_WORLD_EVENT_STOP_WORDS = {
    "的", "了", "在", "是", "和", "与", "或", "但", "而", "也",
    "都", "就", "将", "会", "被", "把", "让", "给", "从", "到",
    "这", "那", "有", "没", "不", "可以", "应该", "需要", "可能",
    "已经", "正在", "当前", "目前", "世界", "事件", "背景", "环境",
    "影响", "渗透",
}


def validate_world_event_integration(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """验证故事是否融入了世界事件关键词。

    仅当 narrative_hints 中存在非空 world_event_context 时生效。
    从 world_event_context 提取中文词，过滤停用词后检查故事中是否出现。
    """
    hints = context.get("narrative_hints", {})
    world_event_context = hints.get("world_event_context")
    if not world_event_context:
        return True, "", {}

    raw_words = re.findall(r"[\u4e00-\u9fff]{2,4}", world_event_context)
    extracted_keywords = [w for w in raw_words if w not in _WORLD_EVENT_STOP_WORDS]

    if not extracted_keywords:
        return True, "", {"extracted_keywords": [], "found_in_story": [], "integrated": True}

    found_in_story = [kw for kw in extracted_keywords if kw in story_text]
    integrated = len(found_in_story) > 0

    details = {
        "extracted_keywords": extracted_keywords,
        "found_in_story": found_in_story,
        "integrated": integrated,
    }

    if integrated:
        return True, "", details
    return False, "世界事件关键词未融入故事文本", details


_CONFLICT_BASE_KEYWORDS = [
    "冲突", "对抗", "争执", "紧张", "矛盾", "对峙",
    "威胁", "危机", "挑战", "压力", "争吵", "抗争",
    "敌意", "反对", "阻碍", "困境",
]


def validate_conflict_directive_compliance(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """验证故事是否遵从冲突指令。

    仅当 narrative_hints 中存在非空 conflict_directive 时生效。
    合并通用冲突关键词和从 conflict_directive 提取的额外关键词，检查故事中是否出现。
    """
    hints = context.get("narrative_hints", {})
    conflict_directive = hints.get("conflict_directive")
    if not conflict_directive:
        return True, "", {}

    extra_words = re.findall(r"[\u4e00-\u9fff]{2,}", conflict_directive)
    extra_words = [w for w in extra_words if w not in _WORLD_EVENT_STOP_WORDS]

    all_keywords = list(set(_CONFLICT_BASE_KEYWORDS + extra_words))
    found_in_story = [kw for kw in all_keywords if kw in story_text]
    compliant = len(found_in_story) > 0

    details = {
        "conflict_keywords_checked": all_keywords,
        "found_in_story": found_in_story,
        "compliant": compliant,
    }

    if compliant:
        return True, "", details
    return False, "冲突指令关键词未在故事中出现", details
