"""AI prompt helper functions for context building."""
from typing import Dict, Any, Optional, List, Tuple


def _collect_available_people(character_settings: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
        for member in character_settings["family"].get('family_members', []):
            if isinstance(member, dict) and member.get('name'):
                available_people.append(member)
    
    # Collect key_people, avoid duplicates
    if "relationships" in character_settings:
        for person in character_settings["relationships"].get('key_people', []):
            name = person.get('name', '')
            if name and not any(p.get('name') == name for p in available_people):
                available_people.append(person)
    
    return available_people


def _format_people_names(available_people: list, language: str, include_role: bool = True) -> str:
    """格式化人物列表为可读字符串。"""
    if not available_people:
        return "无" if language == "zh" else "None"
    
    sep = "、" if language == "zh" else ", "
    if include_role:
        if language == "zh":
            parts = [f"{p.get('name', '')}（{p.get('role', '')}）" for p in available_people if p.get('name')]
        else:
            parts = [f"{p.get('name', '')} ({p.get('role', '')})" for p in available_people if p.get('name')]
    else:
        parts = [p.get('name', '') for p in available_people if p.get('name')]
    
    return sep.join(parts) if parts else ("无" if language == "zh" else "None")


def _build_new_character_intro_context(new_character: Optional[Dict[str, Any]], language: str) -> str:
    """构建新人物引入提示，指导AI自然地在故事中引入新角色。
    
    关键：此函数会生成一个醒目的提示块，确保 AI 理解这是新人物的首次登场。
    """
    if not new_character:
        return ""
    
    name = new_character.get("name", "")
    role = new_character.get("role", "")
    relationship = new_character.get("relationship", "")
    relationship_desc = new_character.get("relationship_desc", "")
    personality = ", ".join(new_character.get("personality_traits", [])) if new_character.get("personality_traits") else ""
    occupation = new_character.get("occupation", "")
    
    if not name:
        return ""
    
    if language == "zh":
        parts = ["\n\n" + "="*50]
        parts.append("【本轮新登场人物 - 首次出现】")
        parts.append("="*50)
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
        parts.append('写作要求（非常重要）：')
        parts.append('  1. 这是此人物**第一次**出现在主角的生活中')
        parts.append('  2. 必须安排一个合理的「相识/相遇」场景')
        parts.append('  3. 禁止让此人物像老朋友一样突然出现')
        parts.append('  4. 禁止假设主角已经认识TA')
        parts.append('  5. 禁止让他们之间有「过去的回忆」或「之前的互动」')
        parts.append('  6. 故事应该围绕或包含这次**初次相遇/接触**展开')
        parts.append("="*50)
        return "\n".join(parts)
    else:
        parts = ["\n\n" + "="*50]
        parts.append("【NEW CHARACTER - FIRST APPEARANCE】")
        parts.append("="*50)
        parts.append(f"\nNote: Character **{name}** is appearing for the FIRST TIME in this round!")
        parts.append("")
        parts.append("Character Info:")
        if role:
            parts.append(f"  - Role: {role}")
        if occupation:
            parts.append(f"  - Occupation: {occupation}")
        if relationship or relationship_desc:
            parts.append(f"  - Relationship to protagonist: {relationship or relationship_desc}")
        if personality:
            parts.append(f"  - Personality: {personality}")
        parts.append("")
        parts.append("Writing Requirements (VERY IMPORTANT):")
        parts.append("  1. This is the character's FIRST EVER appearance")
        parts.append("  2. Must write a natural 'meeting/encounter' scene")
        parts.append("  3. FORBIDDEN to have them appear as an old friend")
        parts.append("  4. FORBIDDEN to assume protagonist already knows them")
        parts.append("  5. FORBIDDEN to reference 'past memories' or 'previous interactions'")
        parts.append("  6. Story should revolve around this FIRST meeting/encounter")
        parts.append("="*50)
        return "\n".join(parts)


def _build_available_people_constraint(available_people: list, language: str) -> str:
    """构建"可用人物列表"约束字符串，用于提示词。"""
    if not available_people:
        return ""
    
    names = [p.get('name', '') for p in available_people if p.get('name')]
    if not names:
        return ""
    
    names_str = ', '.join(names)
    if language == "zh":
        return f"\n**可用人物列表（事件中的人物必须且只能来自此列表）**：{names_str}"
    else:
        return f"\n**Available People List (all people in events MUST and ONLY come from this list)**: {names_str}"


def _build_time_context(
    game_date_info: Optional[Dict[str, Any]],
    language: str
) -> str:
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
        season_en = {"春": "Spring", "夏": "Summer", "秋": "Autumn", "冬": "Winter"}.get(season, season)
        return f"""\n[Current Time]
{date_str} ({season_en}), protagonist age {age}, Week {total_week}"""


def _build_pending_storylines_context(
    pending_storylines: Optional[list],
    language: str
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
    
    # 分离高/中重要性剧情线
    high_storylines = [sl for sl in pending_storylines if sl.get("importance") == "high"]
    medium_storylines = [sl for sl in pending_storylines if sl.get("importance") != "high"]
    
    if language == "zh":
        lines = ["\n【未完结的重要剧情线】"]
        if high_storylines:
            lines.append("**必须在故事中涉及以下高重要性剧情线（至少一条）：**")
            for sl in high_storylines:
                desc = sl.get("description", "")
                created_week = sl.get("created_week", 0) + 1  # ★ week 从0开始，显示时+1
                characters = sl.get("related_characters", [])
                char_str = f"，涉及人物: {'、'.join(characters)}" if characters else ""
                lines.append(f"- 【高】第{created_week}周起: {desc}{char_str}")
        if medium_storylines:
            lines.append("\n可选择性延续的剧情线：")
            for sl in medium_storylines:
                desc = sl.get("description", "")
                created_week = sl.get("created_week", 0) + 1  # ★ week 从0开始，显示时+1
                characters = sl.get("related_characters", [])
                char_str = f"，涉及人物: {'、'.join(characters)}" if characters else ""
                lines.append(f"- 【中】第{created_week}周起: {desc}{char_str}")
        if high_storylines:
            lines.append("\n强制要求：故事必须自然地涉及至少一条高重要性剧情线，可以是续写发展、回应或解决。不能完全忽略这些未完结的重要事件。")
        else:
            lines.append("\n建议自然地延续或回应以上剧情线。如果剧情自然结束，无需强行续写。")
        return "\n".join(lines)
    else:
        lines = ["\n[Pending Important Storylines]"]
        if high_storylines:
            lines.append("**MUST address at least one of these HIGH-importance storylines in the story:**")
            for sl in high_storylines:
                desc = sl.get("description", "")
                created_week = sl.get("created_week", 0)
                characters = sl.get("related_characters", [])
                char_str = f", involving: {', '.join(characters)}" if characters else ""
                lines.append(f"- [HIGH] Since week {created_week}: {desc}{char_str}")
        if medium_storylines:
            lines.append("\nOptional storylines to continue:")
            for sl in medium_storylines:
                desc = sl.get("description", "")
                created_week = sl.get("created_week", 0)
                characters = sl.get("related_characters", [])
                char_str = f", involving: {', '.join(characters)}" if characters else ""
                lines.append(f"- [MEDIUM] Since week {created_week}: {desc}{char_str}")
        if high_storylines:
            lines.append("\nMANDATORY: Story MUST naturally involve at least one high-importance storyline - continue, address, or resolve it. Cannot completely ignore these unresolved important events.")
        else:
            lines.append("\nSuggested: Naturally continue or address the above storylines. Don't force continuation if the plot naturally concludes.")
        return "\n".join(lines)


def _build_continuation_mandate(
    last_event_concluded: bool,
    last_round_full_story: str,
    language: str
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
            return f"""\n【必须续写上一轮未完结的故事】
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
            return f"""\n[MUST CONTINUE THE UNFINISHED STORY FROM LAST ROUND]
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
            return f"""\n【上一轮故事背景 - 必须保持叙事连贯】
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
            return f"""\n[PREVIOUS ROUND STORY CONTEXT - MUST MAINTAIN NARRATIVE CONTINUITY]
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
    character_habits: Optional[list],
    language: str
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
        lines = ["\n【人物习惯记录 - 必须在故事中体现，保持角色行为一致性】"]
        strength_label = {"strong": "根深蒂固", "moderate": "明显", "emerging": "初现"}
        cat_label = {"behavioral": "行为", "speech": "言语", "emotional": "情绪", "social": "社交", "lifestyle": "生活"}
        for char_name, habits in habits_by_char.items():
            lines.append(f"\n- {char_name}：")
            for h in habits:
                cat = cat_label.get(h.get("category", ""), "其他")
                strength = strength_label.get(h.get("strength", "moderate"), "明显")
                origin = h.get("origin", "")
                origin_part = f"（来源：{origin}）" if origin else ""
                lines.append(f"  - 【{cat}/{strength}】{h.get('habit', '')}{origin_part}")
        lines.append("\n角色在故事中的行为应自然体现以上习惯。习惯不需要每次都明确提及，但行为不应与已建立的习惯矛盾。"
         "\n如果某个事件导致习惯发生变化，应在故事中自然地体现这种转变过程。")
        return "\n".join(lines)
    else:
        lines = ["\n[Character Habits - MUST be reflected in story, maintain behavioral consistency]"]
        strength_label = {"strong": "deep-rooted", "moderate": "notable", "emerging": "emerging"}
        cat_label = {"behavioral": "Behavioral", "speech": "Speech", "emotional": "Emotional", "social": "Social", "lifestyle": "Lifestyle"}
        for char_name, habits in habits_by_char.items():
            lines.append(f"\n> {char_name}:")
            for h in habits:
                cat = cat_label.get(h.get("category", ""), "Other")
                strength = strength_label.get(h.get("strength", "moderate"), "notable")
                origin = h.get("origin", "")
                origin_part = f" (origin: {origin})" if origin else ""
                lines.append(f"  - [{cat}/{strength}] {h.get('habit', '')}{origin_part}")
        lines.append("\nCharacters should naturally exhibit these habits in the story. Habits don't need explicit mention every time, but behavior should not contradict established habits."
         "\nIf an event causes a habit to change, show the transition naturally in the story.")
        return "\n".join(lines)


def _build_foreshadowing_context(
    activated_seed: Optional[Dict[str, Any]],
    language: str
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
        "character_return": "之前出现过的人物带着新变化回来"
    }
    type_hints_en = {
        "mystery": "A mysterious element resurfaces",
        "relationship": "A relationship undercurrent bears new fruit",
        "warning": "A past warning or omen now comes true",
        "opportunity": "A previously noted opportunity reappears",
        "consequence": "Consequences of past actions now manifest",
        "character_return": "A character from the past returns with changes"
    }
    
    # 回收方式描述
    recycle_hints_zh = {
        "revelation": "通过揭露一个之前隐藏的秘密/真相来回收",
        "confirmation": "通过事实验证之前的预感/猜测来回收",
        "ironic_twist": "通过讽刺性的反转（与当初预期相反的结果）来回收",
        "escalation": "通过事态升级、情况恶化/爆发来回收",
        "echo": "通过微妙的呼应、似曾相识的场景来回收"
    }
    recycle_hints_en = {
        "revelation": "Recover by revealing a hidden secret/truth",
        "confirmation": "Recover by confirming a prior intuition/guess",
        "ironic_twist": "Recover through an ironic reversal (opposite of expected outcome)",
        "escalation": "Recover through situation escalation/eruption",
        "echo": "Recover through subtle resonance, a deja vu moment"
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
        "major": "伏笔回响应成为推动本轮故事发展的关键因素之一"
    }
    weight_hints_en = {
        "minor": "The echo should exist as a decorative detail, not altering the main plot",
        "supporting": "The echo should serve as an important subplot element, enriching story layers",
        "major": "The echo should become one of the key drivers of this round's story"
    }
    
    chars_str = "、".join(characters) if characters else ""
    
    if language == "zh":
        type_hint = type_hints_zh.get(seed_type, "之前埋下的伏笔现在回响")
        recycle_hint = recycle_hints_zh.get(recycle, "通过自然的方式回收")
        weight_hint = weight_hints_zh.get(weight, weight_hints_zh["supporting"])
        
        lines = [
            f"\n【伏笔回响 — 草蛇灰线，伏脉千里】",
            f"在第{planted_week}周，故事中埋下了一个伏笔：",
            f"「{desc}」",
        ]
        if context:
            lines.append(f"当时的场景：{context}")
        if chars_str:
            lines.append(f"涉及人物：{chars_str}")
        lines.append(f"")
        lines.append(f"请{intensity_zh}将这个伏笔的回响编织进本轮故事：{type_hint}。")
        lines.append(f"")
        lines.append(f"【隐蔽度指导】{intensity_detail_zh}")
        lines.append(f"【回收方式】{recycle_hint}")
        lines.append(f"【叙事角色】{weight_hint}")
        lines.append(f"")
        lines.append(f"克制与延迟满足的艺术：")
        lines.append(f"- 不要一次揭示全部——留白是力量。只展现伏笔回响的一个切面")
        lines.append(f"- 回响可以引发新的疑问，而非回答所有问题")
        lines.append(f"- 让读者自己'发现'关联，而非由叙述者指出")
        lines.append(f"- 引入方式：人物对话、巧合重逢、意外发现、消息传来、梦境、相似情境")
        lines.append(f"- 禁止直接提及'伏笔''回响''草蛇灰线''呼应''命运''前因后果'等元叙述词汇")
        return "\n".join(lines)
    else:
        type_hint = type_hints_en.get(seed_type, "A past foreshadowing now echoes")
        recycle_hint = recycle_hints_en.get(recycle, "Recover naturally")
        weight_hint = weight_hints_en.get(weight, weight_hints_en["supporting"])
        
        lines = [
            f"\n[FORESHADOWING ECHO — Subtle Threads, Distant Echoes]",
            f"In Week {planted_week}, a seed was planted in the story:",
            f'"{desc}"',
        ]
        if context:
            lines.append(f"Original scene: {context}")
        if chars_str:
            lines.append(f"Characters involved: {', '.join(characters)}")
        lines.append(f"")
        lines.append(f"Weave this echo {intensity_en} into the current story: {type_hint}.")
        lines.append(f"")
        lines.append(f"[Concealment Guidance] {intensity_detail_en}")
        lines.append(f"[Recovery Method] {recycle_hint}")
        lines.append(f"[Narrative Role] {weight_hint}")
        lines.append(f"")
        lines.append(f"The Art of Restraint & Delayed Gratification:")
        lines.append(f"- Don't reveal everything at once — show only ONE facet of the echo")
        lines.append(f"- The echo can raise new questions rather than answering all of them")
        lines.append(f"- Let readers 'discover' the connection themselves, don't spell it out")
        lines.append(f"- Introduction methods: dialogue, coincidental meeting, unexpected discovery, news arriving, dreams, parallel situations")
        lines.append(f"- NEVER mention 'foreshadowing', 'echo', 'callback', 'destiny', 'fate', 'cause and effect', or any meta-narrative terms")
        return "\n".join(lines)


def _build_logic_constraints(game_date_info: Optional[Dict[str, Any]], language: str) -> str:
    """
    构建逻辑性约束文本，用于注入事件生成提示词。
    """
    if not game_date_info:
        return ""
    
    date_str = game_date_info.get("date_string", "")
    season = game_date_info.get("season", "")
    
    if language == "zh":
        return f"""\n11. **时间与逻辑一致性（必须严格遵守）**：
    - 严格遵守时间线：当前是{date_str}，{season}季，故事中的时间、季节、天气等应与此一致
    - 人物动机一致性：人物行为应符合其性格设定和当前处境
    - 因果逻辑一致性：事件的发展应符合因果关系，不能出现前后矛盾
    - 人物目标一致性：主角的行为应符合其人生愿景和当前目标"""
    else:
        date_str_en = game_date_info.get("date_string_en", "")
        season_en = {"春": "Spring", "夏": "Summer", "秋": "Autumn", "冬": "Winter"}.get(season, season)
        return f"""\n11. **Time & Logic Consistency (MUST STRICTLY FOLLOW)**:
    - Strict timeline: Current is {date_str_en}, {season_en}, story time/season/weather must match
    - Character motivation consistency: Characters must act according to their personality and current situation
    - Causal logic consistency: Events must follow cause-and-effect, no contradictions
    - Character goal consistency: Protagonist's actions should align with their life vision and current goals"""


def _build_established_facts_context(
    established_facts: Optional[list],
    language: str,
    max_facts: int = 30,
    max_total_chars: int = 2000,
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
        "commitment": 0,   # 承诺（最高优先级）
        "promise": 0,      # 承诺的别名
        "decision": 1,     # 重要决策
        "state_change": 2, # 状态变化
        "location": 3,     # 地点
        "role": 4,         # 角色
        "situation": 5,    # 事务
        "relationship": 6, # 关系
        "habit": 7,        # 习惯
        "fact": 8,         # 一般事实
    }
    
    def get_priority(fact: dict) -> int:
        category = fact.get("category", "fact").lower()
        # 检查是否包含关键词
        fact_text = fact.get("fact", "").lower()
        if "承诺" in fact_text or "答应" in fact_text or "promise" in fact_text:
            return 0
        if "决定" in fact_text or "选择" in fact_text or "decision" in fact_text or "chose" in fact_text:
            return 1
        return priority_order.get(category, 8)
    
    # 排序事实
    sorted_facts = sorted(established_facts, key=get_priority)
    
    # 类别标签
    cat_labels = {
        "zh": {"location": "地点", "role": "角色", "situation": "事务", 
               "commitment": "承诺", "promise": "承诺", "decision": "决策",
               "state_change": "状态变化", "relationship": "关系", "habit": "习惯", "fact": "事实"},
        "en": {"location": "Location", "role": "Role", "situation": "Situation",
               "commitment": "Commitment", "promise": "Promise", "decision": "Decision",
               "state_change": "State Change", "relationship": "Relationship", "habit": "Habit", "fact": "Fact"}
    }
    
    labels = cat_labels.get(language, cat_labels["en"])
    
    # 构建事实列表，限制数量和总长度
    lines = []
    if language == "zh":
        lines.append("\n【已建立的世界事实 - 必须严格遵守，不得矛盾】")
    else:
        lines.append("\n[Established World Facts - MUST STRICTLY FOLLOW, NO CONTRADICTIONS]")
    
    total_chars = 0
    fact_count = 0
    
    for fact in sorted_facts:
        if fact_count >= max_facts:
            break
        
        category = fact.get("category", "fact")
        cat_label = labels.get(category, labels.get("fact", "Fact"))
        subject = fact.get("subject", "")
        fact_text = fact.get("fact", "")
        source_week = fact.get("source_week", "")
        
        # 构建单条事实
        if language == "zh":
            line = f"- 【{cat_label}】{subject}：{fact_text}"
            if source_week:
                line += f"（第{int(source_week) + 1}周）"  # ★ week 从0开始，显示时+1
        else:
            line = f"- [{cat_label}] {subject}: {fact_text}"
            if source_week:
                line += f" (Week {int(source_week) + 1})"  # ★ week 从0开始，显示时+1
        
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
        lines.append("故事中的人物角色、地理位置、正在处理的事务必须与以上事实一致，不得出现矛盾或随意变动。")
    else:
        lines.append("Character roles, geographic locations, and ongoing affairs MUST be consistent with the above facts. No contradictions or random changes.")
    
    return "\n".join(lines)


def _build_world_model_constraints(
    world_model: Optional[Any],
    language: str
) -> str:
    """
    构建世界模型约束文本段落，用于增强故事一致性。
    调用 WorldModel.build_constraints_text() 生成包含地理位置、职业、承诺、
    因果链和身体状态的综合约束。
    
    Args:
        world_model: WorldModel 实例（可为 None）
        language: 语言代码
    
    Returns:
        世界模型约束字符串
    """
    if world_model is None:
        return ""
    try:
        return world_model.build_constraints_text(language)
    except Exception:
        return ""


def _build_full_character_context(
    character_settings: Optional[Dict[str, Any]],
    language: str
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
        raw_members = family.get('family_members', [])
        member_names = []
        for member in raw_members:
            if isinstance(member, dict):
                name = member.get('name', '')
                role = member.get('role', '')
                if name:
                    member_names.append(f"{name}（{role}）" if zh else f"{name} ({role})")
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
            char_parts.append(f"""Social Relationships:
- Relationship Description: {rel.get('relationships_description', '')}
- **Available People List (includes family and key people, all people in events MUST come from this list)**: {people_str}""")
    
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
        "zh": {"energy": "精力", "mood": "情绪", "knowledge": "学识", "wealth": "财富"},
        "en": {"energy": "Energy", "mood": "Mood", "knowledge": "Knowledge", "wealth": "Wealth"}
    }
    
    for key in ["energy", "mood", "knowledge", "wealth"]:
        val = effects.get(key, 0)
        if val != 0:
            label = labels.get(language, labels["en"]).get(key, key)
            sign = "+" if val > 0 else ""
            parts.append(f"{label}{sign}{val}")
    
    return "、".join(parts) if parts else ("无" if language == "zh" else "None")


# ==================== Common Constraints ====================

def _build_common_story_constraints(language: str) -> str:
    """
    构建故事生成的公共约束，所有故事生成提示词都应包含。
    
    包含：
    1. 第三人称叙事要求
    2. 禁止跳脱叙事（第四面墙）
    3. 禁止编造过往事件
    4. 故事结尾决策点要求
    
    Args:
        language: 语言代码
    
    Returns:
        公共约束字符串
    """
    if language == "zh":
        return """
【核心叙事约束 - 必须严格遵守】
1. **人称要求**：必须使用第三人称叙事（"他/她"而非"我/你"），保持全文人称统一
2. **禁止跳脱叙事**：故事中绝对不能出现任何打破第四面墙的内容，包括但不限于：
   - 提及"游戏""模拟""系统""属性值""精力值""情绪值"等元信息
   - 出现作者旁白、对读者说话、解释创作意图
   - 出现对故事本身的评论或总结性元叙述
   故事应完全沉浸在角色的世界中
3. **禁止编造过往事件**：故事中提到的任何过去发生的事情，必须来自提供的上下文（上周故事、近期总结、年度回顾、剧情线等）。绝对禁止凭空捏造从未发生过的回忆、对话、事件或经历。不确定的过往不要提及
4. **故事结尾要求**：故事结尾必须停在一个具体、明确的决策点！
   - 正确示例：「她说："明天一早跟我走，怎么样？"」「他递来一把钥匙："这是你自己的选择了。"」「父亲沉声道："你自己拿主意吧。"」
   - 错误示例：「他们相视而笑。」（无决策点）、「一切都已经不一样了。」（纯情感结尾）
   - 故事结尾必须是：某人说出一句话需要主角回应、面临两个选择、需要做出承诺、需要表态等
   - **绝对禁止**以纯情感描写或感慨收尾，必须有具体的"下一步怎么办"的悬念
"""
    else:
        return """
[Core Narrative Constraints - MUST STRICTLY FOLLOW]
1. **Perspective**: MUST use third-person narration ("he/she" not "I/you"), maintain consistent perspective throughout
2. **NO FOURTH-WALL BREAKING**: The story must NEVER contain:
   - References to 'game', 'simulation', 'system', 'stats', 'energy points', 'mood value', or any meta-information
   - Author asides, addressing the reader, explaining creative intent
   - Commentary or meta-narrative about the story itself
   The story must remain fully immersed in the character's world
3. **DO NOT FABRICATE PAST EVENTS**: Any past events mentioned in the story MUST come from the provided context (previous story, recent summary, annual review, storylines, etc.). ABSOLUTELY FORBIDDEN to invent memories, conversations, events or experiences that never happened. Do not mention uncertain past events
4. **STORY ENDING REQUIREMENT**: Story MUST end at a concrete, specific decision point!
   - Good: 'She said, "Come with me tomorrow morning, what do you say?"' 'He handed over a key: "This is your choice now."' 'Father said gravely: "Make your own decision."'
   - Bad: 'They looked at each other and smiled.' (no decision point) 'Everything has changed.' (pure emotional ending)
   - Ending MUST be: someone asks a question requiring response, facing two paths, needing to make a promise, needing to take a stance, etc.
   - **ABSOLUTELY FORBIDDEN** to end with pure emotional reflection or sentiment - there must be a concrete "what happens next" tension
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
    
    names_str = "、".join(available_people) if language == "zh" else ", ".join(available_people)
    
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

