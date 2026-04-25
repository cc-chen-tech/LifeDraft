"""Story generation prompts."""

from typing import Any, Dict, Optional

from config.prompts._helpers import (
    _build_available_people_constraint,
    _build_character_habits_context,
    _build_common_story_constraints,
    _build_continuation_mandate,
    _build_critical_summary,
    _build_established_facts_context,
    _build_foreshadowing_context,
    _build_full_character_context,
    _build_logic_constraints,
    _build_new_character_intro_context,
    _build_pending_storylines_context,
    _build_time_context,
    _build_world_model_constraints,
    _collect_available_people,
    _format_people_names,
)
from src.ai.prompt_sanitizer import sanitize_user_choice

# ==================== 自定义选择相关 Prompts ====================


def get_custom_choice_effects_prompt(
    character_settings: dict,
    current_state: dict,
    language: str = "zh",
) -> str:
    """
    生成自定义选择效果的 system prompt。

    Args:
        character_settings: 角色设定
        current_state: 当前玩家状态
        language: 语言

    Returns:
        System prompt 字符串
    """
    import json

    if language == "zh":
        return f"""你是一个人生模拟游戏的叙事引擎。玩家选择了一个自定义的行动，请根据当前情境和玩家的选择，生成合理的属性变化。

角色设定：{json.dumps(character_settings or {}, ensure_ascii=False)}
当前状态：精力={current_state.get('energy', 50)}, 情绪={current_state.get('mood', 50)}, 学识={current_state.get('knowledge', 50)}, 财富={current_state.get('wealth', 1000)}

属性变化范围说明：
- energy(精力): -20到20，负值表示累了，正值表示休息恢复
- mood(情绪): -20到20，负值表示不开心，正值表示开心
- knowledge(学识): -10到15，正值表示学到东西
- wealth(财富): -1000到1000，平时变化应该较小

注意：属性变化应该合理，不要过于极端。大多数情况下变化应该在 -10 到 10 之间。

请仅返回JSON格式的属性变化：
{{
  "energy": 0,
  "mood": 0,
  "knowledge": 0,
  "wealth": 0
}}"""
    else:
        return f"""You are a narrative engine for a life simulation game. The player chose a custom action. Based on the current situation and player's choice, generate reasonable attribute changes.

Character settings: {json.dumps(character_settings or {}, ensure_ascii=False)}
Current state: Energy={current_state.get('energy', 50)}, Mood={current_state.get('mood', 50)}, Knowledge={current_state.get('knowledge', 50)}, Wealth={current_state.get('wealth', 1000)}

Attribute change ranges:
- energy: -20 to 20, negative means tired, positive means rested
- mood: -20 to 20, negative means unhappy, positive means happy
- knowledge: -10 to 15, positive means learned something
- wealth: -1000 to 1000, usually small changes

Note: Changes should be reasonable, not extreme. Most changes should be between -10 and 10.

Return ONLY JSON format:
{{
  "energy": 0,
  "mood": 0,
  "knowledge": 0,
  "wealth": 0
}}"""


def get_custom_choice_result_prompt(
    character_settings: dict,
    current_state: dict,
    language: str = "zh",
) -> str:
    """
    生成自定义选择完整结果（包含故事续写和属性变化）的 system prompt。

    Args:
        character_settings: 角色设定
        current_state: 当前玩家状态
        language: 语言

    Returns:
        System prompt 字符串
    """
    import json

    if language == "zh":
        return f"""你是一个人生模拟游戏的叙事引擎。玩家选择了一个自定义的行动，你需要：
1. 根据当前情境和玩家的选择，生成合理的故事续写（200-400字）
2. 生成合理的属性变化（必须符合逻辑）

角色设定：{json.dumps(character_settings or {}, ensure_ascii=False)}
当前状态：精力={current_state.get('energy', 50)}, 情绪={current_state.get('mood', 50)}, 学识={current_state.get('knowledge', 50)}, 财富={current_state.get('wealth', 1000)}

属性变化范围说明：
- energy(精力): -20到20，负值表示累了，正值表示休息恢复
- mood(情绪): -20到20，负值表示不开心，正值表示开心
- knowledge(学识): -10到15，正值表示学到东西
- wealth(财富): -1000到1000，平时变化应该较小

注意：属性变化应该合理，不要过于极端。大多数情况下变化应该在 -10 到 10 之间。

请返回JSON格式：
{{
  "story_continuation": "故事续写...",
  "effects": {{
    "energy": 0,
    "mood": 0,
    "knowledge": 0,
    "wealth": 0
  }}
}}"""
    else:
        return f"""You are a narrative engine for a life simulation game. The player chose a custom action. You need to:
1. Generate a reasonable story continuation (200-400 words) based on the situation and choice
2. Generate reasonable attribute changes (must be logical)

Character settings: {json.dumps(character_settings or {}, ensure_ascii=False)}
Current state: Energy={current_state.get('energy', 50)}, Mood={current_state.get('mood', 50)}, Knowledge={current_state.get('knowledge', 50)}, Wealth={current_state.get('wealth', 1000)}

Attribute change ranges:
- energy: -20 to 20, negative means tired, positive means rested
- mood: -20 to 20, negative means unhappy, positive means happy
- knowledge: -10 to 15, positive means learned something
- wealth: -1000 to 1000, usually small changes

Note: Changes should be reasonable, not extreme. Most changes should be between -10 and 10.

Return JSON format:
{{
  "story_continuation": "Story continuation...",
  "effects": {{
    "energy": 0,
    "mood": 0,
    "knowledge": 0,
    "wealth": 0
  }}
}}"""


def get_custom_choice_user_prompt(
    event_description: str,
    custom_text: str,
    language: str = "zh",
) -> str:
    """
    生成自定义选择的 user prompt。

    Args:
        event_description: 事件描述
        custom_text: 用户自定义选择文本（已清洗）
        language: 语言

    Returns:
        User prompt 字符串
    """
    if language == "zh":
        return f"""当前情境：
{event_description}

玩家的选择：{custom_text}

请生成合理的结果。"""
    else:
        return f"""Current situation:
{event_description}

Player's choice: {custom_text}

Generate reasonable results."""


# ==================== 事件生成 Prompts ====================


def get_event_generation_prompt(
    player_state: Dict[str, Any],
    language: str = "en",
    current_phase: str = "early_career",
    character_settings: Optional[Dict[str, Any]] = None,
    opening_story: Optional[str] = None,
    last_event_description: Optional[str] = None,
    four_week_summary: Optional[str] = None,
    yearly_summary: Optional[str] = None,
    game_date_info: Optional[Dict[str, Any]] = None,
    pending_storylines: Optional[list] = None,
    established_facts: Optional[list] = None,
    world_model: Optional[Any] = None,
) -> str:
    """
    Generate the prompt for AI event generation.

    Args:
        player_state: Current player state dictionary
        language: Language code ('en' or 'zh')
        current_phase: Current life phase description
        character_settings: Character background settings
        opening_story: The opening story text for narrative continuity
        last_event_description: The last event description for continuity
        four_week_summary: Recent 4-week summary for context
        yearly_summary: Yearly summary (randomly included) for context
        game_date_info: Game-internal date info for time consistency
        pending_storylines: Unresolved storylines for narrative continuity
        world_model: Optional WorldModel instance for consistency constraints

    Returns:
        Formatted prompt string
    """

    if language == "zh":
        return _get_chinese_prompt(
            player_state,
            current_phase,
            character_settings,
            opening_story,
            last_event_description,
            four_week_summary,
            yearly_summary,
            game_date_info,
            pending_storylines,
            established_facts,
            world_model=world_model,
        )
    else:
        return _get_english_prompt(
            player_state,
            current_phase,
            character_settings,
            opening_story,
            last_event_description,
            four_week_summary,
            yearly_summary,
            game_date_info,
            pending_storylines,
            established_facts,
            world_model=world_model,
        )


