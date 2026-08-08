"""AI prompt helper functions for context building."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.utils.financial_narrative import sanitize_authoritative_fact_records

logger = logging.getLogger(__name__)

# 约束优先级标记
CONSTRAINT_MUST = "[MUST]"      # 违反即失败
CONSTRAINT_SHOULD = "[SHOULD]"  # 应尽力遵守
CONSTRAINT_REF = "[REF]"        # 仅供参考

# 约束 Token 预算配置
CONSTRAINT_BUDGET = {
    "critical_summary": 100,      # 不可削减
    "established_facts": 800,     # 不可削减
    "storylines": 600,            # 可压缩
    "world_model": 500,           # 不可削减
    "foreshadowing": 400,         # 可削减
    "habits": 300,                # 可削减
    "vector_context": 400,        # 可削减
    "overused_phrases": 300,      # 可削减
    "style_constraints": 400,     # 可削减（风格引擎）
    "arc_hint": 200,              # 可削减（人物弧光）
    "conflict_directive": 150,    # 可削减（冲突指令）
    "world_event_context": 200,   # 可削减（世界呼吸）
    "fate_echo_hint": 150,        # 可削减（宿命回响）
    "preference_hint": 100,       # 可削减（偏好适配）
    "foreshadowing_technique_hint": 150,  # 可削减（伏笔技法）
}

# 削减优先级：数字越大越先被削减
_BUDGET_TRIM_ORDER = [
    "preference_hint",
    "foreshadowing_technique_hint",
    "fate_echo_hint",
    "arc_hint",
    "conflict_directive",
    "world_event_context",
    "style_constraints",
    "overused_phrases",
    "vector_context",
    "habits",
    "foreshadowing",
]

# 不可削减项
_BUDGET_PROTECTED = {"critical_summary", "established_facts", "world_model"}


def _compress_fact(fact: dict, language: str) -> str:
    """
    将单条事实压缩为高信息密度格式。

    根据 fact 的 type/category 字段选择不同的压缩模板：
    - commitment/promise: "★ {人物}→{对象}: {动作}(W{周},{状态})"
    - decision: "{人物}: {决策内容}(W{周})"
    - location: "{人物}@{地点}"
    - 其他: 截断前40字符 + "..."

    Args:
        fact: 事实字典，可能包含 category, subject, fact, source_week, status 等字段
        language: 语言代码 "zh" 或 "en"

    Returns:
        压缩后的事实文本
    """
    category = (fact.get("category") or fact.get("type") or "").lower()
    subject = fact.get("subject", "")
    fact_text = fact.get("fact", "") or fact.get("description", "")
    source_week = fact.get("source_week", "")
    status = fact.get("status", "")

    # 周次显示（week 从 0 开始，显示时+1）
    week_str = ""
    if source_week != "" and source_week is not None:
        try:
            week_str = f"W{int(source_week) + 1}"
        except (ValueError, TypeError):
            week_str = ""

    zh = language == "zh"

    # commitment / promise 类
    if category in ("commitment", "promise"):
        status_part = f",{status}" if status else ""
        week_part = f",{week_str}" if week_str else ""
        meta = f"({week_part}{status_part})".replace("(,", "(")
        if not meta or meta == "()":
            meta = ""
        if zh:
            return f"★ {subject}→{fact_text}{meta}"
        else:
            return f"★ {subject}→{fact_text}{meta}"

    # decision 类
    if category == "decision":
        week_part = f"({week_str})" if week_str else ""
        return f"{subject}: {fact_text}{week_part}"

    # location 类
    if category == "location":
        return f"{subject}@{fact_text}"

    # 其他类型：截断
    full = f"{subject}: {fact_text}" if subject else fact_text
    if len(full) > 40:
        return full[:40] + "..."
    return full


def _estimate_tokens(text: str) -> int:
    """估计文本的 token 数。中文按 len*0.75，英文按 len/4。"""
    if not text:
        return 0
    # 简单判断：如果包含大量中文字符则用 0.75 比率
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if chinese_chars > len(text) * 0.3:
        return int(len(text) * 0.75)
    return max(1, len(text) // 4)


def _allocate_constraint_budget(
    constraint_texts: Dict[str, str],
    budget: Optional[Dict[str, int]] = None,
) -> Dict[str, str]:
    """
    根据 Token 预算分配约束文本。
    当总约束超过预算时，按优先级从低到高削减。

    Args:
        constraint_texts: 约束名称 -> 约束文本 的映射
        budget: 预算配置，默认使用 CONSTRAINT_BUDGET

    Returns:
        调整后的约束文本映射（可能被截断）
    """
    if budget is None:
        budget = CONSTRAINT_BUDGET

    total_budget = sum(budget.values())

    # 计算当前总 token
    current_tokens: Dict[str, int] = {}
    total_tokens = 0
    for key, text in constraint_texts.items():
        tokens = _estimate_tokens(text)
        current_tokens[key] = tokens
        total_tokens += tokens

    # 未超预算，原样返回
    if total_tokens <= total_budget:
        return dict(constraint_texts)

    # 需要削减的 token 数
    excess = total_tokens - total_budget
    result = dict(constraint_texts)

    for key in _BUDGET_TRIM_ORDER:
        if excess <= 0:
            break
        if key not in result or key in _BUDGET_PROTECTED:
            continue

        text = result[key]
        current = current_tokens.get(key, 0)
        allowed = budget.get(key, 0)

        if current <= allowed:
            continue

        # 计算允许的字符数：根据 token/char 比率反推
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if chinese_chars > len(text) * 0.3:
            # 中文：1 char ≈ 0.75 token
            allowed_chars = int(allowed / 0.75)
        else:
            # 英文：1 char ≈ 0.25 token
            allowed_chars = allowed * 4

        if len(text) > allowed_chars and allowed_chars > 0:
            # 中文用中文后缀，英文用英文后缀
            if chinese_chars > len(text) * 0.3:
                result[key] = text[:allowed_chars] + "...（已精简）"
            else:
                result[key] = text[:allowed_chars] + "... (trimmed)"
            new_tokens = _estimate_tokens(result[key])
            excess -= (current - new_tokens)
            current_tokens[key] = new_tokens
        elif allowed_chars <= 0:
            # 预算为 0，整个删除
            result[key] = ""
            excess -= current
            current_tokens[key] = 0

    return result


def _collect_available_people(
    character_settings: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    从角色设定中收集所有可用人物（家庭成员 + 关键人物），去重。

    Returns:
        人物字典列表 [{"name": ..., "role": ...}, ...]
    """
    if not character_settings:
        return []

    available_people = []

    # Collect family members (object format only)
    if "family" in character_settings:
        for member in character_settings["family"].get("family_members", []):
            if isinstance(member, dict) and member.get("name"):
                available_people.append(member)

    # Collect key_people, avoid duplicates. Accept both the canonical
    # {"key_people": [...]} shape and legacy list payloads produced by older
    # creation/preset flows.
    relationships = character_settings.get("relationships")
    if isinstance(relationships, list):
        key_people = relationships
    elif isinstance(relationships, dict):
        key_people = relationships.get("key_people", [])
    else:
        key_people = []

    if isinstance(key_people, list):
        for person in key_people:
            if not isinstance(person, dict):
                continue
            name = person.get("name", "")
            if name and not any(p.get("name") == name for p in available_people):
                available_people.append(person)

    return available_people


def _format_people_names(
    available_people: list, language: str, include_role: bool = True
) -> str:
    """格式化人物列表为可读字符串。"""
    if not available_people:
        return "无" if language == "zh" else "None"

    def role_label(person: dict) -> str:
        return str(
            person.get("role")
            or person.get("relationship")
            or person.get("relation")
            or person.get("relationship_desc")
            or person.get("relationship_description")
            or ""
        ).strip()

    sep = "、" if language == "zh" else ", "
    if include_role:
        if language == "zh":
            parts = [
                f"{p.get('name', '')}（{role_label(p)}）"
                for p in available_people
                if p.get("name")
            ]
        else:
            parts = [
                f"{p.get('name', '')} ({role_label(p)})"
                for p in available_people
                if p.get("name")
            ]
    else:
        parts = [p.get("name", "") for p in available_people if p.get("name")]

    return sep.join(parts) if parts else ("无" if language == "zh" else "None")


def _build_new_character_intro_context(
    new_character: Optional[Dict[str, Any]], language: str
) -> str:
    """构建新人物引入提示，指导AI自然地在故事中引入新角色。

    关键：此函数会生成一个醒目的提示块，确保 AI 理解这是新人物的首次登场。
    """
    if not new_character:
        return ""

    name = new_character.get("name", "")
    role = new_character.get("role", "")
    relationship = new_character.get("relationship", "")
    relationship_desc = new_character.get("relationship_desc", "")
    personality = (
        ", ".join(new_character.get("personality_traits", []))
        if new_character.get("personality_traits")
        else ""
    )
    occupation = new_character.get("occupation", "")

    if not name:
        return ""

    if language == "zh":
        parts = ["\n\n" + "=" * 50]
        parts.append("【本轮新登场人物 - 首次出现】")
        parts.append("=" * 50)
        parts.append(f"\n注意: 人物 **{name}** 是本轮故事中**首次出现**的新人物！")
        parts.append("")
        parts.append("人物信息：")
        if role:
            parts.append(f"  - 身份/角色：{role}")
        if occupation:
            parts.append(f"  - 职业：{occupation}")
        if relationship or relationship_desc:
            parts.append(f"  - 与主角关系：{relationship or relationship_desc}")
        if personality:
            parts.append(f"  - 性格特点：{personality}")
        parts.append("")
        parts.append("写作要求（非常重要）：")
        parts.append("  1. 这是此人物**第一次**出现在主角的生活中")
        parts.append("  2. 必须安排一个合理的「相识/相遇」场景")
        parts.append("  3. 禁止让此人物像老朋友一样突然出现")
        parts.append("  4. 禁止假设主角已经认识TA")
        parts.append("  5. 禁止让他们之间有「过去的回忆」或「之前的互动」")
        parts.append("  6. 故事应该围绕或包含这次**初次相遇/接触**展开")
        parts.append("=" * 50)
        return "\n".join(parts)
    else:
        parts = ["\n\n" + "=" * 50]
        parts.append("【NEW CHARACTER - FIRST APPEARANCE】")
        parts.append("=" * 50)
        parts.append(
            f"\nNote: Character **{name}** is appearing for the FIRST TIME in this round!"
        )
        parts.append("")
        parts.append("Character Info:")
        if role:
            parts.append(f"  - Role: {role}")
        if occupation:
            parts.append(f"  - Occupation: {occupation}")
        if relationship or relationship_desc:
            parts.append(
                f"  - Relationship to protagonist: {relationship or relationship_desc}"
            )
        if personality:
            parts.append(f"  - Personality: {personality}")
        parts.append("")
        parts.append("Writing Requirements (VERY IMPORTANT):")
        parts.append("  1. This is the character's FIRST EVER appearance")
        parts.append("  2. Must write a natural 'meeting/encounter' scene")
        parts.append("  3. FORBIDDEN to have them appear as an old friend")
        parts.append("  4. FORBIDDEN to assume protagonist already knows them")
        parts.append(
            "  5. FORBIDDEN to reference 'past memories' or 'previous interactions'"
        )
        parts.append("  6. Story should revolve around this FIRST meeting/encounter")
        parts.append("=" * 50)
        return "\n".join(parts)