def _get_english_prompt(
    player_state: Dict[str, Any],
    current_phase: str,
    character_settings: Optional[Dict[str, Any]] = None,
    opening_story: Optional[str] = None,
    last_event_description: Optional[str] = None,
    four_week_summary: Optional[str] = None,
    yearly_summary: Optional[str] = None,
    game_date_info: Optional[Dict[str, Any]] = None,
    pending_storylines: Optional[list] = None,
    established_facts: Optional[list] = None,
    world_model: Optional[Any] = None,
) -> str:
    """English prompt template."""

    age = player_state.get("age", 22)
    energy = player_state.get("energy", 70)
    mood = player_state.get("mood", 60)
    knowledge = player_state.get("knowledge", 50)
    wealth = player_state.get("wealth", 10000)
    relationships = player_state.get("relationships", {})

    rel_str = ", ".join(
        [f"{name}({affinity})" for name, affinity in relationships.items()]
    )
    if not rel_str:
        rel_str = "None"

    phase_descriptions = {
        "early_career": "early career phase (just starting out)",
        "establishing": "establishment phase (building career and relationships)",
        "growth": "growth phase (expanding opportunities)",
        "consolidation": "consolidation phase (stabilizing life)",
    }
    phase_desc = phase_descriptions.get(current_phase, current_phase)

    # Build character context and available people
    character_context, available_people = _build_full_character_context(
        character_settings, "en"
    )
    available_people_str = _build_available_people_constraint(available_people, "en")

    # Build time context
    time_context = _build_time_context(game_date_info, "en")

    # Build pending storylines context
    storylines_context = _build_pending_storylines_context(pending_storylines, "en")

    # Build established facts context
    facts_context = _build_established_facts_context(established_facts, "en")

    # Build world model constraints
    world_model_context = _build_world_model_constraints(world_model, "en", established_facts)

    # Build logic constraints
    logic_constraints = _build_logic_constraints(game_date_info, "en")

    # Build decision history summary
    history_str = "None"
    decision_history = player_state.get("decision_history", [])
    if decision_history:
        recent_decisions = decision_history[-5:]  # Last 5 decisions
        history_parts = []
        for d in recent_decisions:
            history_parts.append(
                f"Week {d.get('week')}: {d.get('choice')} (Event: {d.get('event')[:50]}...)"
            )
        history_str = "\n".join(history_parts)

    # ★ 拐点提取：从较多的历史中提取关键信息，帮助AI识别重复模式
    recent_topics_str = ""
    if len(decision_history) > 5:
        older_decisions = decision_history[-15:-5]  # 6-15个前的决策
        if older_decisions:
            topic_parts = []
            for d in older_decisions:
                event_snippet = d.get('event', '')[:80]
                topic_parts.append(f"W{d.get('week')}: {event_snippet}")
            recent_topics_str = "\n".join(topic_parts)

    # ★ 构建更早历史上下文字符串（避免在f-string中使用反斜杠）
    older_history_section_en = ""
    if recent_topics_str:
        older_history_section_en = (
            "\n\n【Older History Summaries - MUST NOT repeat these plots】\n"
            + recent_topics_str
        )

    prompt = f"""You are a "fate engine" for a life simulation game. Generate a life event that requires the player to make a meaningful choice.

MOST IMPORTANT REQUIREMENTS:
1. **MUST use third-person narration** ("he/she" not "I/you"), keep consistent perspective throughout
2. The story should be 800-1200 words, with dialogue, scene descriptions, and key moments. Write it with depth and engagement.

【Complete Character Settings - MUST STRICTLY FOLLOW】
{character_context if character_context else "Standard modern young adult"}{available_people_str}{time_context}

【近期历史 - 禁止重复相似情节】
{history_str}{older_history_section_en}

【Current Player State】
Age: {age} years old
Energy: {energy}/100
Mood: {mood}/100
Knowledge: {knowledge}/100
Wealth: ${wealth:,}
Key Relationships: {rel_str}{storylines_context}{facts_context}{world_model_context}

【Generation Requirements - MUST STRICTLY FOLLOW】
1. **CRITICAL: Event must be highly relevant to character settings**:
   - **Era Background**: Must strictly match character's era (if ancient, cannot have "company", "client proposal", "mentor" etc. modern concepts)
   - **Occupation/Identity**: Must match character's identity (if student, cannot have workplace events; if spy, cannot have ordinary company work)
   - **Family Background**: If family situation is special, reflect it in the event
   - **Personality Traits**: Event must match character's personality (introverted/extroverted, adventurous/conservative, etc.)
   - **Social Relationships**: **All people in the event MUST and ONLY come from the "Available People List"**, cannot create new people
2. Event must relate to at least two state values (energy, mood, knowledge, wealth, or relationships)
3. Event should fit the "{phase_desc}" life stage and strictly match character settings
4. Provide 2-4 options, each clearly listing effects on [energy, mood, knowledge, wealth]
5. **Story should be 800-1200 words - engaging and immersive**:
   - Write it as a compelling scene with depth
   - Include 3-5 meaningful dialogue exchanges
   - Include essential dialogue, expressions, actions, inner thoughts
   - Use quotation marks for dialogue, e.g.: She said, "Why are you here today?"
   - Focus on the key decision point while building atmosphere
6. Options should present real trade-offs - no option should be clearly superior
7. Relationship effects should be specified as "relationships": {{"name": +/-value}}, **name MUST come from Available People List**
8. **IMPORTANT: Based on the character's personality, abilities, interests, and life vision, mark each option with "likely_choice": true/false to indicate what the character would most likely choose. At least one option should have likely_choice: true.**
9. **ABSOLUTELY FORBIDDEN to generate events that don't match character background**, for example:
    - Ancient character encounters "company", "client proposal", "mentor", "Friday after work" etc. modern concepts
    - Student character encounters "company innovation competition", "client proposal" etc. workplace events
    - Spy character encounters "company innovation competition", "client proposal" etc. ordinary workplace events
    - Event contains people not in the "Available People List"
10. **CRITICAL: Each generated event should be completely different from recent history. Avoid repeating the same plot and options. Be creative and create diverse life scenarios.**
    - **FORBIDDEN opening patterns**: Do not start with "XX sat in the study", "candles flickered", "dawn was breaking" or similar cliché openings that have been used before
    - **FORBIDDEN repeated props**: Do not reuse the same props (e.g. "three documents on the desk", "a letter", "a report") across consecutive events
    - **FORBIDDEN repeated entrances**: Do not have characters always "push open the door" or "walk in quickly" - vary how characters appear
    - **FORBIDDEN atmosphere recycling**: Do not repeat the same weather/atmosphere descriptions (rain, fog, candlelight shadows)
    - **Vary story structure**: Start from different moments (mid-conversation, mid-action, a surprising discovery) rather than always from "morning in a room"
    - **Vary conflict types**: Rotate between interpersonal conflicts, moral dilemmas, unexpected discoveries, external crises, personal growth moments{logic_constraints}
12. **NO FOURTH-WALL BREAKING**: The story must NEVER contain meta-commentary, references to 'game', 'simulation', 'system', 'stats', 'energy points', 'mood value', etc. No author asides, no addressing the reader, no explaining creative intent. The story must remain fully immersed in the character's world.
13. **DO NOT FABRICATE PAST EVENTS**: Any past events referenced in the story MUST come from the context provided above. ABSOLUTELY FORBIDDEN to invent memories, conversations, events or experiences that never happened. Do not mention uncertain past events.

REMINDER: event_description should be 800-1200 words - engaging and immersive. Focus on the key moment with atmosphere and depth.

【Output Format】
You MUST return ONLY valid JSON in this exact format:
{{
  "event_description": "A vivid description (1500-2000 words with extensive dialogue)"
  "options": [
    {{
      "text": "Option A description (max 15 words)",
      "effects": {{
        "energy": -10,
        "mood": 5,
        "knowledge": 0,
        "wealth": 2000,
        "relationships": {{"Alice": -10}}
      }},
      "likely_choice": true
    }},
    {{
      "text": "Option B description (max 15 words)",
      "effects": {{
        "energy": -20,
        "mood": -10,
        "knowledge": 5,
        "wealth": 5000
      }}
    }}
  ]
}}

Now generate a new event based on the player state above. Return ONLY the JSON, no additional text."""

    return prompt


def _get_chinese_prompt(
    player_state: Dict[str, Any],
    current_phase: str,
    character_settings: Optional[Dict[str, Any]] = None,
    opening_story: Optional[str] = None,
    last_event_description: Optional[str] = None,
    four_week_summary: Optional[str] = None,
    yearly_summary: Optional[str] = None,
    game_date_info: Optional[Dict[str, Any]] = None,
    pending_storylines: Optional[list] = None,
    established_facts: Optional[list] = None,
    world_model: Optional[Any] = None,
) -> str:
    """Chinese prompt template."""

    age = player_state.get("age", 22)
    energy = player_state.get("energy", 70)
    mood = player_state.get("mood", 60)
    knowledge = player_state.get("knowledge", 50)
    wealth = player_state.get("wealth", 10000)
    week = player_state.get("week", 0)
    relationships = player_state.get("relationships", {})

    rel_str = "，".join(
        [f"{name}({affinity})" for name, affinity in relationships.items()]
    )
    if not rel_str:
        rel_str = "无"

    phase_descriptions = {
        "early_career": "职场新人阶段",
        "establishing": "立业阶段",
        "growth": "成长期",
        "consolidation": "稳定期",
    }
    phase_desc = phase_descriptions.get(current_phase, current_phase)

    # Build character context and available people
    character_context, available_people = _build_full_character_context(
        character_settings, "zh"
    )
    available_people_str = _build_available_people_constraint(available_people, "zh")

    # Build time context
    time_context = _build_time_context(game_date_info, "zh")

    # Build pending storylines context
    storylines_context = _build_pending_storylines_context(pending_storylines, "zh")

    # Build established facts context
    facts_context = _build_established_facts_context(established_facts, "zh")

    # Build world model constraints
    world_model_context = _build_world_model_constraints(world_model, "zh", established_facts)

    # Build logic constraints
    logic_constraints = _build_logic_constraints(game_date_info, "zh")

    # Build decision history summary
    history_str = "无"
    decision_history = player_state.get("decision_history", [])
    if decision_history:
        recent_decisions = decision_history[-5:]  # 最近5个决策
        history_parts = []
        for d in recent_decisions:
            history_parts.append(
                f"第{d.get('week')}周：{d.get('choice')}（事件：{d.get('event')[:50]}...）"
            )
        history_str = "\n".join(history_parts)

    # ★ 拐点提取：从较多的历史中提取关键信息，帮助AI识别重复模式
    recent_topics_str = ""
    if len(decision_history) > 5:
        older_decisions = decision_history[-15:-5]  # 6-15个前的决策
        if older_decisions:
            topic_parts = []
            for d in older_decisions:
                event_snippet = d.get('event', '')[:80]
                topic_parts.append(f"第{d.get('week')}周: {event_snippet}")
            recent_topics_str = "\n".join(topic_parts)

    # Build story context for narrative continuity
    story_context = ""
    # Use opening story for first few weeks (week 0 or 1), or when no event history yet
    if opening_story and (week <= 1 or not last_event_description):
        # First week: continue from opening story
        story_context = f"""\n【开场故事】
{opening_story}

请基于以上开场故事，续写后续情节。故事要自然接续开场情境，描述大约1周内发生的事情。"""
    elif last_event_description:
        # Subsequent weeks: continue from last event
        story_context = f"""\n【上周故事】
{last_event_description}

请基于上周的故事，续写本周（第{week}周）的新故事。故事要有连续性，描述大约1周内发生的事情。"""

    # Add 4-week summary context if available
    summary_context = ""
    if four_week_summary:
        summary_context += f"""\n【近期总结（最近4周）】
{four_week_summary}
"""

    # Add yearly summary context if provided (randomly selected)
    if yearly_summary:
        summary_context += f"""\n【年度回顾】
{yearly_summary}
"""

    # ★ 构建更早历史上下文字符串（避免在f-string中使用反斜杠）
    older_history_section = ""
    if recent_topics_str:
        older_history_section = (
            "\n\n【更早的历史事件摘要 - 禁止与这些情节雷同】\n"
            + recent_topics_str
        )

    prompt = f"""你是一个人生模拟游戏的“命运引擎”。请根据以下玩家状态和角色设定，以故事续写的方式生成一个需要拉择的生活事件。

最重要的要求：
1. **必须使用第三人称叙事**（"他/她"而非"我/你"），保持全文人称统一
2. 故事应该控制在800-1200字，包含丰富的人物对话、场景描写、内心活动。要生动有深度，聚焦核心决策时刻。{story_context}{summary_context}

【角色完整设定 - 必须严格遵守】
{character_context if character_context else "标准现代青年"}{available_people_str}{time_context}

**人物约束（严格禁止创造新人物）**：
- 所有出现在事件中的人物名字必须且只能来自上方“可用人物列表”
- 绝对禁止凭空创造任何新人物
- 如果需要其他人物，请使用模糊称谓（如“一位同事”“一个朋友”）

【近期历史 - 禁止重复相似情节】
{history_str}{older_history_section}

**★ 反重复红线（违反任何一条即为失败）★**：
- 禁止以"某人坐在书房/值房"、"烛火摇曳"、"晨光熙微"、"天还未亮"等老套开头
- 禁止用"案上攓着三份文书"、"一封密报"等作为**万能开场道具**——核心剧情物件（如角色持有的信物、武器）正常提及不受限，但描写方式必须每次不同
- 禁止人物每次都"推门进来""快步走来"——应变化登场方式
- 禁止回收相同的天气/氛围描写（细雨、晨雾、烛火影子拉得很长、晨光）——每个场景的环境感官必须独特
- **故事结构必须变化**：不要总是"早晨在房间"开始，可以从对话中场、行动中场、意外发现、突发危机等时刻开始
- **冲突类型必须轮换**：人际矛盾、道德困境、意外发现、外部危机、个人成长等不同类型交替使用
- **注意区分**：核心剧情道具/人物/地点的合理复现 ≠ 重复。重复是指用相同的描写句式、相同的场景结构、相同的氛围词来偷懒

【玩家当前状态】
年龄：{age}岁
精力：{energy}/100
情绪：{mood}/100
学识：{knowledge}/100
财富：{wealth:,}元
关键关系：{rel_str}{storylines_context}{facts_context}{world_model_context}

【生成要求 - 必须严格遵守】
1. **CRITICAL：事件必须与角色的基本设定高度相关**：
   - **时代背景**：必须严格符合角色的时代设定（如果是古代，不能出现"公司"、"客户提案"、"导师"等现代概念；如果是未来，要体现未来科技）
   - **职业/身份**：必须符合角色的身份（如果是学生，不能出现职场事件；如果是间谍，不能出现普通公司工作）
   - **家庭背景**：如果家庭情况特殊，要在事件中体现
   - **性格特点**：事件要符合角色的性格（内向/外向、冒险/保守等）
   - **社会关系**：**事件中出现的所有人物必须且只能来自"可用人物列表"**，不能凭空创造新人物
2. 事件必须与至少两项状态值相关（精力、情绪、学识、财富或关系）
3. 事件应贴近"{phase_desc}"人生阶段，并严格符合角色的基本设定
4. 提供2-4个选项，每个选项明确列出对【精力、情绪、学识、财富】的影响值
5. **故事应该800-1200字，生动有深度**：
   - 写成有吸引力的场景片段，有一定深度
   - 包含3-5轮有意义的对话交流
   - 包含必要的对话、表情、动作、内心活动
   - 对话用引号表示，如：她说："你今天怎么来了？"
   - 聚焦核心决策点，同时营造氛围
6. 选项应呈现真实的权衡取舍，不应有明显最优选项
7. 关系影响应指定为"relationships": {{"姓名": +/-数值}}，**姓名必须来自可用人物列表**
8. **重要：根据角色的性格特点、能力、兴趣和人生愿景，在选项中标注"likely_choice": true/false，表示该角色最可能做出的选择。每个事件至少有一个likely_choice为true的选项。**
9. **绝对禁止生成与角色背景不符的事件**，例如：
    - 古代角色遇到"公司"、"客户提案"、"导师"、"周五下班"等现代概念
    - 学生角色遇到"公司内部创新大赛"、"客户提案"等职场事件
    - 间谍角色遇到"公司内部创新大赛"、"客户提案"等普通职场事件
    - 事件中出现不在"可用人物列表"中的人物
10. **CRITICAL：每次生成的事件应该与近期历史完全不同，避免重复相同的情节和选项。发挥创意，创造多样化的生活场景。**
    - **禁止套路开头**：不要再用"某人坐在书房"、"烛火摇曳"、"晨光熙微"、"天还未亮"等已用过的开头
    - **禁止万能道具开场**：不要用"案上攓着三份文书"、"一封密报"等作为通用场景道具——核心剧情物件正常提及不受限，但描写角度必须变化
    - **禁止重复登场**：人物不要每次都"推门进来""快步走来"，应变化登场方式
    - **禁止回收氛围**：不要重复相同的天气/氛围描写（细雨、晨雾、烛火影子拉得很长、晨光）——每个场景的感官细节必须独特
    - **故事结构必须变化**：不要总是"早晨在房间"开始，可从对话中场、行动中场、意外发现、突发危机开始
    - **冲突类型必须轮换**：人际矛盾、道德困境、意外发现、外部危机、个人成长等交替使用
    - **注意区分**：核心道具/人物/地点的剧情性复现是正常的，重复指的是用相同的句式、结构、氛围词偷懒{logic_constraints}
12. **严禁跳脱叙事**：故事中绝对不能出现任何打破第四面墙的内容，包括但不限于：提及"游戏""模拟""系统""属性值""精力值""情绪值"等元信息；出现作者旁白、对读者说话、解释创作意图；出现对故事本身的评论或总结性元叙述。故事应完全沉浸在角色的世界中。
13. **严禁编造过往事件**：故事中提到的任何过去发生的事情，必须来自上面提供的上下文（上周故事、近期总结、年度回顾等）。绝对禁止凭空捏造从未发生过的回忆、对话、事件或经历。不确定的过往不要提及。

再次强调：event_description应该800-1200字，生动有深度。既不过长影响节奏，也不过短缺乏沉浸感！

【输出格式】
你必须仅返回有效的JSON格式，格式如下：
{{
  "event_description": "对情况的生动描述（1500-2000字，包含大量人物对话）"
  "options": [
    {{
      "text": "选项A描述（最多15字）",
      "effects": {{
        "energy": -10,
        "mood": 5,
        "knowledge": 0,
        "wealth": 2000,
        "relationships": {{"李华": -10}}
      }},
      "likely_choice": true
    }},
    {{
      "text": "选项B描述（最多15字）",
      "effects": {{
        "energy": -20,
        "mood": -10,
        "knowledge": 5,
        "wealth": 5000
      }}
    }}
  ]
}}

现在根据上述玩家状态和角色设定生成一个新事件。**必须严格符合角色设定，且与历史情节完全不同。**仅返回JSON，不要添加任何其他文本。"""

    return prompt