def _build_available_people_constraint(available_people: list, language: str) -> str:
    """构建"可用人物列表"约束字符串，用于提示词。"""
    if not available_people:
        return ""

    names = [p.get("name", "") for p in available_people if p.get("name")]
    if not names:
        return ""

    names_str = ", ".join(names)
    if language == "zh":
        return f"\n{CONSTRAINT_MUST} **可用人物列表（事件中的人物必须且只能来自此列表，严禁使用名单外的人物）**：{names_str}"
    else:
        return f"\n{CONSTRAINT_MUST} **Available People List (all people in events MUST and ONLY come from this list, STRICTLY FORBIDDEN to use people outside this list)**: {names_str}"


def _build_time_context(game_date_info: Optional[Dict[str, Any]], language: str) -> str:
    """
    构建时间信息上下文段落。

    Args:
        game_date_info: 游戏内日期信息字典
        language: 语言代码

    Returns:
        时间信息上下文字符串
    """
    if not game_date_info:
        return ""

    if language == "zh":
        date_str = game_date_info.get("date_string", "")
        season = game_date_info.get("season", "")
        age = game_date_info.get("age", "")
        total_week = game_date_info.get("total_week", 0)
        return f"""\n【当前时间】
{date_str}（{season}季），主角{age}岁，第{total_week}周"""
    else:
        date_str = game_date_info.get("date_string_en", "")
        season = game_date_info.get("season", "")
        age = game_date_info.get("age", "")
        total_week = game_date_info.get("total_week", 0)
        season_en = {
            "春": "Spring",
            "夏": "Summer",
            "秋": "Autumn",
            "冬": "Winter",
        }.get(season, season)
        return f"""\n[Current Time]
{date_str} ({season_en}), protagonist age {age}, Week {total_week}"""


def _build_pending_storylines_context(
    pending_storylines: Optional[list], language: str
) -> str:
    """
    构建未完结剧情线上下文段落。
    高重要性剧情线使用强制约束，中重要性的使用建议性约束。

    Args:
        pending_storylines: 未完结的剧情线列表
        language: 语言代码

    Returns:
        剧情线上下文字符串
    """
    if not pending_storylines:
        return ""

    # ★ 三级分离：overdue（过期必须处理）/ high / medium
    overdue_storylines = [
        sl for sl in pending_storylines
        if sl.get("importance") == "high" and sl.get("overdue", False)
    ]
    high_storylines = [
        sl for sl in pending_storylines
        if sl.get("importance") == "high" and not sl.get("overdue", False)
    ]
    medium_storylines = [
        sl for sl in pending_storylines if sl.get("importance") != "high"
    ]

    def _fmt_storyline(sl: dict, lang: str) -> str:
        """格式化单条剧情线"""
        desc = sl.get("description", "")
        created_week = sl.get("created_week", 0) + (1 if lang == "zh" else 0)
        characters = sl.get("related_characters", [])
        if lang == "zh":
            char_str = f"，涉及人物: {'、'.join(characters)}" if characters else ""
            return f"第{created_week}周起: {desc}{char_str}"
        else:
            char_str = f", involving: {', '.join(characters)}" if characters else ""
            return f"Since week {created_week}: {desc}{char_str}"

    def _fmt_storyline_compressed_high(sl: dict, lang: str) -> str:
        """压缩高重要性剧情线为单行摘要"""
        desc = sl.get("description", "")
        characters = sl.get("related_characters", [])
        if lang == "zh":
            short_desc = desc[:30] + "..." if len(desc) > 30 else desc
            char_str = f"（涉及: {'、'.join(characters)}）" if characters else ""
            return f"• {short_desc}{char_str}"
        else:
            short_desc = desc[:50] + "..." if len(desc) > 50 else desc
            char_str = f" (involves: {', '.join(characters)})" if characters else ""
            return f"• {short_desc}{char_str}"

    def _fmt_storyline_compressed_medium(sl: dict, lang: str) -> str:
        """压缩中重要性剧情线为仅名称"""
        desc = sl.get("description", "")
        if lang == "zh":
            short_desc = desc[:15] + "..." if len(desc) > 15 else desc
            return f"• {short_desc}"
        else:
            short_desc = desc[:30] + "..." if len(desc) > 30 else desc
            return f"• {short_desc}"

    if language == "zh":
        lines = ["\n【未完结的重要剧情线】"]

        # ★ 最高优先级：overdue 剧情线 — 独立强制约束
        if overdue_storylines:
            lines.append(f"\n{CONSTRAINT_MUST} 🚨 **以下剧情线已严重滞后，本轮故事必须推进或解决其中至少一条：**")
            for sl in overdue_storylines:
                lines.append(f"- 🚨【逾期】{_fmt_storyline(sl, 'zh')}")
            lines.append(
                "强制要求：以上剧情线已被搁置太久，故事必须明确推进、回应或解决至少一条。"
                "不能继续回避。如涉及时间承诺（约定、仪式等），必须让事件发生或给出合理交代。"
            )

        if high_storylines:
            lines.append(f"\n{CONSTRAINT_SHOULD} **必须在故事中涉及以下高重要性剧情线（至少一条）：**")
            for sl in high_storylines:
                lines.append(f"- 【高】{_fmt_storyline_compressed_high(sl, 'zh')}")
        if medium_storylines:
            lines.append(f"\n{CONSTRAINT_REF} 可选择性延续的剧情线：")
            for sl in medium_storylines:
                lines.append(f"- 【中】{_fmt_storyline_compressed_medium(sl, 'zh')}")
        if high_storylines and not overdue_storylines:
            lines.append(
                "\n强制要求：故事必须自然地涉及至少一条高重要性剧情线，可以是续写发展、回应或解决。不能完全忽略这些未完结的重要事件。"
            )
        elif not overdue_storylines:
            lines.append(
                "\n建议自然地延续或回应以上剧情线。如果剧情自然结束，无需强行续写。"
            )
        return "\n".join(lines)
    else:
        lines = ["\n[Pending Important Storylines]"]

        # ★ Overdue storylines — separate MUST constraint
        if overdue_storylines:
            lines.append(
                f"\n{CONSTRAINT_MUST} 🚨 **OVERDUE: The following storylines have been stalled too long. "
                "MUST advance or resolve at least one in THIS round:**"
            )
            for sl in overdue_storylines:
                lines.append(f"- 🚨[OVERDUE] {_fmt_storyline(sl, 'en')}")
            lines.append(
                "MANDATORY: These storylines have been neglected too long. "
                "Story MUST explicitly advance, address, or resolve at least one. "
                "If it involves a time commitment (appointment, ceremony, etc.), "
                "the event MUST happen or a clear explanation must be given."
            )

        if high_storylines:
            lines.append(
                f"\n{CONSTRAINT_SHOULD} **MUST address at least one of these HIGH-importance storylines in the story:**"
            )
            for sl in high_storylines:
                lines.append(f"- [HIGH] {_fmt_storyline_compressed_high(sl, 'en')}")
        if medium_storylines:
            lines.append(f"\n{CONSTRAINT_REF} Optional storylines to continue:")
            for sl in medium_storylines:
                lines.append(f"- [MEDIUM] {_fmt_storyline_compressed_medium(sl, 'en')}")
        if high_storylines and not overdue_storylines:
            lines.append(
                "\nMANDATORY: Story MUST naturally involve at least one high-importance storyline - continue, address, or resolve it. Cannot completely ignore these unresolved important events."
            )
        elif not overdue_storylines:
            lines.append(
                "\nSuggested: Naturally continue or address the above storylines. Don't force continuation if the plot naturally concludes."
            )
        return "\n".join(lines)


def _build_continuation_mandate(
    last_event_concluded: bool, last_round_full_story: str, language: str
) -> str:
    """
    构建上一轮故事上下文。无论事件是否完结，都注入上一轮故事作为参考。
    - 未完结时：强制续写指令
    - 已完结时：叙事背景参考，确保故事承上启下

    Args:
        last_event_concluded: 上一轮事件是否已完结
        last_round_full_story: 上一轮完整故事文本（含选择标记和续写）
        language: 语言代码

    Returns:
        上一轮故事上下文字符串
    """
    if not last_round_full_story:
        return ""

    # Split story into event part and choice+continuation part
    event_part = last_round_full_story
    choice_continuation_part = ""

    sep_idx = last_round_full_story.find("\n\n--- ")
    if sep_idx > 0:
        event_part = last_round_full_story[:sep_idx]
        choice_continuation_part = last_round_full_story[sep_idx:]

    if not last_event_concluded:
        # 未完结 - 强制续写，截断事件部分但始终保留选择+续写
        if len(event_part) > 1500:
            event_part = event_part[:1500] + "..."

        story_text = event_part + choice_continuation_part

        if language == "zh":
            return f"""\n{CONSTRAINT_MUST} 【必须续写上一轮未完结的故事】
上一轮的故事尚未完结，你必须延续上一轮的故事线。

【上一轮完整故事（含选择后的发展）】
{story_text}

【续写规则】
- 必须围绕上一轮的核心事件展开后续发展
- 特别注意：上方"选择后的发展"描述了主角做出决策后发生的事情，你必须从这个结果继续往下写
- 可以引入新的转折和变化，但必须与上一轮的事件直接相关
- 禁止开启一个与上一轮无关的全新事件
- 可以解决上一轮的悬念，也可以让事情继续发展
"""
        else:
            return f"""\n{CONSTRAINT_MUST} [MUST CONTINUE THE UNFINISHED STORY FROM LAST ROUND]
The previous round's story has NOT concluded. You MUST continue the previous storyline.

[Previous Round's Full Story (including post-choice development)]
{story_text}

[Continuation Rules]
- MUST continue the development of the previous round's core event
- PAY SPECIAL ATTENTION: The "post-choice development" above describes what happened after the player's decision. You MUST continue from that result
- Can introduce new twists and changes, but must be directly related to the previous event
- FORBIDDEN to start a completely unrelated new event
- Can resolve the previous suspense, or let the situation continue developing
"""
    else:
        # 已完结 - 提供叙事背景参考，确保承上启下
        if len(event_part) > 800:
            event_part = "..." + event_part[-800:]

        story_text = event_part + choice_continuation_part

        if language == "zh":
            return f"""\n{CONSTRAINT_REF} 【上一轮故事背景 - 必须保持叙事连贯】
上一轮的故事已自然完结，但本轮故事必须在此基础上继续发展，不能出现"失忆式"断裂。

【上一轮故事（含选择后的发展）】
{story_text}

【承上启下规则】
- 本轮故事必须承接上一轮的世界状态：人物关系、地理位置、正在进行的事务
- 特别是"选择后的发展"部分描述了主角决策的直接结果，新故事应自然衍接这个结果
- 可以开启新的事件，但主角和周围人物应该记得上一轮发生的事
- 上一轮中出现的人物、对话、决定的后果应该在本轮有所体现或被提及
- 故事中的人物不应该表现得好像上一轮的事没发生过
"""
        else:
            return f"""\n{CONSTRAINT_REF} [PREVIOUS ROUND STORY CONTEXT - MUST MAINTAIN NARRATIVE CONTINUITY]
The previous round's story concluded naturally, but this round MUST continue from that context. No "amnesia-style" disconnection.

[Previous Round's Story (including post-choice development)]
{story_text}

[Continuity Rules]
- This round MUST inherit the world state from last round: character relationships, locations, ongoing affairs
- Pay special attention to the "post-choice development" section which describes the direct result of the player's decision. New story should naturally follow from that result
- Can start new events, but characters should remember what happened last round
- Characters, dialogue, and consequences from last round should be reflected or referenced
- Characters must NOT act as if last round never happened
"""