def get_result_generation_prompt(
    event_description: str,
    chosen_option: str,
    effects: Dict[str, Any],
    language: str = "en",
    character_settings: Optional[Dict[str, Any]] = None,
    recent_context: str = "",
) -> str:
    """
    Generate prompt for story continuation after player's choice.

    This prompt generates a detailed story continuation (500-800 chars) that:
    - Continues the narrative from the event
    - Shows the immediate consequences of the player's choice
    - Includes character interactions and dialogue where appropriate
    - Maintains consistency with the character settings
    """
    # 清洗用户选择输入，防止 prompt 注入
    sanitized_chosen_option = sanitize_user_choice(chosen_option)

    # Build character context
    char_context = ""
    if character_settings:
        if "identity" in character_settings:
            identity = character_settings["identity"]
            char_context += f"\n主角：{identity.get('name', '未知')}"
        if "occupation" in character_settings:
            occupation = character_settings["occupation"]
            char_context += f"\n职业：{occupation.get('occupation', '未知')}"

    if language == "zh":
        return f"""你是一个沉浸式叙事小说作家。现在请续写以下故事，展示玩家做出选择后发生了什么。

## 角色信息{char_context}

## 当前故事
{event_description}

## 玩家的选择
{sanitized_chosen_option}

## 选择带来的影响
{effects}

## 要求
1. 续写500-800字，详细描述选择后立即发生的事情
2. 包含具体的场景描写、人物反应和丰富的对话（至少3-5轮自然对话）
3. 展现这个选择带来的即时后果和情感变化
4. 保持沉浸式第二人称叙事（"你"的视角）
5. 语言生动流畅，有细节感，对话要体现人物性格
6. 严禁跳脱叙事：不得提及"游戏""模拟""系统""属性值"等元信息，不得出现作者旁白

仅返回续写的故事内容，不要其他说明或标题。"""
    else:
        return f"""You are an immersive narrative writer. Continue the following story, showing what happens after the player's choice.

## Character Info{char_context}

## Current Story
{event_description}

## Player's Choice
{sanitized_chosen_option}

## Effects of Choice
{effects}

## Requirements
1. Write 500-800 words continuing the story
2. Include specific scene descriptions, character reactions, and rich dialogue (at least 3-5 natural exchanges)
3. Show immediate consequences and emotional changes from this choice
4. Maintain immersive second-person narrative ("you" perspective)
5. Vivid and fluid language with good details, dialogue should reflect character personality
6. NO FOURTH-WALL BREAKING: never mention 'game', 'simulation', 'system', 'stats', etc. No author asides

Return only the story continuation, no other explanations or headers."""


def get_options_only_prompt(
    story_description: str,
    player_state: Dict[str, Any],
    character_settings: Optional[Dict[str, Any]] = None,
    language: str = "zh",
) -> str:
    """
    Generate prompt for creating options based on an existing story.
    Used when we already have the story (e.g., opening story) and only need options.

    Args:
        story_description: The existing story text
        player_state: Current player state
        character_settings: Character background settings
        language: Language code

    Returns:
        Formatted prompt string
    """
    relationships = player_state.get("relationships", {})
    collected = _collect_available_people(character_settings)
    available_people = [p.get("name", "") for p in collected if p.get("name")]

    # Add names from current relationships
    for name in relationships.keys():
        if name not in available_people:
            available_people.append(name)

    people_list = "、".join(available_people) if available_people else "无"

    # Build character context for option generator (era, personality, key background)
    char_context_parts = []
    if character_settings:
        if "era" in character_settings:
            era = character_settings["era"]
            era_desc = era.get("era_description", "")
            era_year = era.get("year", "")
            if era_desc or era_year:
                char_context_parts.append(
                    f"时代：{era_year}年，{era_desc}"
                    if language == "zh"
                    else f"Era: {era_year}, {era_desc}"
                )
        if "traits" in character_settings:
            traits = character_settings["traits"]
            traits_desc = traits.get("traits_description", "")
            if traits_desc:
                char_context_parts.append(
                    f"性格：{traits_desc}"
                    if language == "zh"
                    else f"Traits: {traits_desc}"
                )
        if "world" in character_settings:
            world = character_settings["world"]
            world_desc = world.get("world_description", "")
            if world_desc:
                char_context_parts.append(
                    f"世界：{world_desc}"
                    if language == "zh"
                    else f"World: {world_desc}"
                )

    char_context_str = "\n".join(char_context_parts)

    if language == "zh":
        char_section = (
            f"\n\n【角色背景】\n{char_context_str}" if char_context_str else ""
        )
        return f"""你是一个人生模拟游戏的选项生成器。基于以下故事描述，生成2-4个用户可以选择的选项。

【故事描述】
{story_description}

【可用人物列表】
{people_list}{char_section}

【核心要求 - 必须严格遵守】

**最重要：选项必须精确回应故事结尾的决策点！**

请仔细阅读上面的故事，特别关注故事**最后几段**面临的具体情境（某人提出邀请/面临冲突/需要做选择），然后生成2-4个**直接回应该情境**的选项。

**逻辑一致性要求：**
- 选项必须是主角在故事结尾的**具体情境下**可以采取的行动
- 选项必须符合角色的身份、时代背景和性格特点
- 每个选项都应该是对故事结尾**同一个决策点**的不同回应，而非各自描述不同的事情

**绝对禁止：**
- 不要生成"休息"、"学习"、"工作"等与故事无关的通用选项
- 不要生成"继续前进"、"思考一下"、"保持现状"等模糊的万能选项
- 不要生成脱离故事情境的独立行动

【其他要求】
3. 每个选项明确列出对【精力(energy)、情绪(mood)、学识(knowledge)、财富(wealth)】的影响值
4. 选项应呈现真实的权衡取舍，不应有明显最优选项
5. **关系影响必须指定为"relationships": {{"姓名": +/-数值}}，姓名必须严格来自可用人物列表，禁止使用列表中不存在的名字！**
6. 标注"likely_choice": true/false表示角色最可能做出的选择

【输出格式】
仅返回有效的JSON格式：
{{
  "options": [
    {{
      "text": "选项A描述（最多15字）",
      "effects": {{
        "energy": -10,
        "mood": 5,
        "knowledge": 0,
        "wealth": 0,
        "relationships": {{}}
      }},
      "likely_choice": true
    }},
    {{
      "text": "选项B描述（最多15字）",
      "effects": {{
        "energy": -5,
        "mood": -5,
        "knowledge": 5,
        "wealth": 0
      }},
      "likely_choice": false
    }}
  ]
}}

仅返回JSON，不要其他内容。"""
    else:
        char_section_en = (
            f"\n\n[Character Background]\n{char_context_str}"
            if char_context_str
            else ""
        )
        return f"""You are an options generator for a life simulation game. Based on the following story description, generate 2-4 options for the user to choose from.

[Story Description]
{story_description}

[Available People]
{people_list}{char_section_en}

[Requirements]
1. **Options MUST precisely respond to the decision point at the END of the story**:
   - Read the story carefully, focus on the **last few paragraphs** to identify the specific situation (invitation/conflict/dilemma)
   - Options must be actions the protagonist can take in that **specific situation**
   - Options must fit the character's identity, era, and personality
   - All options should be different responses to the **same decision point**, not describing unrelated things
2. **FORBIDDEN to generate generic options unrelated to the story**:
   - "Rest", "Study", "Work", "Exercise" etc.
   - "Continue forward", "Think about it", "Keep status quo" etc.
   - Any action detached from the story context
3. Each option clearly lists effects on [energy, mood, knowledge, wealth]
4. Options should present real trade-offs - no option should be clearly superior
5. Relationship effects should be specified as "relationships": {{"name": +/-value}}, name must come from Available People List
6. Mark "likely_choice": true/false to indicate what the character would most likely choose

[Output Format]
Return ONLY valid JSON:
{{
  "options": [
    {{
      "text": "Option A description (max 15 words)",
      "effects": {{
        "energy": -10,
        "mood": 5,
        "knowledge": 0,
        "wealth": 0,
        "relationships": {{}}
      }},
      "likely_choice": true
    }},
    {{
      "text": "Option B description (max 15 words)",
      "effects": {{
        "energy": -5,
        "mood": -5,
        "knowledge": 5,
        "wealth": 0
      }},
      "likely_choice": false
    }}
  ]
}}

Return ONLY the JSON, no additional text."""


def get_story_only_prompt(
    player_state: Dict[str, Any],
    language: str = "zh",
    current_phase: str = "early_career",
    character_settings: Optional[Dict[str, Any]] = None,
    opening_story: Optional[str] = None,
    last_event_description: Optional[str] = None,
    four_week_summary: Optional[str] = None,
    yearly_summary: Optional[str] = None,
    game_date_info: Optional[Dict[str, Any]] = None,
    pending_storylines: Optional[list] = None,
    established_facts: Optional[list] = None,
    last_event_concluded: bool = True,
    last_round_full_story: str = "",
    activated_foreshadowing: Optional[Dict[str, Any]] = None,
    character_habits: Optional[list] = None,
    world_model: Optional[Any] = None,
    vector_context: str = "",  # ★ 向量检索上下文
    overused_phrases: str = "",  # ★ 动态禁用短语列表
    style_constraints: str = "",  # ★ 风格引擎约束
    arc_hint: str = "",  # ★ 人物弧光约束
    conflict_directive: str = "",  # ★ 冲突升级指令
    world_event_context: str = "",  # ★ 世界呼吸背景事件
    fate_echo_hint: str = "",  # ★ 宿命回响提示
    preference_hint: str = "",  # ★ 偏好适配提示
    foreshadowing_technique_hint: str = "",  # ★ 伏笔技法提示
    chapter_opening: str = "",  # ★ 章节开头约束
    chapter_ending: str = "",  # ★ 章节结尾约束
    three_act_hint: str = "",  # ★ 三幕结构提示
    pacing_intervention: str = "",  # ★ 节奏干预指令
    quality_level: str = "expert",  # ★ 叙事质量级别
    player_name: Optional[str] = None,  # ★ 主角名称
) -> str:
    """
    Generate prompt for story-only generation (no JSON, pure narrative).
    This produces longer, more detailed stories since there's no JSON format constraint.

    Args:
        player_state: Current player state dictionary
        language: Language code ('en' or 'zh')
        current_phase: Current life phase description
        character_settings: Character background settings
        opening_story: The opening story text for narrative continuity
        last_event_description: The last event description for continuity
        four_week_summary: Recent 4-week summary for context
        yearly_summary: Yearly summary (randomly included) for context

    Returns:
        Formatted prompt string for pure story generation
    """

    age = player_state.get("age", 22)
    week = player_state.get("week", 0) + 1  # ★ week 从0开始，显示时+1，与前端一致
    energy = player_state.get("energy", 70)
    mood = player_state.get("mood", 60)
    knowledge = player_state.get("knowledge", 50)
    wealth = player_state.get("wealth", 10000)
    relationships = player_state.get("relationships", {})

    rel_str = (
        "、".join([f"{name}({affinity})" for name, affinity in relationships.items()])
        if relationships
        else "无"
    )

    # Build character context (simplified for story-only prompt)
    available_people = _collect_available_people(character_settings)
    character_context = ""

    if character_settings:
        char_parts = []

        if "era" in character_settings:
            era = character_settings["era"]
            char_parts.append(
                f"""时代背景：{era.get('year', '未知')}年，{era.get('era_description', '')}"""
            )

        if "age" in character_settings:
            age_info = character_settings["age"]
            char_parts.append(f"""起始年龄：{age_info.get('age', '未知')}岁""")

        if "gender" in character_settings:
            gender_info = character_settings["gender"]
            char_parts.append(f"""性别：{gender_info.get('gender', '未知')}""")

        if "world" in character_settings:
            world = character_settings["world"]
            char_parts.append(f"""世界设定：{world.get('world_description', '')}""")

        if "family" in character_settings:
            family = character_settings["family"]
            char_parts.append(f"""家庭背景：{family.get('family_description', '')}""")

        if available_people:
            people_str = _format_people_names(available_people, "zh")
            char_parts.append(f"""关键人物：{people_str}""")

        if "traits" in character_settings:
            traits = character_settings["traits"]
            char_parts.append(f"""个人特点：{traits.get('traits_description', '')}""")

        character_context = "\n".join(char_parts)

    # Build player name instruction
    name_instruction = ""
    if player_name:
        if language == "zh":
            name_instruction = f"""\n【主角名称】\n主角名称是：{player_name}。请始终使用这个名字称呼主角，禁止编造其他名字、添加后缀或改变主角名称。"""
        else:
            name_instruction = f"""\n[Protagonist Name]\nThe protagonist's name is: {player_name}. Always use this exact name. Do not invent alternative names, add suffixes, or change the protagonist's name."""

    # Build story context
    story_context = ""
    if opening_story and (week <= 1 or not last_event_description):
        story_context = f"""\n【开场故事】
{opening_story}

请基于以上开场故事，续写后续情节。"""
    elif last_event_description:
        story_context = f"""\n【上周故事】
{last_event_description}

请基于上周的故事，续写本周（第{week}周）的新故事。"""

    # Build summary context
    summary_context = ""
    if four_week_summary:
        summary_context += f"""\n【近期总结（4周）】
{four_week_summary}"""
    if yearly_summary:
        summary_context += f"""\n【年度回顾】
{yearly_summary}"""

    # Build available people constraint string
    available_people_str = _build_available_people_constraint(available_people, "zh")

    # Build time context
    time_context = _build_time_context(game_date_info, language)

    # Build pending storylines context
    storylines_context = _build_pending_storylines_context(pending_storylines, language)

    # Build established facts context
    facts_context = _build_established_facts_context(established_facts, language)

    # Build world model constraints
    world_model_context = _build_world_model_constraints(world_model, language, established_facts)

    # Build continuation mandate (if previous event not concluded)
    continuation_mandate = _build_continuation_mandate(
        last_event_concluded, last_round_full_story, language
    )

    # Build foreshadowing echo context (if a seed was activated)
    foreshadowing_context = _build_foreshadowing_context(
        activated_foreshadowing, language
    )

    # Build character habits context
    habits_context = _build_character_habits_context(character_habits, language)

    # ★ 向量检索上下文（如果有）
    vector_context_section = vector_context + "\n" if vector_context else ""

    # ★ 构建红线约束摘要（开头+结尾强化）
    critical_summary = _build_critical_summary(
        pending_storylines=pending_storylines,
        established_facts=established_facts,
        world_model=world_model,
        language=language,
    )

    # ★ 构建叙事引擎增强约束块
    narrative_enhancements_zh = ""
    narrative_enhancements_en = ""
    _enhancement_parts_zh = []
    _enhancement_parts_en = []
    # ★ 节奏干预指令（最高优先级，MUST 级别）
    if pacing_intervention:
        _enhancement_parts_zh.append(f"\n[MUST] 【节奏干预】{pacing_intervention}")
        _enhancement_parts_en.append(f"\n[MUST] [Pacing Intervention] {pacing_intervention}")
    if style_constraints:
        _enhancement_parts_zh.append(f"\n【风格约束】\n{style_constraints}")
        _enhancement_parts_en.append(f"\n[Style Constraints]\n{style_constraints}")
    if arc_hint:
        _enhancement_parts_zh.append(f"\n{arc_hint}")
        _enhancement_parts_en.append(f"\n{arc_hint}")
    if conflict_directive:
        _enhancement_parts_zh.append(f"\n【冲突指令】{conflict_directive}")
        _enhancement_parts_en.append(f"\n[Conflict Directive] {conflict_directive}")
    if world_event_context:
        _enhancement_parts_zh.append(f"\n【世界背景事件】\n{world_event_context}")
        _enhancement_parts_en.append(f"\n[World Background Events]\n{world_event_context}")
    if fate_echo_hint:
        _enhancement_parts_zh.append(f"\n【宿命回响】{fate_echo_hint}")
        _enhancement_parts_en.append(f"\n[Fate Echo] {fate_echo_hint}")
    if preference_hint:
        _enhancement_parts_zh.append(f"\n[SHOULD] 【偏好适配】{preference_hint}")
        _enhancement_parts_en.append(f"\n[SHOULD] [Preference Hint] {preference_hint}")
    if foreshadowing_technique_hint:
        _enhancement_parts_zh.append(f"\n【伏笔技法】{foreshadowing_technique_hint}")
        _enhancement_parts_en.append(f"\n[Foreshadowing Technique] {foreshadowing_technique_hint}")
    # ★ 章节结构约束（中观层）
    if three_act_hint:
        _enhancement_parts_zh.append(f"\n[SHOULD] 【三幕结构】{three_act_hint}")
        _enhancement_parts_en.append(f"\n[SHOULD] [Three-Act Structure] {three_act_hint}")
    if chapter_opening:
        _enhancement_parts_zh.append(f"\n[SHOULD] 【章节开头约束】{chapter_opening}")
        _enhancement_parts_en.append(f"\n[SHOULD] [Chapter Opening] {chapter_opening}")
    if chapter_ending:
        _enhancement_parts_zh.append(f"\n[SHOULD] 【章节结尾约束】{chapter_ending}")
        _enhancement_parts_en.append(f"\n[SHOULD] [Chapter Ending] {chapter_ending}")
    if _enhancement_parts_zh:
        narrative_enhancements_zh = "\n".join(_enhancement_parts_zh)
    if _enhancement_parts_en:
        narrative_enhancements_en = "\n".join(_enhancement_parts_en)

    # ★ 构建公共叙事约束（根据质量级别）
    common_constraints = _build_common_story_constraints(language, quality_level)

    if language == "zh":
        # === 开头：红线约束摘要 ===
        critical_open = f"\n{critical_summary}\n" if critical_summary else ""
        # === 结尾：红线约束摘要重复 ===
        critical_close = f"\n{critical_summary}\n" if critical_summary else ""

        prompt = f"""你是一位才华横溢的小说家。请根据以下角色设定和玩家状态，写一段生动的故事（描述这一周发生的事情）。
{critical_open}
{story_context}{summary_context}

【角色设定】
{character_context if character_context else "标准现代青年"}{name_instruction}{available_people_str}{time_context}

【玩家当前状态】
年龄：{age}岁 | 第{week}周
精力：{energy}/100 | 情绪：{mood}/100 | 学识：{knowledge}/100
财富：{wealth:,}元 | 关系：{rel_str}

[MUST] 强制约束（违反即重新生成）：{storylines_context}{facts_context}{world_model_context}{continuation_mandate}

[SHOULD] 建议约束：{foreshadowing_context}{habits_context}
{narrative_enhancements_zh}
[REF] 参考信息：
{vector_context_section}

{common_constraints}

【写作要求】
1. **故事应该800-1200字**，包含3-5轮对话交流，对话用""包裹
2. 包含环境描写、表情动作、内心独白等细节，事件必须严格符合角色设定
3. 故事中出现的人物必须来自可用人物列表，标点禁止中英混用
4. **场景连贯性**：检查上一轮结束地点，禁止无故跳跃场景。开头前3句明确当前地点
5. **只返回故事文本**，不要JSON、选项列表或其他标记
6. **反重复红线**：禁止套路开头/万能道具/重复登场方式/回收氛围。结构和冲突类型必须变化
{overused_phrases}
{critical_close}
现在请开始写故事："""
    else:
        # === EN: 开头/结尾红线约束摘要 ===
        critical_open_en = f"\n{critical_summary}\n" if critical_summary else ""
        critical_close_en = f"\n{critical_summary}\n" if critical_summary else ""

        prompt = f"""You are a talented novelist. Based on the following character settings and player state, write a vivid story (describing what happens this week).
{critical_open_en}
{story_context}{summary_context}

[Character Settings]
{character_context if character_context else "Standard modern young adult"}{name_instruction}{available_people_str}{time_context}

[Current Player State]
Age: {age} | Week {week}
Energy: {energy}/100 | Mood: {mood}/100 | Knowledge: {knowledge}/100
Wealth: ${wealth:,} | Relationships: {rel_str}

[MUST] Mandatory constraints (violation = regeneration):{storylines_context}{facts_context}{world_model_context}{continuation_mandate}

[SHOULD] Advisory constraints:{foreshadowing_context}{habits_context}
{narrative_enhancements_en}
[REF] Reference information:
{vector_context_section}

{common_constraints}

[Writing Requirements]
1. **Story should be 800-1200 words**, include 3-5 dialogue exchanges using quotation marks
2. Include environment descriptions, expressions, actions, inner thoughts; must match character settings
3. Characters must come from available people list
4. **Scene continuity**: Check previous round ending location. No unexplained scene jumps. First 3 sentences must establish location
5. **Return ONLY story text**, no JSON, no option lists
6. **Anti-repetition red lines**: No cliché openings/recycled props/repeated entrances/recycled atmosphere. Vary structure and conflict types

{critical_close_en}
Now begin writing the story:"""

    return prompt