def _build_character_habits_context(
    character_habits: Optional[list], language: str
) -> str:
    """
    构建人物习惯上下文段落，用于在故事生成时保持角色行为一致性。

    Args:
        character_habits: 已记录的角色习惯列表
        language: 语言代码

    Returns:
        角色习惯上下文字符串
    """
    if not character_habits:
        return ""

    # 按角色分组
    habits_by_char: Dict[str, list] = {}
    for h in character_habits:
        char_name = h.get("character", "未知")
        if char_name not in habits_by_char:
            habits_by_char[char_name] = []
        habits_by_char[char_name].append(h)

    if language == "zh":
        lines = [f"\n{CONSTRAINT_SHOULD} 【人物习惯记录 - 必须在故事中体现，保持角色行为一致性】"]
        strength_label = {"strong": "根深蒂固", "moderate": "明显", "emerging": "初现"}
        cat_label = {
            "behavioral": "行为",
            "speech": "言语",
            "emotional": "情绪",
            "social": "社交",
            "lifestyle": "生活",
        }
        for char_name, habits in habits_by_char.items():
            lines.append(f"\n- {char_name}：")
            for h in habits:
                cat = cat_label.get(h.get("category", ""), "其他")
                strength = strength_label.get(h.get("strength", "moderate"), "明显")
                origin = h.get("origin", "")
                origin_part = f"（来源：{origin}）" if origin else ""
                lines.append(
                    f"  - 【{cat}/{strength}】{h.get('habit', '')}{origin_part}"
                )
        lines.append(
            "\n角色在故事中的行为应自然体现以上习惯。习惯不需要每次都明确提及，但行为不应与已建立的习惯矛盾。"
            "\n如果某个事件导致习惯发生变化，应在故事中自然地体现这种转变过程。"
        )
        return "\n".join(lines)
    else:
        lines = [
            f"\n{CONSTRAINT_SHOULD} [Character Habits - MUST be reflected in story, maintain behavioral consistency]"
        ]
        strength_label = {
            "strong": "deep-rooted",
            "moderate": "notable",
            "emerging": "emerging",
        }
        cat_label = {
            "behavioral": "Behavioral",
            "speech": "Speech",
            "emotional": "Emotional",
            "social": "Social",
            "lifestyle": "Lifestyle",
        }
        for char_name, habits in habits_by_char.items():
            lines.append(f"\n> {char_name}:")
            for h in habits:
                cat = cat_label.get(h.get("category", ""), "Other")
                strength = strength_label.get(h.get("strength", "moderate"), "notable")
                origin = h.get("origin", "")
                origin_part = f" (origin: {origin})" if origin else ""
                lines.append(
                    f"  - [{cat}/{strength}] {h.get('habit', '')}{origin_part}"
                )
        lines.append(
            "\nCharacters should naturally exhibit these habits in the story. Habits don't need explicit mention every time, but behavior should not contradict established habits."
            "\nIf an event causes a habit to change, show the transition naturally in the story."
        )
        return "\n".join(lines)


def _build_foreshadowing_context(
    activated_seed: Optional[Dict[str, Any]], language: str
) -> str:
    """
    构建伏笔回响上下文。当有一颗伏笔种子被激活时，生成指导性提示，
    根据隐蔽度和回收方式分级引导AI在新故事中自然地回应这个伏笔。

    实现"草蛇灰线，伏脉千里"的核心注入逻辑：
    - 低隐蔽度种子 -> 较直接的回响（读者可以明确感知关联）
    - 高隐蔽度种子 -> 极其隐晦的回响（仅重读时才能发现联系）
    - 回收方式指导AI采用恰当的叙事技法

    Args:
        activated_seed: 被激活的伏笔种子字典
        language: 语言代码

    Returns:
        伏笔回响提示字符串，没有激活的种子则返回空字符串
    """
    if not activated_seed:
        return ""

    desc = activated_seed.get("description", "")
    context = activated_seed.get("original_context", "")
    characters = activated_seed.get("related_characters", [])
    seed_type = activated_seed.get("seed_type", "mystery")
    planted_week = activated_seed.get("planted_week", 0) + 1  # ★ week 从0开始，显示时+1
    obfuscation = activated_seed.get("obfuscation_level", 0.5)
    weight = activated_seed.get("narrative_weight", "supporting")
    recycle = activated_seed.get("recycle_method", "echo")

    if not desc:
        return ""

    # 种子类型描述
    type_hints_zh = {
        "mystery": "神秘元素重新浮现",
        "relationship": "人物关系暗线产生了新的发展",
        "warning": "曾经的警告或预兆现在应验了",
        "opportunity": "之前擦肩而过的机会重新出现",
        "consequence": "过去行为的连锁反应现在显现",
        "character_return": "之前出现过的人物带着新变化回来",
    }
    type_hints_en = {
        "mystery": "A mysterious element resurfaces",
        "relationship": "A relationship undercurrent bears new fruit",
        "warning": "A past warning or omen now comes true",
        "opportunity": "A previously noted opportunity reappears",
        "consequence": "Consequences of past actions now manifest",
        "character_return": "A character from the past returns with changes",
    }

    # 回收方式描述
    recycle_hints_zh = {
        "revelation": "通过揭露一个之前隐藏的秘密/真相来回收",
        "confirmation": "通过事实验证之前的预感/猜测来回收",
        "ironic_twist": "通过讽刺性的反转（与当初预期相反的结果）来回收",
        "escalation": "通过事态升级、情况恶化/爆发来回收",
        "echo": "通过微妙的呼应、似曾相识的场景来回收",
    }
    recycle_hints_en = {
        "revelation": "Recover by revealing a hidden secret/truth",
        "confirmation": "Recover by confirming a prior intuition/guess",
        "ironic_twist": "Recover through an ironic reversal (opposite of expected outcome)",
        "escalation": "Recover through situation escalation/eruption",
        "echo": "Recover through subtle resonance, a deja vu moment",
    }

    # 根据隐蔽度决定注入强度
    if obfuscation >= 0.7:
        intensity_zh = "极度隐晦地"
        intensity_detail_zh = "这是一个深层伏笔。回响必须极其隐晦——可以是一个似曾相识的细节、一句无意间的话、一个微妙的巧合。读者第一次读不应该注意到这个关联，只有重读时才会恍然大悟。"
        intensity_en = "extremely subtly"
        intensity_detail_en = "This is a deep foreshadowing. The echo must be extremely subtle — a deja vu detail, a casual remark, a tiny coincidence. First-time readers should NOT notice the connection; only re-readers will have an 'aha' moment."
    elif obfuscation >= 0.4:
        intensity_zh = "自然地"
        intensity_detail_zh = "这是一个中等隐蔽度的伏笔。回响应该自然融入故事——看似合理的巧合、自然引出的话题、顺理成章的重逢。细心的读者可能注意到关联，但不刻意的读者会觉得只是故事自然发展。"
        intensity_en = "naturally"
        intensity_detail_en = "This is a moderately concealed foreshadowing. The echo should blend naturally — a plausible coincidence, a naturally arising topic, a reasonable reunion. Attentive readers may notice, but casual readers should feel it's just natural story progression."
    else:
        intensity_zh = "较明显地"
        intensity_detail_zh = "这是一个显性伏笔。可以让回响较为明显——人物直接提及、事件明确关联。读者应该能感受到'之前发生的事影响了现在'，但仍需通过故事情节而非旁白来展现。"
        intensity_en = "relatively clearly"
        intensity_detail_en = "This is an overt foreshadowing. The echo can be relatively clear — direct references by characters, explicit event connections. Readers should feel 'the past affects the present', but still show through plot, not narration."

    # 根据叙事权重决定回响在故事中的角色
    weight_hints_zh = {
        "minor": "伏笔回响作为故事的点缀细节存在，不改变主要情节走向",
        "supporting": "伏笔回响作为重要的支线元素，丰富故事层次",
        "major": "伏笔回响应成为推动本轮故事发展的关键因素之一",
    }
    weight_hints_en = {
        "minor": "The echo should exist as a decorative detail, not altering the main plot",
        "supporting": "The echo should serve as an important subplot element, enriching story layers",
        "major": "The echo should become one of the key drivers of this round's story",
    }

    chars_str = "、".join(characters) if characters else ""

    if language == "zh":
        type_hint = type_hints_zh.get(seed_type, "之前埋下的伏笔现在回响")
        recycle_hint = recycle_hints_zh.get(recycle, "通过自然的方式回收")
        weight_hint = weight_hints_zh.get(weight, weight_hints_zh["supporting"])

        lines = [
            f"\n{CONSTRAINT_SHOULD} 【伏笔回响 — 草蛇灰线，伏脉千里】",
            f"在第{planted_week}周，故事中埋下了一个伏笔：",
            f"「{desc}」",
        ]
        if context:
            lines.append(f"当时的场景：{context}")
        if chars_str:
            lines.append(f"涉及人物：{chars_str}")
        lines.append("")
        lines.append(f"请{intensity_zh}将这个伏笔的回响编织进本轮故事：{type_hint}。")
        lines.append("")
        lines.append(f"【隐蔽度指导】{intensity_detail_zh}")
        lines.append(f"【回收方式】{recycle_hint}")
        lines.append(f"【叙事角色】{weight_hint}")
        lines.append("")
        lines.append("克制与延迟满足的艺术：")
        lines.append("- 不要一次揭示全部——留白是力量。只展现伏笔回响的一个切面")
        lines.append("- 回响可以引发新的疑问，而非回答所有问题")
        lines.append("- 让读者自己'发现'关联，而非由叙述者指出")
        lines.append(
            "- 引入方式：人物对话、巧合重逢、意外发现、消息传来、梦境、相似情境"
        )
        lines.append(
            "- 禁止直接提及'伏笔''回响''草蛇灰线''呼应''命运''前因后果'等元叙述词汇"
        )
        return "\n".join(lines)
    else:
        type_hint = type_hints_en.get(seed_type, "A past foreshadowing now echoes")
        recycle_hint = recycle_hints_en.get(recycle, "Recover naturally")
        weight_hint = weight_hints_en.get(weight, weight_hints_en["supporting"])

        lines = [
            f"\n{CONSTRAINT_SHOULD} [FORESHADOWING ECHO — Subtle Threads, Distant Echoes]",
            f"In Week {planted_week}, a seed was planted in the story:",
            f'"{desc}"',
        ]
        if context:
            lines.append(f"Original scene: {context}")
        if chars_str:
            lines.append(f"Characters involved: {', '.join(characters)}")
        lines.append("")
        lines.append(
            f"Weave this echo {intensity_en} into the current story: {type_hint}."
        )
        lines.append("")
        lines.append(f"[Concealment Guidance] {intensity_detail_en}")
        lines.append(f"[Recovery Method] {recycle_hint}")
        lines.append(f"[Narrative Role] {weight_hint}")
        lines.append("")
        lines.append("The Art of Restraint & Delayed Gratification:")
        lines.append(
            "- Don't reveal everything at once — show only ONE facet of the echo"
        )
        lines.append(
            "- The echo can raise new questions rather than answering all of them"
        )
        lines.append(
            "- Let readers 'discover' the connection themselves, don't spell it out"
        )
        lines.append(
            "- Introduction methods: dialogue, coincidental meeting, unexpected discovery, news arriving, dreams, parallel situations"
        )
        lines.append(
            "- NEVER mention 'foreshadowing', 'echo', 'callback', 'destiny', 'fate', 'cause and effect', or any meta-narrative terms"
        )
        return "\n".join(lines)


def _build_era_anachronism_constraints(
    character_settings: Optional[Dict[str, Any]], language: str
) -> str:
    """
    构建时代错位预防约束，明确列出各时代禁止出现的事物。
    用于注入事件生成提示词，防止AI生成时代不符的内容。
    """
    if not character_settings:
        return ""

    era = character_settings.get("era", {})
    era_desc = (era.get("era_description", "") + " " + era.get("world_context", "")).lower()
    world = character_settings.get("world", {})
    tech_level = (world.get("technology_level", "") + " " + world.get("world_description", "")).lower()

    # 判断是否为古代/前现代背景
    is_historical = any(
        word in era_desc or word in tech_level
        for word in ["古代", "ancient", "medieval", "中世纪", "宋朝", "唐朝", "明朝", "清朝", "southern song", "tang", "ming", "qing", "dynasty", "pre-modern"]
    )

    # 判断是否为现代/当代背景
    is_modern = any(
        word in era_desc or word in tech_level
        for word in ["现代", "当代", "modern", "contemporary", "future", "科幻", "sci-fi", "赛博"]
    )

    if not is_historical and not is_modern:
        # 无法判断时代，返回通用约束
        if language == "zh":
            return "\n【时代一致性约束】请确保故事中的科技、社会制度、生活方式与角色设定的时代背景严格一致。"
        else:
            return "\n[Era Consistency] Ensure technology, social systems, and lifestyle match the character's era setting."

    if is_historical:
        if language == "zh":
            return """\n【★ 时代错位红线（违反即失败）★】
角色设定为古代/前现代背景，故事中绝对禁止出现以下现代概念：
- 电子设备：手机、电脑、电话、电视、收音机、相机、录音笔
- 交通工具：汽车、飞机、火车、地铁、高铁、摩托车、自行车（古代可用马匹、轿子、马车、船只）
- 现代场所：公司、办公室、星巴克、咖啡厅、商场、超市、电影院、健身房、医院（古代可用客栈、茶楼、集市、药铺、医馆）
- 现代制度：客户提案、导师制度、周五下班、KPI、PPT、会议、合同、签证、护照
- 互联网与通讯：互联网、微信、QQ、邮件、短信、社交媒体、APP、网站
- 现代娱乐：电子游戏、网络小说、电视剧、电影、流行音乐、演唱会
- 现代科技：电灯泡、电梯、空调、冰箱、洗衣机、微波炉、塑料、橡胶
- 现代货币与金融：股票、基金、比特币、信用卡、支付宝、微信支付、银行转账
- 现代教育：高考、大学专业、考研、论文答辩、实验室、科研项目
- 如果出现"咖啡"，必须是古代茶饮或酒；如果出现"医院"，必须是古代医馆或药铺
- 古代人物穿古装、用古代器具、遵循古代礼仪，绝对禁止穿西装、打领带、用现代物品"""
        else:
            return """\n[★ ERA ANACHRONISM RED LINE (violation = failure) ★]
The character is set in a historical/pre-modern era. The following modern concepts are ABSOLUTELY FORBIDDEN:
- Electronics: phones, computers, telephones, TVs, radios, cameras, recorders
- Transportation: cars, airplanes, trains, subways, high-speed rail, motorcycles, bicycles (use horses, sedan chairs, carriages, boats)
- Modern venues: companies, offices, Starbucks, coffee shops, malls, supermarkets, cinemas, gyms, hospitals (use inns, tea houses, markets, apothecaries)
- Modern systems: client proposals, mentorship programs, "Friday off", KPIs, PowerPoint, meetings, contracts, visas, passports
- Internet & communication: internet, WeChat, email, social media, apps, websites
- Modern entertainment: video games, web novels, TV shows, movies, pop music, concerts
- Modern technology: light bulbs, elevators, air conditioning, refrigerators, washing machines, plastic, rubber
- Modern finance: stocks, funds, Bitcoin, credit cards, mobile payments, bank transfers
- Modern education: college entrance exams, university majors, graduate school, thesis defense, laboratories
- If "coffee" appears, it must be ancient tea or wine; if "hospital" appears, it must be an ancient apothecary
- Characters must wear ancient clothing, use ancient tools, follow ancient etiquette. NO suits, ties, or modern items"""

    # Modern era — explicitly prevent reverse drift into historical/classical settings.
    if language == "zh":
        return """\n【★ 反向时代漂移红线（违反即失败）★】
角色设定为现代/当代现实主义背景，故事必须保留现代城市、现代职业、现代货币和2020年代生活方式。
- 禁止古风漂移：不得把现代角色改写到唐朝、宋朝、明朝、清朝、长安、洛阳、汴京、临安、西市、东市等朝代/古城语境。
- 禁止古代称谓和社会制度：郎君、娘子、将作监、科举、客栈、茶楼、木坊、胡商等只能在玩家明确要求历史背景时出现。
- 禁止古代货币和器物替代现代设定：铜钱、三百文、贯钱、银两、绢帛等不得替代元、工资、投资款、合同、账户、工作室预算。
- 如果角色是当代创业者、独立游戏制作人、产品经理、职场人或学生，场景必须围绕现代办公室/工作室/学校/家庭/城市生活展开。
- 可以出现现代科技、交通工具和生活方式，但应符合具体时代（如2020年代不应出现过于超前的科技）。"""
    else:
        return """\n[★ REVERSE ERA DRIFT RED LINE (violation = failure) ★]
The character is set in a modern/contemporary realistic era. Preserve modern cities, jobs, currency, and 2020s lifestyle.
- Do not drift into dynasties, medieval cities, historical markets, inns, guild workshops, imperial exams, or archaic titles unless the player explicitly requested a historical setting.
- Do not replace modern money, salary, investment, contracts, accounts, or studio budgets with coins, taels, silver, tribute, or scrolls.
- If the character is a contemporary founder, indie game developer, product manager, worker, or student, scenes must stay grounded in modern offices, studios, schools, homes, or city life.
- Modern technology, transportation, and lifestyle are appropriate, but should match the specific time period."""


def build_realistic_modern_world_boundary(
    character_settings: Optional[Dict[str, Any]], language: str
) -> str:
    """Build hard constraints that stop ordinary modern settings drifting into sci-fi/IP worlds."""
    if not character_settings:
        return ""

    text = _flatten_setting_text(character_settings).lower()
    modern_cues = [
        "现代",
        "当代",
        "现实",
        "写实",
        "都市",
        "职场",
        "互联网",
        "公司",
        "产品经理",
        "2020",
        "2021",
        "2022",
        "2023",
        "2024",
        "modern",
        "contemporary",
        "realistic",
        "office",
        "company",
    ]
    speculative_cues = [
        "赛博",
        "cyberpunk",
        "科幻",
        "sci-fi",
        "未来",
        "2077",
        "夜之城",
        "荒坂",
        "night city",
        "arasaka",
    ]

    if not any(cue in text for cue in modern_cues):
        return ""
    if any(cue in text for cue in speculative_cues):
        return ""

    if language == "zh":
        return """
[MUST] 【现实主义世界边界 - 违反即重新生成】
- 当前角色设定是现代/当代现实主义背景；必须保留现实城市、现实公司、现实社会制度和2020年代常识。
- 禁止赛博朋克、未来都市、科幻黑帮、反乌托邦公司战争、黑客义体、霓虹废土等未被玩家明确要求的题材漂移。
- 禁止引入外部游戏/IP世界或其专有名词，包括但不限于：夜之城、荒坂集团、Cyberpunk 2077、Night City、Arasaka。
- 如果需要公司、导师、同事、投资人、债主等角色，必须使用角色设定和故事历史中已有的现实主义身份，不得套用知名游戏世界观。"""

    return """
[MUST] [Realistic Modern World Boundary - violation means regeneration]
- The current character setting is modern/contemporary realism; preserve real-world cities, companies, social systems, and 2020s common sense.
- Do not drift into cyberpunk, future-city, sci-fi gang, dystopian corporate war, hacker implant, or neon wasteland genres unless explicitly requested by the player.
- Do not introduce external game/IP worlds or proper nouns, including: Night City, Arasaka, Cyberpunk 2077, 夜之城, 荒坂集团.
- If the story needs companies, mentors, peers, investors, or creditors, use realistic identities from the character settings and established story history."""


def _flatten_setting_text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_setting_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_setting_text(item) for item in value)
    return str(value) if value is not None else ""