def get_relationship_event_context(events: list, era: str, language: str) -> str:
    """
    生成关系事件上下文供AI使用

    Args:
        events: 触发的关系事件列表
        era: 时代背景
        language: 语言

    Returns:
        关系事件上下文字符串
    """
    if not events:
        return ""

    if language == "zh":
        lines = ["\n【本轮触发的重要关系事件 - 必须自然融入故事】"]
        for event in events:
            lines.append(f"- **{event['character_name']}**: {event['era_name']}")
            lines.append(f"  {event['description']}")
        lines.append("")
        lines.append(
            "请将以上关系事件自然地融入本轮故事中，使其感觉是故事发展的自然结果。"
        )
        lines.append("事件表达方式应符合时代背景，避免突兀。")
    else:
        lines = ["\n[IMPORTANT RELATIONSHIP EVENT - MUST INTEGRATE INTO STORY]"]
        for event in events:
            lines.append(f"- **{event['character_name']}**: {event['era_name']}")
            lines.append(f"  {event['description']}")
        lines.append("")
        lines.append(
            "Naturally integrate the above relationship events into this round's story."
        )
        lines.append("Events should feel like natural story developments, not forced.")

    return "\n".join(lines)


def get_round_event_prompt(
    player_state: Dict[str, Any],
    language: str,
    round_number: int,
    round_context: str,
    character_settings: Optional[Dict[str, Any]] = None,
    relationship_events: Optional[list] = None,
    historical_weekly_summary: Optional[str] = None,
    historical_yearly_summary: Optional[str] = None,
    game_date_info: Optional[Dict[str, Any]] = None,
    pending_storylines: Optional[list] = None,
    established_facts: Optional[list] = None,
    last_event_concluded: bool = True,
    last_round_full_story: str = "",
    activated_foreshadowing: Optional[Dict[str, Any]] = None,
    character_habits: Optional[list] = None,
    world_model: Optional[Any] = None,
    new_character: Optional[Dict[str, Any]] = None,
    vector_context: str = "",  # ★ 向量检索上下文
    overused_phrases: str = "",  # ★ 动态禁用短语列表
    style_constraints: str = "",  # ★ 风格引擎约束
    arc_hint: str = "",  # ★ 人物弧光约束
    conflict_directive: str = "",  # ★ 冲突升级指令
    world_event_context: str = "",  # ★ 世界呼吸背景事件
    fate_echo_hint: str = "",  # ★ 宿命回响提示
    preference_hint: str = "",  # ★ 偏好适配提示
    foreshadowing_technique_hint: str = "",  # ★ 伏笔技法提示
    chapter_opening: str = "",  # ★ 章节开头约束
    chapter_ending: str = "",  # ★ 章节结尾约束
    three_act_hint: str = "",  # ★ 三幕结构提示
    pacing_intervention: str = "",  # ★ 节奏干预指令
    quality_level: str = "expert",  # ★ 叙事质量级别
    player_name: Optional[str] = None,  # ★ 主角名称
) -> str:
    """
    Generate prompt for a single round's story within a week.

    Args:
        player_state: Current player state dictionary
        language: Language code ('zh' or 'en')
        round_number: Round number within week (0=周一, 1=周中, 2=周末)
        round_context: Previous rounds' summaries and choices
        character_settings: Character background settings
        relationship_events: 触发的关系事件列表
        historical_weekly_summary: 随机选中的历史周总结
        historical_yearly_summary: 随机选中的历史年度总结

    Returns:
        Formatted prompt string for story generation
    """
    age = player_state.get("age", 22)
    week = player_state.get("week", 0) + 1  # ★ week 从0开始，显示时+1，与前端一致
    energy = player_state.get("energy", 70)
    mood = player_state.get("mood", 60)
    knowledge = player_state.get("knowledge", 50)
    wealth = player_state.get("wealth", 10000)
    relationships = player_state.get("relationships", {})

    rel_str = (
        "、".join([f"{name}({affinity})" for name, affinity in relationships.items()])
        if relationships
        else "无"
    )

    # Build character context
    available_people = _collect_available_people(character_settings)
    character_context = ""
    available_people_str = ""

    if character_settings:
        char_parts = []

        if "era" in character_settings:
            era = character_settings["era"]
            char_parts.append(
                f"""时代背景：{era.get('year', '')}年，{era.get('era_description', '')}"""
            )

        if "world" in character_settings:
            world = character_settings["world"]
            char_parts.append(f"""世界设定：{world.get('world_description', '')}""")

        if "family" in character_settings:
            family = character_settings["family"]
            char_parts.append(f"""家庭背景：{family.get('family_description', '')}""")

        if "traits" in character_settings:
            traits = character_settings["traits"]
            char_parts.append(f"""个人特质：{traits.get('traits_description', '')}""")

        # 生成可用人物列表字符串（包含所有人物）
        # 如果有新人物，特别标注其首次登场
        if available_people:
            people_list = _format_people_names(available_people, "zh")

            # 如果有新人物，在人物列表中特别标注
            new_char_name = new_character.get("name", "") if new_character else ""
            if new_char_name:
                # 特别标注新人物
                available_people_str = f"""\n**可用人物列表（仅限使用）**：{people_list}

注意：**{new_char_name}** 是本轮**首次登场**的新人物，请确保写一个自然的「相遇/相识」场景！
禁止创造不在上述列表中的人物名字！如需新人物请用「陌生人」「路人」等通用称谓。"""
            else:
                available_people_str = f"""\n**可用人物列表（仅限使用）**：{people_list}
禁止创造不在上述列表中的人物名字！如需新人物请用「陌生人」「路人」等通用称谓。"""

        if char_parts:
            character_context = "\n".join(char_parts)

    # Build player name instruction
    name_instruction = ""
    if player_name:
        if language == "zh":
            name_instruction = f"""\n【主角名称】\n主角名称是：{player_name}。请始终使用这个名字称呼主角，禁止编造其他名字、添加后缀或改变主角名称。"""
        else:
            name_instruction = f"""\n[Protagonist Name]\nThe protagonist's name is: {player_name}. Always use this exact name. Do not invent alternative names, add suffixes, or change the protagonist's name."""

    # Round names
    round_names_zh = ["周一", "周中", "周末"]
    round_names_en = ["Monday", "Midweek", "Weekend"]

    round_name = (
        round_names_zh[round_number] if round_number < 3 else f"第{round_number+1}轮"
    )
    round_name_en = (
        round_names_en[round_number] if round_number < 3 else f"Round {round_number+1}"
    )

    # ★ 构建公共叙事约束（根据质量级别）
    common_constraints = _build_common_story_constraints(language, quality_level)

    if language == "zh":
        # Build previous rounds context
        context_section = ""
        if round_context:
            context_section = f"""\n
【本周前几轮经历】
{round_context}

请基于上述经历继续发展故事，保持连贯性。"""

        # ★ 构建叙事引擎增强约束块（round）
        round_enhancements_zh = ""
        _re_parts_zh = []
        # ★ 节奏干预指令（最高优先级，MUST 级别）
        if pacing_intervention:
            _re_parts_zh.append(f"\n[MUST] 【节奏干预】{pacing_intervention}")
        if style_constraints:
            _re_parts_zh.append(f"\n【风格约束】\n{style_constraints}")
        if arc_hint:
            _re_parts_zh.append(f"\n{arc_hint}")
        if conflict_directive:
            _re_parts_zh.append(f"\n【冲突指令】{conflict_directive}")
        if world_event_context:
            _re_parts_zh.append(f"\n【世界背景事件】\n{world_event_context}")
        if fate_echo_hint:
            _re_parts_zh.append(f"\n【宿命回响】{fate_echo_hint}")
        if preference_hint:
            _re_parts_zh.append(f"\n[SHOULD] 【偏好适配】{preference_hint}")
        if foreshadowing_technique_hint:
            _re_parts_zh.append(f"\n【伏笔技法】{foreshadowing_technique_hint}")
        # ★ 章节结构约束（中观层）
        if three_act_hint:
            _re_parts_zh.append(f"\n[SHOULD] 【三幕结构】{three_act_hint}")
        if chapter_opening:
            _re_parts_zh.append(f"\n[SHOULD] 【章节开头约束】{chapter_opening}")
        if chapter_ending:
            _re_parts_zh.append(f"\n[SHOULD] 【章节结尾约束】{chapter_ending}")
        if _re_parts_zh:
            round_enhancements_zh = "\n".join(_re_parts_zh)

        # Build relationship events context
        rel_events_context = ""
        if relationship_events:
            era = (
                character_settings.get("era", {}).get("era_description", "")
                if character_settings
                else ""
            )
            rel_events_context = get_relationship_event_context(
                relationship_events, era, language
            )

        # Build historical memory context (as flashback/reminiscence)
        memory_context = ""
        if historical_weekly_summary or historical_yearly_summary:
            memory_parts = ["\n【历史回忆 - 可自然地融入故事作为回忆片段】"]
            if historical_yearly_summary:
                memory_parts.append(f"「往年回忆」{historical_yearly_summary}")
            if historical_weekly_summary:
                memory_parts.append(f"「近期回忆」{historical_weekly_summary}")
            memory_parts.append(
                "提示：当人物回忆过去或谈论往事时，可以自然引用以上内容。"
            )
            memory_context = "\n".join(memory_parts)

        # Build time and storyline contexts
        time_context = _build_time_context(game_date_info, language)
        storylines_context = _build_pending_storylines_context(
            pending_storylines, language
        )
        facts_context = _build_established_facts_context(established_facts, language)

        # Build world model constraints
        world_model_context = _build_world_model_constraints(world_model, language, established_facts)

        # Build continuation mandate (if previous event not concluded)
        continuation_mandate = _build_continuation_mandate(
            last_event_concluded, last_round_full_story, language
        )

        # Build foreshadowing echo context
        foreshadowing_context = _build_foreshadowing_context(
            activated_foreshadowing, language
        )

        # Build character habits context
        habits_context = _build_character_habits_context(character_habits, language)

        # Build new character introduction context
        new_char_context = _build_new_character_intro_context(new_character, language)

        # ★ 向量检索上下文
        vector_context_section = ""
        if vector_context:
            vector_context_section = f"""
[REF] 📚 相关历史片段（回忆参考）
{vector_context}
使用提示：可作为角色回忆、对话引用或背景参考。自然融入，不要重复叙述。
"""

        # ★ 构建红线约束摘要
        critical_summary_zh = _build_critical_summary(
            pending_storylines=pending_storylines,
            established_facts=established_facts,
            world_model=world_model,
            language=language,
        )
        critical_open_zh = f"\n{critical_summary_zh}\n" if critical_summary_zh else ""
        critical_close_zh = f"\n{critical_summary_zh}\n" if critical_summary_zh else ""

        prompt = f"""你是一位才华横溢的小说家。请为第{week}周的{round_name}写一段生动的故事。
{critical_open_zh}

【角色设定】
{character_context if character_context else "标准现代青年"}{name_instruction}{available_people_str}{time_context}

【当前状态】
年龄：{age}岁 | 第{week}周 - {round_name}
精力：{energy}/100 | 情绪：{mood}/100 | 学识：{knowledge}/100
财富：{wealth:,}元 | 关系：{rel_str}{context_section}{rel_events_context}{memory_context}

[MUST] 强制约束（违反即重新生成）：{world_model_context}{storylines_context}{facts_context}{continuation_mandate}{new_char_context}

[MUST] 写作前红线检查（违反即重新生成）：
1. 人物位置：检查世界模型约束中角色位置，禁止无故跳跃。场景转换必须交代移动过程
2. 承诺约束：检查未兑现的承诺，不得遗忘或违反
3. 过期剧情线：必须推进至少一条 overdue 剧情线（如有）

[SHOULD] 建议约束：{foreshadowing_context}{habits_context}
{round_enhancements_zh}
[REF] 参考信息：
{vector_context_section}

{common_constraints}

【写作要求】
1. **故事应该1500-2000字**，包含4-6轮对话交流，对话用""包裹
2. 包含环境描写、表情动作、内心独白等细节，事件必须符合角色设定
3. 人物必须来自可用人物列表，标点禁止中英混用
4. **场景连贯性**：开头前3句明确当前地点，禁止无故跳跃场景
5. **只返回故事文本**，不要JSON、选项列表
6. **反重复红线**：禁止套路开头/万能道具/重复登场方式/回收氛围。结构和冲突类型必须变化
{overused_phrases}
{critical_close_zh}
现在请开始写{round_name}的故事："""
    else:
        context_section = ""
        if round_context:
            context_section = f"""\n
[Previous Rounds This Week]
{round_context}

Continue the story based on the above, maintaining continuity."""

        # ★ 构建叙事引擎增强约束块（round EN）
        round_enhancements_en = ""
        _re_parts_en = []
        # ★ 节奏干预指令（最高优先级，MUST 级别）
        if pacing_intervention:
            _re_parts_en.append(f"\n[MUST] [Pacing Intervention] {pacing_intervention}")
        if style_constraints:
            _re_parts_en.append(f"\n[Style Constraints]\n{style_constraints}")
        if arc_hint:
            _re_parts_en.append(f"\n{arc_hint}")
        if conflict_directive:
            _re_parts_en.append(f"\n[Conflict Directive] {conflict_directive}")
        if world_event_context:
            _re_parts_en.append(f"\n[World Background Events]\n{world_event_context}")
        if fate_echo_hint:
            _re_parts_en.append(f"\n[Fate Echo] {fate_echo_hint}")
        if preference_hint:
            _re_parts_en.append(f"\n[SHOULD] [Preference Hint] {preference_hint}")
        if foreshadowing_technique_hint:
            _re_parts_en.append(f"\n[Foreshadowing Technique] {foreshadowing_technique_hint}")
        # ★ 章节结构约束（中观层）
        if three_act_hint:
            _re_parts_en.append(f"\n[SHOULD] [Three-Act Structure] {three_act_hint}")
        if chapter_opening:
            _re_parts_en.append(f"\n[SHOULD] [Chapter Opening] {chapter_opening}")
        if chapter_ending:
            _re_parts_en.append(f"\n[SHOULD] [Chapter Ending] {chapter_ending}")
        if _re_parts_en:
            round_enhancements_en = "\n".join(_re_parts_en)

        # Build relationship events context
        rel_events_context = ""
        if relationship_events:
            era = (
                character_settings.get("era", {}).get("era_description", "")
                if character_settings
                else ""
            )
            rel_events_context = get_relationship_event_context(
                relationship_events, era, language
            )

        # Build historical memory context (as flashback/reminiscence)
        memory_context = ""
        if historical_weekly_summary or historical_yearly_summary:
            memory_parts = [
                "\n[Historical Memory - Can be naturally woven into the story as flashbacks]"
            ]
            if historical_yearly_summary:
                memory_parts.append(f"[Past Year Memory] {historical_yearly_summary}")
            if historical_weekly_summary:
                memory_parts.append(f"[Recent Memory] {historical_weekly_summary}")
            memory_parts.append(
                "Hint: When characters recall the past or discuss old times, you can naturally reference the above content."
            )
            memory_context = "\n".join(memory_parts)

        # Build time and storyline contexts
        time_context = _build_time_context(game_date_info, language)
        storylines_context = _build_pending_storylines_context(
            pending_storylines, language
        )
        facts_context = _build_established_facts_context(established_facts, language)

        # Build world model constraints
        world_model_context_en = _build_world_model_constraints(world_model, language, established_facts)

        # Build continuation mandate (if previous event not concluded)
        continuation_mandate_en = _build_continuation_mandate(
            last_event_concluded, last_round_full_story, language
        )

        # Build foreshadowing echo context
        foreshadowing_context_en = _build_foreshadowing_context(
            activated_foreshadowing, language
        )

        # Build character habits context
        habits_context_en = _build_character_habits_context(character_habits, language)

        # Build new character introduction context
        new_char_context_en = _build_new_character_intro_context(
            new_character, language
        )

        # ★ 向量检索上下文
        vector_context_section_en = ""
        if vector_context:
            vector_context_section_en = f"""
[REF] Relevant Historical Fragments (Reference)
{vector_context}
Usage tip: Use as character memories, dialogue references, or background context. Weave naturally, don't repeat.
"""

        # ★ 构建红线约束摘要
        critical_summary_en = _build_critical_summary(
            pending_storylines=pending_storylines,
            established_facts=established_facts,
            world_model=world_model,
            language=language,
        )
        critical_open_en = f"\n{critical_summary_en}\n" if critical_summary_en else ""
        critical_close_en = f"\n{critical_summary_en}\n" if critical_summary_en else ""

        prompt = f"""You are a talented novelist. Write a vivid story for {round_name_en} of Week {week}.
{critical_open_en}

[Character Settings]
{character_context if character_context else "Standard modern young adult"}{name_instruction}{available_people_str}{time_context}

[Current State]
Age: {age} | Week {week} - {round_name_en}
Energy: {energy}/100 | Mood: {mood}/100 | Knowledge: {knowledge}/100
Wealth: ${wealth:,} | Relationships: {rel_str}{context_section}{rel_events_context}{memory_context}

[MUST] Mandatory constraints (violation = regeneration):{world_model_context_en}{storylines_context}{facts_context}{continuation_mandate_en}{new_char_context_en}

[MUST] Pre-writing red line checks (violation = regeneration):
1. Character location: Check world model constraints for each character's position. No unexplained teleportation. Scene changes must describe travel
2. Commitment constraint: Check unfulfilled commitments. Must not forget or contradict them
3. Overdue storylines: Must advance at least one overdue storyline (if any)

[SHOULD] Advisory constraints:{foreshadowing_context_en}{habits_context_en}
{round_enhancements_en}
[REF] Reference information:
{vector_context_section_en}

{common_constraints}

[Writing Requirements]
1. **Story should be 1500-2000 words**, include 4-6 dialogue exchanges using quotation marks
2. Include environment descriptions, expressions, actions, inner thoughts; must match character settings
3. Characters must come from available people list
4. **Scene continuity**: First 3 sentences must establish location. No unexplained scene jumps
5. **Return ONLY story text**, no JSON, no options
6. **Anti-repetition red lines**: No cliché openings/recycled props/repeated entrances/recycled atmosphere. Vary structure and conflict types

{critical_close_en}
Now write the {round_name_en} story:"""

    return prompt