def _build_image_era_constraints(
    character_settings: Optional[Dict[str, Any]], language: str
) -> str:
    """
    构建图像生成时代约束，防止场景插画中出现时代不符的元素。
    用于注入图像生成提示词，确保古代背景不会出现星巴克、汽车等现代视觉元素。
    """
    if not character_settings:
        return ""

    era = character_settings.get("era", {})
    era_desc = (era.get("era_description", "") + " " + era.get("world_context", "")).lower()
    world = character_settings.get("world", {})
    tech_level = (world.get("technology_level", "") + " " + world.get("world_description", "")).lower()

    # 判断是否为古代/前现代背景
    is_historical = any(
        word in era_desc or word in tech_level
        for word in ["古代", "ancient", "medieval", "中世纪", "宋朝", "唐朝", "明朝", "清朝", "southern song", "tang", "ming", "qing", "dynasty", "pre-modern"]
    )

    # 判断是否为现代/当代背景
    is_modern = any(
        word in era_desc or word in tech_level
        for word in ["现代", "当代", "modern", "contemporary", "future", "科幻", "sci-fi", "赛博"]
    )

    if not is_historical and not is_modern:
        if language == "zh":
            return "\n【画面时代一致性】确保画面中的建筑、服饰、道具与时代背景严格一致。"
        else:
            return "\n[Visual Era Consistency] Ensure architecture, clothing, and props match the era."

    if is_historical:
        if language == "zh":
            return """\n【★ 画面时代红线（违反即失败）★】
角色设定为古代/前现代背景，画面绝对禁止出现以下现代视觉元素：
- 现代建筑：摩天大楼、玻璃幕墙、霓虹灯、现代桥梁、电线杆
- 现代交通工具：汽车、飞机、火车、摩托车、自行车（古代可用马匹、轿子、马车、木船）
- 现代商业标识：星巴克、麦当劳、肯德基、必胜客、汉堡王、苹果、华为、小米、耐克、阿迪达斯、优衣库、ZARA、H&M、可口可乐、百事、广告牌、LED屏幕、二维码
- 现代物品：手机、电脑、电视、相机、路灯、红绿灯、空调外机、冰箱、洗衣机、电梯
- 现代服饰：西装、领带、牛仔裤、运动鞋、眼镜、T恤、卫衣、风衣、羽绒服（古代可用传统服饰、布鞋、长袍、襦裙、汉服、盔甲）
- 现代场景：咖啡厅、商场、超市、地铁站、机场、医院（古代可用茶馆、集市、药铺、驿站、书院、衙门）
- 画面中的建筑必须是古代风格：木质结构、瓦片屋顶、砖石城墙、飞檐斗拱
- 画面中的服饰必须是古代服装：长袍、襦裙、汉服、盔甲、布衣、绸缎
- 画面中的器具必须是古代器物：陶瓷、青铜、木质家具、油纸伞、竹简、毛笔
- 人物一致性：同一人物的多张图片必须是同一个人，相同脸型、相同五官比例、相同发型，仅允许服装和姿势变化"""
        else:
            return """\n[★ VISUAL ERA RED LINE (violation = failure) ★]
Character is set in a historical/pre-modern era. The image MUST NOT contain these modern visual elements:
- Modern buildings: skyscrapers, glass facades, neon lights, modern bridges, power lines
- Modern vehicles: cars, airplanes, trains, motorcycles, bicycles (use horses, sedan chairs, carriages, wooden boats)
- Modern commercial signs: Starbucks, McDonald's, KFC, Pizza Hut, Burger King, Apple, Huawei, Xiaomi, Nike, Adidas, Uniqlo, ZARA, H&M, Coca-Cola, Pepsi, billboards, LED screens, QR codes
- Modern objects: phones, computers, TVs, cameras, street lamps, traffic lights, AC units, refrigerators, washing machines, elevators
- Modern clothing: suits, ties, jeans, sneakers, glasses, T-shirts, hoodies, windbreakers, down jackets (use traditional robes, cloth shoes, long robes, ruqun, hanfu, armor)
- Modern venues: coffee shops, malls, supermarkets, subway stations, airports, hospitals (use tea houses, markets, apothecaries, post stations, academies, government offices)
- Buildings must be ancient style: wooden structures, tile roofs, brick/stone walls, flying eaves
- Clothing must be ancient/traditional: robes, ruqun, hanfu, armor, cloth garments, silk
- Objects must be ancient: ceramics, bronze, wooden furniture, oil-paper umbrellas, bamboo slips, writing brushes
- Character consistency: multiple images of the same person MUST be the same individual: same face shape, same facial proportions, same hairstyle. Only clothing and pose may vary"""

    # Modern era — anti-sci-fi/fantasy + anti-brand constraints (QA found cyberpunk and brand logos invading realistic modern stories)
    if language == "zh":
        return """\n【★ 画面写实主义红线（违反即失败）★】
角色设定为现代/当代背景，画面必须严格遵守写实主义原则，绝对禁止科幻、奇幻、超现实元素入侵：

【绝对禁止的科幻/未来/奇幻元素】
- 禁止赛博朋克风格：金属质感夹克、电路纹理服装、发光线条装饰、机械义肢、电子眼
- 禁止全息投影：全息屏幕、全息城市、全息古建筑线框、悬浮信息面板、AR投影
- 禁止发光效果：红色/蓝色/紫色发光眼睛、发光物体、霓虹光效人物轮廓、身体发光
- 禁止未来交通工具：科幻飞车、悬浮载具、未来飞行器、喷气背包
- 禁止科幻场景：科幻城市、未来都市天际线、高科技实验室、太空背景、末日废墟
- 禁止奇幻元素：精灵耳朵、魔法光环、异色瞳（非自然色）、翅膀、角、鳞片
- 禁止超现实元素：多重曝光、 surrealist 变形、非自然比例、抽象几何入侵

【绝对禁止的真实商业品牌标识】
- 禁止出现任何真实品牌的Logo、商标、标志性配色或包装
- 包括但不限于：星巴克、麦当劳、苹果、耐克、阿迪达斯、可口可乐、肯德基、华为、小米等
- 如有咖啡厅场景，不得出现星巴克标志性绿色；如有快餐场景，不得出现麦当劳金色拱门
- 人物穿着的衣服不得带有任何真实品牌的Logo或标志性图案

【服装要求（现代日常写实）】
- 男性：衬衫、T恤、 Polo衫、休闲外套、牛仔裤/休闲裤、运动鞋/皮鞋/帆布鞋
- 女性：连衣裙、衬衫、针织衫、牛仔裤、风衣、简约配饰、平底鞋/低跟鞋
- 禁止：金属质感服装、未来感盔甲、电路纹理、发光装饰、夸张科幻造型、透明材质服装、机甲风格

【背景要求】
- 真实城市/自然环境：现代建筑街道、公园、咖啡厅内部、办公室、住宅、校园、自然风景
- 自然光线：日光、室内灯光、街灯、黄昏光，禁止彩色霓虹光效、禁止非自然色光源
- 禁止科幻城市天际线、禁止全息投影叠加、禁止悬浮建筑

【人物一致性要求（严格遵守）】
- 同一人物的多张图片必须是同一个人：相同脸型、相同五官比例、相同发型、相同肤色
- 仅允许服装和姿势变化，面部特征必须绝对保持一致
- 写实摄影风格，禁止动漫风、油画风、科幻风、插画风、水彩风
- 人物比例必须符合真实人类，禁止九头身、过大眼睛等非自然比例"""
    else:
        return """\n[★ VISUAL REALISM RED LINE (violation = failure) ★]
Character is set in a modern/contemporary era. The image MUST strictly follow realism principles and ABSOLUTELY FORBID sci-fi, fantasy, or surreal elements from invading:

[ABSOLUTELY FORBIDDEN sci-fi/future/fantasy elements]
- NO cyberpunk style: metallic jackets, circuit-textured clothing, glowing line decorations, mechanical prosthetics, electronic eyes
- NO holographic projections: holographic screens, holographic cities, holographic building wireframes, floating info panels, AR projections
- NO glowing effects: red/blue/purple glowing eyes, glowing objects, neon light effects on people, body glow
- NO future vehicles: flying cars, hover vehicles, sci-fi aircraft, jetpacks
- NO sci-fi scenes: sci-fi cities, future city skylines, high-tech labs, space backgrounds, post-apocalyptic ruins
- NO fantasy elements: elf ears, magic auras, unnatural eye colors (purple, red, glowing), wings, horns, scales
- NO surreal elements: double exposure, surrealist deformations, unnatural proportions, abstract geometric intrusions

[ABSOLUTELY FORBIDDEN real commercial brand logos]
- NO real brand logos, trademarks, iconic color schemes, or packaging
- Including but not limited to: Starbucks, McDonald's, Apple, Nike, Adidas, Coca-Cola, KFC, Huawei, Xiaomi
- If cafe scene: NO Starbucks iconic green. If fast food scene: NO McDonald's golden arches
- Clothing MUST NOT display any real brand logos or iconic patterns

[Clothing requirements (modern everyday realism)]
- Men: shirts, T-shirts, polo shirts, casual jackets, jeans/casual pants, sneakers/leather shoes/canvas shoes
- Women: dresses, blouses, knitwear, jeans, windbreakers, simple accessories, flats/low heels
- FORBIDDEN: metallic clothing, futuristic armor, circuit textures, glowing decorations, exaggerated sci-fi styling, transparent material clothing, mecha style

[Background requirements]
- Real urban/natural environments: modern building streets, parks, cafe interiors, offices, homes, campuses, natural scenery
- Natural lighting: daylight, indoor lighting, street lamps, dusk light. NO colored neon light effects, NO unnatural colored light sources
- NO sci-fi city skylines, NO holographic projection overlays, NO floating buildings

[Character consistency requirements (strictly follow)]
- Multiple images of the same person MUST be the same individual: same face shape, same facial proportions, same hairstyle, same skin tone
- Only clothing and pose may vary; facial features MUST remain absolutely consistent
- Realistic photography style. NO anime style, oil painting style, sci-fi style, illustration style, watercolor style
- Human proportions MUST match real humans. NO nine-head-body-ratio, oversized eyes, or other unnatural proportions"""


def _build_logic_constraints(
    game_date_info: Optional[Dict[str, Any]], language: str
) -> str:
    """
    构建逻辑性约束文本，用于注入事件生成提示词。
    """
    if not game_date_info:
        return ""

    date_str = game_date_info.get("date_string", "")
    season = game_date_info.get("season", "")

    if language == "zh":
        return f"""\n{CONSTRAINT_SHOULD} 11. **时间与逻辑一致性（必须严格遵守）**：
    - 严格遵守时间线：当前是{date_str}，{season}季，故事中的时间、季节、天气等应与此一致
    - 人物动机一致性：人物行为应符合其性格设定和当前处境
    - 因果逻辑一致性：事件的发展应符合因果关系，不能出现前后矛盾
    - 人物目标一致性：主角的行为应符合其人生愿景和当前目标"""
    else:
        date_str_en = game_date_info.get("date_string_en", "")
        season_en = {
            "春": "Spring",
            "夏": "Summer",
            "秋": "Autumn",
            "冬": "Winter",
        }.get(season, season)
        return f"""\n{CONSTRAINT_SHOULD} 11. **Time & Logic Consistency (MUST STRICTLY FOLLOW)**:
    - Strict timeline: Current is {date_str_en}, {season_en}, story time/season/weather must match
    - Character motivation consistency: Characters must act according to their personality and current situation
    - Causal logic consistency: Events must follow cause-and-effect, no contradictions
    - Character goal consistency: Protagonist's actions should align with their life vision and current goals"""


def _build_established_facts_context(
    established_facts: Optional[list],
    language: str,
    max_facts: int = 30,
    max_total_chars: int = 2500,
) -> str:
    """
    构建已建立的世界事实上下文段落，用于维护人物/地点/事务的一致性。

    ★ 关键事实优先保留策略：
    1. 按重要性排序：承诺 > 重要决策 > 状态变化 > 其他
    2. 确保关键事实不被截断
    3. 限制总长度避免上下文过长

    Args:
        established_facts: 已建立的世界事实列表
        language: 语言代码
        max_facts: 最大事实数量
        max_total_chars: 最大总字符数

    Returns:
        世界事实上下文字符串
    """
    if not established_facts:
        return ""

    # ★ 优先级排序：承诺 > 重要决策 > 状态变化 > 其他
    priority_order = {
        "commitment": 0,  # 承诺（最高优先级）
        "promise": 0,  # 承诺的别名
        "decision": 1,  # 重要决策
        "state_change": 2,  # 状态变化
        "location": 3,  # 地点
        "role": 4,  # 角色
        "situation": 5,  # 事务
        "relationship": 6,  # 关系
        "habit": 7,  # 习惯
        "fact": 8,  # 一般事实
    }

    def get_priority(fact: dict) -> int:
        category = fact.get("category", "fact").lower()
        # 检查是否包含关键词
        fact_text = fact.get("fact", "").lower()
        if "承诺" in fact_text or "答应" in fact_text or "promise" in fact_text:
            return 0
        if (
            "决定" in fact_text
            or "选择" in fact_text
            or "decision" in fact_text
            or "chose" in fact_text
        ):
            return 1
        return priority_order.get(category, 8)

    # 排序事实
    sorted_facts = sorted(
        sanitize_authoritative_fact_records(established_facts), key=get_priority
    )

    # 类别标签
    cat_labels = {
        "zh": {
            "location": "地点",
            "role": "角色",
            "situation": "事务",
            "commitment": "承诺",
            "promise": "承诺",
            "decision": "决策",
            "state_change": "状态变化",
            "relationship": "关系",
            "habit": "习惯",
            "fact": "事实",
        },
        "en": {
            "location": "Location",
            "role": "Role",
            "situation": "Situation",
            "commitment": "Commitment",
            "promise": "Promise",
            "decision": "Decision",
            "state_change": "State Change",
            "relationship": "Relationship",
            "habit": "Habit",
            "fact": "Fact",
        },
    }

    labels = cat_labels.get(language, cat_labels["en"])

    # 构建事实列表，限制数量和总长度
    lines = []
    if language == "zh":
        lines.append(f"\n{CONSTRAINT_MUST} 【已建立的世界事实 - 必须严格遵守，不得矛盾】")
    else:
        lines.append(
            f"\n{CONSTRAINT_MUST} [Established World Facts - MUST STRICTLY FOLLOW, NO CONTRADICTIONS]"
        )

    total_chars = 0
    fact_count = 0

    for fact in sorted_facts:
        if fact_count >= max_facts:
            break

        category = fact.get("category", "fact")
        cat_label = labels.get(category, labels.get("fact", "Fact"))

        # 构建单条事实（使用压缩模式）
        compressed = _compress_fact(fact, language)
        if language == "zh":
            line = f"- 【{cat_label}】{compressed}"
        else:
            line = f"- [{cat_label}] {compressed}"

        # 检查长度限制
        if total_chars + len(line) > max_total_chars and fact_count > 0:
            # 如果是高优先级事实，仍然添加但标记截断
            if get_priority(fact) <= 1:  # 承诺或决策
                if language == "zh":
                    lines.append("...（更多事实已省略）")
                else:
                    lines.append("... (more facts omitted)")
            break

        lines.append(line)
        total_chars += len(line)
        fact_count += 1

    if language == "zh":
        lines.append(
            "故事中的人物角色、地理位置、正在处理的事务必须与以上事实一致，不得出现矛盾或随意变动。"
        )
    else:
        lines.append(
            "Character roles, geographic locations, and ongoing affairs MUST be consistent with the above facts. No contradictions or random changes."
        )

    return "\n".join(lines)


def _build_fallback_constraints(
    established_facts: Optional[list], language: str
) -> str:
    """
    当世界模型不可用时，从已建立事实中提取关键约束作为降级方案。

    Args:
        established_facts: 已建立的世界事实列表
        language: 语言代码

    Returns:
        降级约束文本
    """
    if not established_facts:
        return ""

    commitments = []
    locations = []

    for fact in sanitize_authoritative_fact_records(established_facts):
        fact_type = fact.get("category", "").lower()
        fact_text = fact.get("fact", "")
        subject = fact.get("subject", "")
        desc = f"{subject}：{fact_text}" if language == "zh" else f"{subject}: {fact_text}"

        if fact_type in ("commitment", "promise"):
            commitments.append(desc)
        elif fact_type == "location":
            locations.append(desc)

    if not commitments and not locations:
        return ""

    if language == "zh":
        parts = ["[降级约束] 以下约束从已建立事实中提取（世界模型不可用）："]
        for c in commitments:
            parts.append(f"- 承诺: {c}")
        for loc in locations:
            parts.append(f"- 位置: {loc}")
    else:
        parts = ["[Fallback Constraints] Extracted from established facts (world model unavailable):"]
        for c in commitments:
            parts.append(f"- Commitment: {c}")
        for loc in locations:
            parts.append(f"- Location: {loc}")

    return "\n".join(parts)


def _build_world_model_constraints(
    world_model: Optional[Any], language: str, established_facts: Optional[list] = None
) -> str:
    """
    构建世界模型约束文本段落，用于增强故事一致性。
    调用 WorldModel.build_constraints_text() 生成包含地理位置、职业、承诺、
    因果链和身体状态的综合约束。

    Args:
        world_model: WorldModel 实例（可为 None）
        language: 语言代码
        established_facts: 已建立的世界事实列表（用于降级）

    Returns:
        世界模型约束字符串
    """
    if world_model is None:
        return _build_fallback_constraints(established_facts, language)
    try:
        result: str = world_model.build_constraints_text(language)
        return f"{CONSTRAINT_MUST} {result}" if result else ""
    except Exception as e:
        logger.error(f"World model constraint build failed: {e}")
        return _build_fallback_constraints(established_facts, language)


def _build_full_character_context(
    character_settings: Optional[Dict[str, Any]], language: str
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    构建完整的角色上下文和可用人物列表。
    用于 get_event_generation_prompt 的中英文版本。

    Returns:
        (character_context_str, available_people_list)
    """
    if not character_settings:
        return "", []

    zh = language == "zh"
    char_parts = []
    available_people = _collect_available_people(character_settings)

    # Era
    if "era" in character_settings:
        era = character_settings["era"]
        if zh:
            char_parts.append(f"""时代背景：
- 年份：{era.get('year', '未知')}年
- 时代描述：{era.get('era_description', '')}
- 世界背景：{era.get('world_context', '')}""")
        else:
            char_parts.append(f"""Era Background:
- Year: {era.get('year', 'Unknown')} AD
- Era Description: {era.get('era_description', '')}
- World Context: {era.get('world_context', '')}""")

    # Age
    if "age" in character_settings:
        age_info = character_settings["age"]
        if zh:
            char_parts.append(f"""起始年龄：
- 年龄：{age_info.get('age', '未知')}岁
- 年龄阶段：{age_info.get('age_description', '')}""")
        else:
            char_parts.append(f"""Starting Age:
- Age: {age_info.get('age', 'Unknown')} years old
- Age Stage: {age_info.get('age_description', '')}""")

    # Gender
    if "gender" in character_settings:
        gender_info = character_settings["gender"]
        if zh:
            char_parts.append(f"""性别：
- 性别：{gender_info.get('gender', '未知')}
- 社会背景：{gender_info.get('gender_description', '')}""")
        else:
            char_parts.append(f"""Gender:
- Gender: {gender_info.get('gender', 'Unknown')}
- Social Context: {gender_info.get('gender_description', '')}""")

    # World
    if "world" in character_settings:
        world = character_settings["world"]
        if zh:
            char_parts.append(f"""世界与社会：
- 世界描述：{world.get('world_description', '')}
- 科技水平：{world.get('technology_level', '')}
- 社会制度：{world.get('social_system', '')}
- 经济状况：{world.get('economy', '')}""")
        else:
            char_parts.append(f"""World & Society:
- World Description: {world.get('world_description', '')}
- Technology Level: {world.get('technology_level', '')}
- Social System: {world.get('social_system', '')}
- Economy: {world.get('economy', '')}""")

    # Family
    if "family" in character_settings:
        family = character_settings["family"]
        raw_members = family.get("family_members", [])
        member_names = []
        for member in raw_members:
            if isinstance(member, dict):
                name = member.get("name", "")
                role = member.get("role", "")
                if name:
                    member_names.append(
                        f"{name}（{role}）" if zh else f"{name} ({role})"
                    )
            elif isinstance(member, str):
                member_names.append(member)

        sep = "、" if zh else ", "
        none_str = "无" if zh else "None"
        members_str = sep.join(member_names) if member_names else none_str

        if zh:
            char_parts.append(f"""家庭情况：
- 家庭描述：{family.get('family_description', '')}
- 家庭成员：{members_str}
- 家庭经济：{family.get('family_economy', '')}
- 家庭关系：{family.get('family_relationships', '')}""")
        else:
            char_parts.append(f"""Family:
- Family Description: {family.get('family_description', '')}
- Family Members: {members_str}
- Family Economy: {family.get('family_economy', '')}
- Family Relationships: {family.get('family_relationships', '')}""")

    # Relationships
    if "relationships" in character_settings:
        rel = character_settings["relationships"]
        people_str = _format_people_names(available_people, language)
        if zh:
            char_parts.append(f"""社会关系：
- 关系描述：{rel.get('relationships_description', '')}
- **可用人物列表（包含家人和关键人物，事件中的人物必须来自此列表）**：{people_str}""")
        else:
            char_parts.append(
                f"""Social Relationships:
- Relationship Description: {rel.get('relationships_description', '')}
- **Available People List (includes family and key people, all people in events MUST come from this list)**: {people_str}"""
            )

    # Traits
    if "traits" in character_settings:
        traits = character_settings["traits"]
        if zh:
            char_parts.append(f"""个人特点：
- 特点描述：{traits.get('traits_description', '')}
- 性格：{traits.get('personality', '')}
- 能力：{traits.get('abilities', '')}
- 兴趣：{traits.get('interests', '')}
- 优点：{traits.get('strengths', '')}
- 缺点：{traits.get('weaknesses', '')}""")
        else:
            char_parts.append(f"""Personal Traits:
- Traits Description: {traits.get('traits_description', '')}
- Personality: {traits.get('personality', '')}
- Abilities: {traits.get('abilities', '')}
- Interests: {traits.get('interests', '')}
- Strengths: {traits.get('strengths', '')}
- Weaknesses: {traits.get('weaknesses', '')}""")

    character_context = "\n".join(char_parts) if char_parts else ""
    return character_context, available_people


def _format_effects(effects: Dict[str, Any], language: str) -> str:
    """
    Format effects dictionary into readable string.

    Args:
        effects: Effects dictionary
        language: Language code

    Returns:
        Formatted string
    """
    if not effects:
        return "无" if language == "zh" else "None"

    parts = []
    labels = {
        "zh": {"energy": "精力", "mood": "情绪", "knowledge": "学识"},
        "en": {
            "energy": "Energy",
            "mood": "Mood",
            "knowledge": "Knowledge",
        },
    }

    for key in ["energy", "mood", "knowledge"]:
        val = effects.get(key, 0)
        if val != 0:
            label = labels.get(language, labels["en"]).get(key, key)
            sign = "+" if val > 0 else ""
            parts.append(f"{label}{sign}{val}")

    return "、".join(parts) if parts else ("无" if language == "zh" else "None")


# ==================== Common Constraints ====================


def _build_common_story_constraints(language: str, quality_level: str = "expert") -> str:
    """
    构建故事生成的公共约束，所有故事生成提示词都应包含。

    包含：
    1. 第三人称叙事要求
    2. 禁止跳脱叙事（第四面墙）
    3. 禁止编造过往事件
    4. 故事结尾决策点要求

    Args:
        language: 语言代码
        quality_level: 质量级别 (fast/expert/master)

    Returns:
        公共约束字符串
    """
    level = quality_level.lower() if quality_level else "expert"

    if language == "zh":
        if level == "fast":
            return f"""
【核心叙事约束 - 快速模式】
1. {CONSTRAINT_MUST} **人称要求**：必须使用第三人称叙事（"他/她"而非"我/你"）
2. {CONSTRAINT_MUST} **禁止跳脱叙事**：禁止提及"游戏""系统""属性值"等元信息
3. {CONSTRAINT_MUST} **故事结尾要求**：故事结尾必须停在一个具体决策点
4. {CONSTRAINT_MUST} **正确使用标点**：对话必须用""包裹，句末使用句号/问号/感叹号，句内用逗号/顿号合理断句。禁止出现没有标点的大段连续文字
"""
        if level == "master":
            return f"""
【核心叙事约束 - 大师级严格标准】
1. {CONSTRAINT_MUST} **人称要求**：必须使用第三人称叙事（"他/她"而非"我/你"），保持全文人称绝对统一，严禁任何视角滑移
2. {CONSTRAINT_MUST} **禁止跳脱叙事**：故事中绝对不能出现任何打破第四面墙的内容，包括但不限于：
   - 提及"游戏""模拟""系统""属性值""精力值""情绪值"等元信息
   - 出现作者旁白、对读者说话、解释创作意图
   - 出现对故事本身的评论或总结性元叙述
   故事应完全沉浸在角色的世界中，杜绝一切元叙事
3. {CONSTRAINT_MUST} **禁止编造过往事件**：故事中提到的任何过去发生的事情，必须来自提供的上下文（上周故事、近期总结、年度回顾、剧情线等）。绝对禁止凭空捏造从未发生过的回忆、对话、事件或经历。不确定的过往不要提及
4. {CONSTRAINT_MUST} **故事结尾要求**：故事结尾必须停在一个具体、明确的决策点！
   - 正确示例：「她说："明天一早跟我走，怎么样？"」「他递来一把钥匙："这是你自己的选择了。"」「父亲沉声道："你自己拿主意吧。"」
   - 错误示例：「他们相视而笑。」（无决策点）、「一切都已经不一样了。」（纯情感结尾）
   - 故事结尾必须是：某人说出一句话需要主角回应、面临两个选择、需要做出承诺、需要表态等
   - **绝对禁止**以纯情感描写或感慨收尾，必须有具体的"下一步怎么办"的悬念
5. {CONSTRAINT_MUST} **文学编辑标准**：
   - 每个场景必须有清晰的环境描写和感官细节
   - 对话必须自然推动情节，避免功能性说明
   - 人物行为必须符合其性格和背景设定
   - 情绪变化必须有充分的情节铺垫
6. {CONSTRAINT_MUST} **标点符号规范（违反即失败）**：
   - 对话必须用中文引号 "" 包裹，如：她说："你今天怎么来了？"
   - 每句话末尾必须使用句号、问号或感叹号
   - 句内必须使用逗号、顿号合理断句，禁止出现超过30字无标点的情况
   - 禁止出现没有标点的大段连续文字
   - 标点禁止中英混用
7. {CONSTRAINT_SHOULD} **大师级写作建议**：注意故事节奏的张弛有度，避免平铺直叙；在关键决策点前营造适当的紧张感或期待感
"""
        # expert (default)
        return f"""
【核心叙事约束 - 必须严格遵守】
1. {CONSTRAINT_MUST} **人称要求**：必须使用第三人称叙事（"他/她"而非"我/你"），保持全文人称统一
2. {CONSTRAINT_MUST} **禁止跳脱叙事**：故事中绝对不能出现任何打破第四面墙的内容，包括但不限于：
   - 提及"游戏""模拟""系统""属性值""精力值""情绪值"等元信息
   - 出现作者旁白、对读者说话、解释创作意图
   - 出现对故事本身的评论或总结性元叙述
   故事应完全沉浸在角色的世界中
3. {CONSTRAINT_MUST} **禁止编造过往事件**：故事中提到的任何过去发生的事情，必须来自提供的上下文（上周故事、近期总结、年度回顾、剧情线等）。绝对禁止凭空捏造从未发生过的回忆、对话、事件或经历。不确定的过往不要提及
4. {CONSTRAINT_MUST} **故事结尾要求**：故事结尾必须停在一个具体、明确的决策点！
   - 正确示例：「她说："明天一早跟我走，怎么样？"」「他递来一把钥匙："这是你自己的选择了。"」「父亲沉声道："你自己拿主意吧。"」
   - 错误示例：「他们相视而笑。」（无决策点）、「一切都已经不一样了。」（纯情感结尾）
   - 故事结尾必须是：某人说出一句话需要主角回应、面临两个选择、需要做出承诺、需要表态等
   - **绝对禁止**以纯情感描写或感慨收尾，必须有具体的"下一步怎么办"的悬念
5. {CONSTRAINT_MUST} **正确使用标点符号**：
   - 对话必须用中文引号 "" 包裹
   - 每句话末尾必须使用句号、问号或感叹号
   - 句内必须使用逗号、顿号合理断句，禁止出现超过30字无标点的情况
   - 禁止出现没有标点的大段连续文字
   - 标点禁止中英混用
6. {CONSTRAINT_SHOULD} **写作建议**：注意故事节奏的张弛有度，避免平铺直叙
"""
    else:
        if level == "fast":
            return f"""
[Core Narrative Constraints - Fast Mode]
1. {CONSTRAINT_MUST} **Perspective**: MUST use third-person narration ("he/she" not "I/you")
2. {CONSTRAINT_MUST} **NO FOURTH-WALL BREAKING**: Never mention 'game', 'system', 'stats', etc.
3. {CONSTRAINT_MUST} **STORY ENDING REQUIREMENT**: Story MUST end at a concrete decision point
4. {CONSTRAINT_MUST} **Proper Punctuation**: Dialogue MUST be in quotation marks. Every sentence MUST end with a period, question mark, or exclamation. Use commas and semicolons for clause breaks. No run-on paragraphs without punctuation
"""
        if level == "master":
            return f"""
[Core Narrative Constraints - Master Strict Standard]
1. {CONSTRAINT_MUST} **Perspective**: MUST use third-person narration ("he/she" not "I/you"), maintain absolutely consistent perspective throughout, no perspective drift allowed
2. {CONSTRAINT_MUST} **NO FOURTH-WALL BREAKING**: The story must NEVER contain:
   - References to 'game', 'simulation', 'system', 'stats', 'energy points', 'mood value', or any meta-information
   - Author asides, addressing the reader, explaining creative intent
   - Commentary or meta-narrative about the story itself
   The story must remain fully immersed in the character's world; eliminate all meta-narrative
3. {CONSTRAINT_MUST} **DO NOT FABRICATE PAST EVENTS**: Any past events mentioned in the story MUST come from the provided context (previous story, recent summary, annual review, storylines, etc.). ABSOLUTELY FORBIDDEN to invent memories, conversations, events or experiences that never happened. Do not mention uncertain past events
4. {CONSTRAINT_MUST} **STORY ENDING REQUIREMENT**: Story MUST end at a concrete, specific decision point!
   - Good: 'She said, "Come with me tomorrow morning, what do you say?"' 'He handed over a key: "This is your choice now."' 'Father said gravely: "Make your own decision."'
   - Bad: 'They looked at each other and smiled.' (no decision point) 'Everything has changed.' (pure emotional ending)
   - Ending MUST be: someone asks a question requiring response, facing two paths, needing to make a promise, needing to take a stance, etc.
   - **ABSOLUTELY FORBIDDEN** to end with pure emotional reflection or sentiment - there must be a concrete "what happens next" tension
5. {CONSTRAINT_MUST} **Literary Editor Standard**:
   - Every scene must have clear environmental description and sensory details
   - Dialogue must naturally advance the plot, avoid functional exposition
   - Character actions MUST align with their personality and background
   - Emotional changes MUST have sufficient plot buildup
6. {CONSTRAINT_MUST} **Proper Punctuation (violation = failure)**:
   - Dialogue MUST be wrapped in quotation marks, e.g.: She said, "Why are you here today?"
   - Every sentence MUST end with a period, question mark, or exclamation mark
   - Use commas and semicolons for clause breaks; no run-on sentences over 30 words without punctuation
   - No paragraphs without any punctuation
   - Do not mix Chinese and English punctuation
7. {CONSTRAINT_SHOULD} **Master-Level Writing Advice**: Pay attention to story pacing; create appropriate tension or anticipation before key decision points
"""
        # expert (default)
        return f"""
[Core Narrative Constraints - MUST STRICTLY FOLLOW]
1. {CONSTRAINT_MUST} **Perspective**: MUST use third-person narration ("he/she" not "I/you"), maintain consistent perspective throughout
2. {CONSTRAINT_MUST} **NO FOURTH-WALL BREAKING**: The story must NEVER contain:
   - References to 'game', 'simulation', 'system', 'stats', 'energy points', 'mood value', or any meta-information
   - Author asides, addressing the reader, explaining creative intent
   - Commentary or meta-narrative about the story itself
   The story must remain fully immersed in the character's world
3. {CONSTRAINT_MUST} **DO NOT FABRICATE PAST EVENTS**: Any past events mentioned in the story MUST come from the provided context (previous story, recent summary, annual review, storylines, etc.). ABSOLUTELY FORBIDDEN to invent memories, conversations, events or experiences that never happened. Do not mention uncertain past events
4. {CONSTRAINT_MUST} **STORY ENDING REQUIREMENT**: Story MUST end at a concrete, specific decision point!
   - Good: 'She said, "Come with me tomorrow morning, what do you say?"' 'He handed over a key: "This is your choice now."' 'Father said gravely: "Make your own decision."'
   - Bad: 'They looked at each other and smiled.' (no decision point) 'Everything has changed.' (pure emotional ending)
   - Ending MUST be: someone asks a question requiring response, facing two paths, needing to make a promise, needing to take a stance, etc.
   - **ABSOLUTELY FORBIDDEN** to end with pure emotional reflection or sentiment - there must be a concrete "what happens next" tension
5. {CONSTRAINT_MUST} **Proper Punctuation**:
   - Dialogue MUST be wrapped in quotation marks
   - Every sentence MUST end with a period, question mark, or exclamation mark
   - Use commas and semicolons for clause breaks; no run-on sentences over 30 words without punctuation
   - No paragraphs without any punctuation
   - Do not mix Chinese and English punctuation
6. {CONSTRAINT_SHOULD} **Writing Advice**: Pay attention to story pacing, avoid flat narration
"""


def _build_character_name_constraint(available_people: List[str], language: str) -> str:
    """
    构建人物名约束。

    Args:
        available_people: 可用人物名列表
        language: 语言代码

    Returns:
        人物名约束字符串
    """
    if not available_people:
        return ""

    names_str = (
        "、".join(available_people) if language == "zh" else ", ".join(available_people)
    )

    if language == "zh":
        return f"""
【人物约束 - 严格禁止创造新人物】
- 所有出现在事件中的人物名字必须且只能来自以下列表：{names_str}
- 绝对禁止凭空创造任何新人物名字
- 如果需要其他人物，请使用模糊称谓（如"一位同事""一个朋友""陌生人"等）
"""
    else:
        return f"""
[Character Constraint - STRICTLY FORBIDDEN to create new characters]
- All character names in events MUST and ONLY come from this list: {names_str}
- ABSOLUTELY FORBIDDEN to create any new character names
- If other characters are needed, use generic terms (e.g., "a colleague", "a friend", "a stranger")
"""


def extract_overused_phrases(
    decision_history: List[Dict[str, Any]],
    min_freq: int = 3,
    max_phrases: int = 15,
    language: str = "zh",
) -> str:
    """
    从历史故事中动态提取高频重复短语，生成禁用列表注入prompt。

    三重策略：
    1. 滑动窗口提取跨故事重复的描写性短语（8-15字）
    2. 提取重复的完整句子（多篇故事中出现相同句子）
    3. 提取重复的故事开头模式（多个故事以相似方式开头）

    Args:
        decision_history: 决策历史列表
        min_freq: 最小出现次数才认为是“过度使用”
        max_phrases: 最多返回多少个短语
        language: 语言

    Returns:
        格式化的禁用短语文本，可直接插入prompt。若无高频短语则返回空字符串。
    """
    import re
    from collections import Counter

    if not decision_history or len(decision_history) < 3:
        return ""

    # 收集所有故事文本
    stories: List[str] = []
    for d in decision_history:
        event = d.get("event", "")
        if event and len(event) > 20:
            stories.append(event)

    if len(stories) < 3:
        return ""

    # 动态调整阈值：故事越多，阈值可以越低
    effective_min_freq = min_freq if len(stories) <= 10 else 2

    ban_items: List[str] = []

    # === 策略一（最重要）：提取重复的故事开头模式 ===
    opening_keywords: Counter = Counter()
    for story in stories:
        first_part = story[:30]
        for keyword in ["晨光", "晨雾", "暮色", "夜色", "月光", "午后",
                        "烛火", "天明", "黄昏", "午时", "卵时",
                        "晨钟", "清晨", "破晓", "曙光"]:
            if keyword in first_part:
                opening_keywords[keyword] += 1

    for keyword, count in opening_keywords.most_common():
        if count >= 3:
            ban_items.append(
                f"以“{keyword}”开头的场景（已用{count}次，必须换其他时间/场景切入）"
            )

    # === 策略二：提取多故事重复的完整句子 ===
    sentence_story_count: Counter = Counter()
    for story in stories:
        sentences = re.split(r'[。！？\n]', story)
        seen_sents: set = set()
        for s in sentences:
            s = s.strip()
            if len(s) >= 15 and s not in seen_sents:
                seen_sents.add(s)
                sentence_story_count[s] += 1

    for sent, count in sentence_story_count.most_common(20):
        if count >= effective_min_freq:
            display = sent[:40] + ("…" if len(sent) > 40 else "")
            ban_items.append(f"“{display}”（完整句子在{count}篇中重复）")

    # 收集已禁用句子的文本，用于过滤策略三中的重复短语
    banned_text = " ".join(ban_items)

    # === 策略三：提取跨故事重复的描写性短语（8-15字） ===
    phrase_counter: Counter = Counter()
    for story in stories:
        seen_in_story: set = set()
        for length in [8, 10, 12, 15]:
            for i in range(len(story) - length + 1):
                phrase = story[i:i + length]
                # 跳过包含换行符的短语
                if '\n' in phrase:
                    continue
                if re.search(r'[\u4e00-\u9fff]{5,}', phrase):
                    if phrase not in seen_in_story:
                        seen_in_story.add(phrase)
                        phrase_counter[phrase] += 1

    frequent = [
        (p, c) for p, c in phrase_counter.most_common(300)
        if c >= effective_min_freq
    ]

    # 去重：长短语包含短短语时只保留长的
    filtered_phrases = []
    for phrase, count in frequent:
        is_sub = False
        for p2, c2 in frequent:
            if len(p2) > len(phrase) and phrase in p2 and c2 >= count * 0.7:
                is_sub = True
                break
        if not is_sub:
            filtered_phrases.append((phrase, count))

    for phrase, count in filtered_phrases:
        if '“' in phrase and '”' in phrase:
            continue
        if len(phrase) <= 8 and not any(c in phrase for c in '的地得了着过在从与'):
            continue
        # 跳过已被更长句子覆盖的短语
        if phrase in banned_text:
            continue
        ban_items.append(f"“{phrase}”（{count}篇故事重复）")

    if not ban_items:
        return ""

    # 截取前 N 个
    ban_items = ban_items[:max_phrases]

    # 格式化输出
    if language == "zh":
        lines = [f"  - {item}" for item in ban_items]
        return (
            "\n【★ 动态禁用列表 - 以下表达已被过度使用，本次严禁使用】\n"
            "必须用全新的描写方式替代：\n"
            + "\n".join(lines)
            + "\n❗ 不是禁止提及相关事物，而是禁止用这些完全相同的句式/开头来描写。请换一种角度、一种感官、一种句式来写。"
        )
    else:
        lines = [f"  - {item}" for item in ban_items]
        return (
            "\n[DYNAMIC BAN LIST - These expressions are overused, DO NOT use them]\n"
            "You MUST use completely different wording:\n"
            + "\n".join(lines)
            + "\n! It's not about avoiding the topics, but about using fresh descriptions."
        )


def _build_critical_summary(
    pending_storylines: Optional[list] = None,
    established_facts: Optional[list] = None,
    world_model: Optional[Any] = None,
    language: str = "zh",
) -> str:
    """
    构建红线约束摘要（约50-100 tokens），用于在 prompt 开头和结尾强化关键约束。
    只提取最关键的约束信息，格式极度精简。
    """
    parts: List[str] = []

    # 1. 从 pending_storylines 中提取 overdue 剧情线（最多3条）
    if pending_storylines:
        overdue = [
            sl.get("description", "")[:20]
            for sl in pending_storylines
            if sl.get("importance") == "high" and sl.get("overdue", False)
        ][:3]
        if overdue:
            joined = "; ".join(overdue) if language == "zh" else "; ".join(overdue)
            if language == "zh":
                parts.append(f"• 过期剧情: {joined}")
            else:
                parts.append(f"• Overdue storylines: {joined}")

    # 2. 从 established_facts 中提取 priority <= 1（承诺/决策）的事实（最多5条）
    if established_facts:
        critical_facts: List[str] = []
        for fact in sanitize_authoritative_fact_records(established_facts):
            if len(critical_facts) >= 5:
                break
            category = fact.get("category", "").lower()
            fact_text = fact.get("fact", "")
            subject = fact.get("subject", "")
            # 承诺或决策类
            is_commitment = category in ("commitment", "promise") or any(
                kw in fact_text.lower()
                for kw in ("承诺", "答应", "promise", "决定", "选择", "decision", "chose")
            )
            if is_commitment:
                short = f"{subject}: {fact_text}"[:30]
                critical_facts.append(short)
        if critical_facts:
            joined = "; ".join(critical_facts)
            if language == "zh":
                parts.append(f"• 关键承诺: {joined}")
            else:
                parts.append(f"• Key commitments: {joined}")

    # 3. 从 world_model 中提取 CRITICAL 位置约束
    if world_model is not None:
        try:
            loc_text = world_model.get_protagonist_location(language) if hasattr(world_model, "get_protagonist_location") else None
            if loc_text:
                if language == "zh":
                    parts.append(f"• 位置约束: {loc_text}")
                else:
                    parts.append(f"• Location: {loc_text}")
        except Exception:
            pass

    if not parts:
        return ""

    items = "\n".join(parts)
    if language == "zh":
        return f"""[MUST] 本轮红线约束速览：
{items}
违反以上任何一条将导致生成失败。"""
    else:
        return f"""[MUST] Critical constraints summary for this round:
{items}
Violating ANY of the above will cause generation failure."""


# ==================== Style / Narrative Integration Helpers ====================


def _build_style_constraints_text(style_prompt_builder, language: str) -> str:
    """构建风格约束文本（硬约束 + 软建议 + 结尾hook）。

    Args:
        style_prompt_builder: StyleAwarePromptBuilder 实例
        language: 语言代码

    Returns:
        合并后的风格约束文本，无风格时返回空字符串
    """
    if style_prompt_builder is None:
        return ""
    try:
        parts: list = []
        hard = style_prompt_builder.build_style_hard_constraints()
        if hard:
            parts.append(hard)
        soft = style_prompt_builder.build_style_soft_suggestions()
        if soft:
            parts.append(soft)
        ending = style_prompt_builder.build_chapter_ending_hint()
        if ending:
            parts.append(ending)
        return "\n".join(parts)
    except Exception as e:
        logger.warning("_build_style_constraints_text failed: %s", e)
        return ""


def _build_arc_context(character_arc_engine, player_name: str) -> str:
    """构建人物弧光上下文。

    Args:
        character_arc_engine: CharacterArcEngine 实例
        player_name: 主角名称

    Returns:
        弧光约束文本，不可用时返回空字符串
    """
    if character_arc_engine is None or not player_name:
        return ""
    try:
        arc = character_arc_engine.arcs.get(player_name)
        return character_arc_engine.generate_constraint(arc)  # type: ignore[no-any-return]
    except Exception as e:
        logger.warning("_build_arc_context failed: %s", e)
        return ""
