"""
Validation and consistency checking prompts.

Contains:
- get_story_analysis_prompt: Story analysis for fact extraction
- get_consistency_validation_prompt: AI consistency validation
"""

from typing import Any, Dict, List, Optional


def get_story_analysis_prompt(
    story_text: str,
    player_choice: str,
    existing_facts_context: str,
    character_settings: Dict[str, Any],
    current_week: int,
    language: str,
) -> str:
    """
    Build prompt for the Story Analyzer Agent.

    The AI is asked to freely identify ALL narratively significant facts
    from the story — not limited to predefined categories. Each fact
    includes a constraint_text that will be injected into future prompts.

    Args:
        story_text: The full story text to analyze
        player_choice: Player's choice text
        existing_facts_context: Text listing currently active dynamic facts
        character_settings: Character settings for name references
        current_week: Current game week number
        language: Language code ('zh' or 'en')

    Returns:
        Analysis prompt string
    """
    # Build character name context
    char_name = ""
    if character_settings:
        char_name = character_settings.get("name", "")

    existing_section = ""
    if existing_facts_context:
        if language == "zh":
            existing_section = f'\n\n{existing_facts_context}\n（注意：如果故事中的新信息使某个已有事实过时或改变，请用 action:"update" 或 action:"invalidate" 处理）'
        else:
            existing_section = f'\n\n{existing_facts_context}\n(Note: If new information makes an existing fact outdated or changed, use action:"update" or action:"invalidate")'

    if language == "zh":
        return f"""请分析以下故事，提取所有对未来叙事有约束力的关键信息。

【故事文本】
{story_text}

【玩家选择】{player_choice}
【当前周数】第{current_week + 1}周
【主角名】{char_name}{existing_section}

【你的任务】
从故事中识别所有重要的世界事实，这些事实在后续故事中必须保持一致。**不要局限于预定义类别**，你可以识别任何类型的关键信息。

常见但不限于以下类型：
- **physical_state**: 身体状态（受伤、生病、怀孕、疲惫等）
- **emotional_state**: 重要的情感状态变化（失恋后的消沉、获奖后的振奋等）
- **possession**: 重要物品的获得或失去（买了车、丢了钥匙、收到礼物等）
- **knowledge**: 角色获知的重要信息（发现秘密、得知消息等）
- **environment**: 环境/场景状态变化（搬了新办公室、装修、天气灾害等）
- **social_dynamic**: 社交关系的微妙变化（暗恋、嫉妒、联盟、冷战等）
- **secret**: 角色掌握的秘密或隐瞒的事情
- **goal**: 角色设定的目标或计划（准备考研、打算创业等）
- **financial**: 重大财务变化（借了钱、签了合同、拿到奖金等）
- **reputation**: 名声/评价变化（被误解、获得认可、传出谣言等）
- **skill**: 技能/能力变化（学会了新技能、发现了天赋等）
- **time_sensitive**: 有时间限制的事项（X天内必须完成、约定了某日某事等）
- **其他任何你认为重要的类型**

【对每个事实，你必须提供】
- **constraint_text**: 这是最重要的字段！写一句明确的约束描述，告诉未来的故事生成AI：因为这个事实的存在，故事中必须/不能做什么。
  例如："张伟右臂打着石膏，至少4周内不能做任何需要双手的动作"
  例如："主角已知李经理在暗中调查财务问题，与他对话时应表现出警觉"
  例如："王琳送的手表一直戴在主角手上，偶尔的描写中应自然出现"
- **source_excerpt（必填）**: ★事实溯源★ 从原故事文本中摘录能证明这个事实的关键句子（10-50字），必须是原文中的直接引用。这用于后续验证事实是否被正确理解。

【输出格式 - JSON】
{{
  "facts": [
    {{
      "action": "new",
      "fact_type": "类型标签",
      "subject": "主体（人物/地点/物品名）",
      "description": "事实描述",
      "constraint_text": "对未来故事的明确约束（一定要具体、可执行）",
      "source_excerpt": "★从故事原文摘录的关键句子★",
      "related_entities": ["相关人物/地点"],
      "importance": "critical/important/normal/minor",
      "expiry_week": -1
    }},
    {{
      "action": "update",
      "target_fact_id": "要更新的已有事实ID",
      "fact_type": "类型标签",
      "subject": "主体",
      "description": "更新后的事实描述",
      "constraint_text": "更新后的约束",
      "source_excerpt": "★从故事原文摘录的关键句子★",
      "related_entities": ["相关人物/地点"],
      "importance": "critical/important/normal/minor",
      "expiry_week": -1
    }},
    {{
      "action": "invalidate",
      "target_fact_id": "要失效的已有事实ID"
    }}
  ]
}}

【注意事项】
- 只提取**真正影响后续叙事**的重要事实，不要提取每个细节
- constraint_text 必须具体、可执行，不能是空洞的描述
- source_excerpt 必须是故事原文的直接摘录，不能是自己总结的
- 每次提取 3-8 个事实为宜，视故事复杂度而定
- importance: critical=违反此约束会产生明显矛盾，important=应该遵守但偶尔可忽略，normal=一般约束，minor=锦上添花
- expiry_week: 如果事实有明确的有效期，填写过期周数；-1表示长期有效直到被更新
- 只返回JSON，不要其他文本"""
    else:
        return f"""Analyze the following story and extract all key information that constrains future narrative.

[Story Text]
{story_text}

[Player's Choice] {player_choice}
[Current Week] Week {current_week}
[Protagonist] {char_name}{existing_section}

[Your Task]
Identify all important world facts from the story that must remain consistent in future stories. **Do NOT limit yourself to predefined categories** — you may identify any type of key information.

Common but not limited to these types:
- **physical_state**: Body condition (injury, illness, pregnancy, exhaustion)
- **emotional_state**: Significant emotional changes (depression after breakup, elation after award)
- **possession**: Important items gained or lost (bought a car, lost keys, received gift)
- **knowledge**: Important information characters learned (discovered secret, received news)
- **environment**: Environment/setting changes (new office, renovation, weather disaster)
- **social_dynamic**: Subtle relationship changes (crush, jealousy, alliance, cold war)
- **secret**: Secrets characters hold or things they're hiding
- **goal**: Goals or plans characters set (preparing for grad school, planning startup)
- **financial**: Major financial changes (borrowed money, signed contract, received bonus)
- **reputation**: Reputation/evaluation changes (misunderstood, gained recognition, rumors)
- **skill**: Skill/ability changes (learned new skill, discovered talent)
- **time_sensitive**: Time-bound items (must complete within X days, scheduled something)
- **Any other type you deem important**

[For each fact, you MUST provide]
- **constraint_text**: This is the most important field! Write a clear constraint telling future story AI: because of this fact, the story must/cannot do what.
  E.g.: "Zhang Wei's right arm is in a cast, cannot do any two-handed activities for at least 4 weeks"
  E.g.: "Protagonist knows Manager Li is secretly investigating financial issues, should show alertness when talking to him"
- **source_excerpt (required)**: ★Fact tracing★ Extract key sentence from original story text that proves this fact (10-50 chars), must be direct quote from story. Used for later verification.

[Output Format - JSON]
{{
  "facts": [
    {{
      "action": "new",
      "fact_type": "type label",
      "subject": "subject (character/place/item name)",
      "description": "fact description",
      "constraint_text": "explicit constraint for future stories (must be specific, actionable)",
      "source_excerpt": "★key sentence quoted from original story★",
      "related_entities": ["related characters/places"],
      "importance": "critical/important/normal/minor",
      "expiry_week": -1
    }},
    {{
      "action": "update",
      "target_fact_id": "ID of existing fact to update",
      "fact_type": "type label",
      "subject": "subject",
      "description": "updated fact description",
      "constraint_text": "updated constraint",
      "source_excerpt": "★key sentence quoted from original story★",
      "related_entities": ["related characters/places"],
      "importance": "critical/important/normal/minor",
      "expiry_week": -1
    }},
    {{
      "action": "invalidate",
      "target_fact_id": "ID of existing fact to invalidate"
    }}
  ]
}}

[Notes]
- Only extract facts that **truly affect future narrative**, not every detail
- constraint_text must be specific and actionable, not vague descriptions
- source_excerpt must be direct quote from story text, not your summary
- Extract 3-8 facts per story as appropriate
- importance: critical=violating creates obvious contradiction, important=should follow but occasional miss OK, normal=general constraint, minor=nice to have
- expiry_week: if fact has clear expiration, fill week number; -1 means long-term valid until updated
- Return ONLY JSON, no other text"""


def get_consistency_validation_prompt(
    story_text: str,
    constraints_text: str,
    character_settings: Dict[str, Any],
    language: str,
    profiled_characters: List[str] = None,
) -> str:
    """
    Build prompt for AI consistency validation.

    Args:
        story_text: The generated story text to validate
        constraints_text: World model constraints text from WorldModel.build_constraints_text()
        character_settings: Character background settings
        language: Language code ('zh' or 'en')
        profiled_characters: 已建立行为画像的角色名单

    Returns:
        Validation prompt string
    """
    if profiled_characters is None:
        profiled_characters = []

    # Build character personality context
    personality_context = ""
    if character_settings:
        name = character_settings.get(
            "name", "主角" if language == "zh" else "Protagonist"
        )
        personality = character_settings.get("personality", {})
        traits = personality.get("traits", [])
        if traits:
            if language == "zh":
                personality_context = f"\n【主角性格特征】{name}：{'、'.join(traits)}"
            else:
                personality_context = (
                    f"\n[Protagonist Personality] {name}: {', '.join(traits)}"
                )

        # Key people personalities
        relationships = character_settings.get("relationships", {})
        key_people = relationships.get("key_people", [])
        people_lines = []
        for person in key_people:
            p_name = person.get("name", "")
            p_personality = person.get("personality", "")
            if p_name and p_personality:
                people_lines.append(f"- {p_name}: {p_personality}")

        if people_lines:
            if language == "zh":
                personality_context += "\n【关键人物性格】\n" + "\n".join(people_lines)
            else:
                personality_context += "\n[Key Character Personalities]\n" + "\n".join(
                    people_lines
                )

    # 已建立行为画像的角色说明
    profiled_chars_note = ""
    if profiled_characters:
        if language == "zh":
            profiled_chars_note = f"\n【已建立行为画像的角色】{'、'.join(profiled_characters)}\n这些角色已有明确的行为模式和性格记录，他们的性格不一致应视为严重问题。"
        else:
            profiled_chars_note = f"\n[Characters with Established Behavioral Profiles] {', '.join(profiled_characters)}\nThese characters have documented behavior patterns - personality inconsistencies for them should be treated as serious issues."

    if language == "zh":
        return f"""请检查以下故事是否与世界模型约束存在逻辑矛盾。

【待检查的故事】
{story_text}

【世界模型约束】
{constraints_text}{personality_context}{profiled_chars_note}

【检查维度】
1. **geographic（地理一致性）**：故事中同场景出现的人物，是否都在合理的地理位置？
2. **career（职业一致性）**：提到的职位、工作内容、职级是否与记录一致？
3. **personality（性格一致性）**：人物行为是否严重偏离已知性格设定？若性格有所变化，故事中是否有合理的草蛇灰线铺垫？
4. **temporal（时间一致性）**：时间、季节、日期描述是否自洽？
5. **commitment（承诺一致性）**：是否遗忘了到期的承诺/约定？若承诺被违背，是否有合理的解释？
   - ★重要：如果承诺标记为"关键承诺，待兑现"（critical），表示这是重要剧情承诺，故事应该有所体现或处理
   - 如果故事确实处理了承诺（兑现、违背、或协商变更），不应报告为问题
6. **causal（因果一致性）**：是否忽略了应有的因果后果？之前的行为是否产生了合理的后续影响？
7. **fabrication（编造事实）**：故事是否提到了**明显矛盾于**上下文/约束中已明确建立的过往事件、回忆或经历？

【重要说明 - 关于 fabrication 的判断】
- ⚠️ **请谨慎判断"编造事实"**：只有当故事提到的过往事件与历史记录**直接矛盾**时，才判定为 fabrication
- ❌ **不要将以下内容误判为 fabrication**：
  - 故事中对角色心理活动的合理描写（如"他想起了过去的某件事"）
  - 对角色过去经历的模糊提及（如"以前也遇到过类似的情况"）
  - 基于当前情境的自然联想或感慨（如"这种感觉似曾相识"）
  - 没有具体时间、地点、人物的情绪性回忆
  - 对角色性格、偏好、习惯的一般性描述（除非与历史记录直接冲突）
  - 使用隐喻、类比等修辞手法（如"仿佛回到了从前"）
- ✅ **只有以下情况才判定为 fabrication**（必须同时满足以下条件）：
  1. 明确提到了具体的时间、地点、人物
  2. 这个具体事件与历史记录中的明确记载**直接冲突**
  3. 冲突无法通过合理的解释来调和
  
  示例：
  - ❌ 历史记录："张伟和李明从未见过面" → 故事："上次和张伟见面时..." → **CRITICAL**
  - ❌ 历史记录："主角不会游泳" → 故事："他想起去年在海边教妹妹游泳" → **CRITICAL**
  - ⚠️ 故事："他想起了小时候的某个夏天"（无具体时间地点） → **不判定**
  - ⚠️ 故事："这种感觉很熟悉，就像曾经经历过"（心理感受） → **不判定**

【严重级别判断规则 - 由AI综合判断】
请你作为一个智能校验器，综合考虑以下因素来判断每个问题的严重级别：

1. **读者感知**：普通读者能否立即发现这个问题？
2. **故事连贯性影响**：这个问题是否会严重破坏故事的连贯性？
3. **角色重要性**：涉及的角色是否有已建立的行为画像（见上方列表）？
4. **问题类型**：因果断裂和编造事实通常更严重

请在 `severity` 字段中直接给出你的判断，并在 `reasoning` 字段中简要说明判断理由。

【输出格式 - JSON】
{{
  "issues": [
    {{
      "dimension": "geographic/career/personality/temporal/commitment/causal/fabrication",
      "severity": "CRITICAL/WARNING",
      "reasoning": "严重级别判断理由（考虑了哪些因素）",
      "description": "问题的具体描述",
      "fix_suggestion": "修正建议"
    }}
  ],
  "should_retry": true/false,
  "retry_reason": "如果建议重试，简要说明原因"
}}

【重试判断规则】
- `should_retry` 由你综合判断：考虑问题的数量、严重程度、和对读者体验的影响
- 一般来说，如果存在明显的因果断裂或编造事实，应该重试
- 也要考虑重试成本：如果问题不严重且可以通过小修改解决，可以不重试

【注意事项】
- 只报告确定存在的问题，不要过度推测
- 如果约束信息为空或不足以判断，不要报告该维度的问题
- 如果没有发现任何问题，返回 {{"issues": [], "should_retry": false}}
- 只返回JSON，不要其他文本"""
    else:
        return f"""Check if the following story has logical contradictions with the world model constraints.

[Story to Check]
{story_text}

[World Model Constraints]
{constraints_text}{personality_context}{profiled_chars_note}

[Check Dimensions]
1. **geographic**: Are characters in the same scene at geographically consistent locations?
2. **career**: Are mentioned positions, job duties, and ranks consistent with records?
3. **personality**: Do character behaviors severely deviate from known personality settings? If personality changes, is there reasonable foreshadowing?
4. **temporal**: Are time, season, and date descriptions self-consistent?
5. **commitment**: Are due commitments/agreements forgotten? If broken, is there reasonable explanation?
6. **causal**: Are expected causal consequences ignored? Do previous actions have reasonable follow-up effects?
7. **fabrication**: Does the story mention past events that **directly contradict** explicitly established facts in context/constraints?

[Important Notes - About fabrication Judgment]
- ⚠️ **Use caution when judging "fabrication"**: Only mark as fabrication when the mentioned past event **directly contradicts** historical records
- ❌ **Do NOT misjudge the following as fabrication**:
  - Reasonable depictions of character psychological activities (e.g., "He remembered something from the past")
  - Vague references to past experiences (e.g., "I've encountered similar situations before")
  - Natural associations or emotional reflections based on current context (e.g., "This feeling seems familiar")
  - Emotional memories without specific time, place, or people
  - General descriptions of character personality, preferences, or habits (unless directly conflicting with historical records)
  - Use of rhetorical devices like metaphors or analogies (e.g., "It was as if returning to the old days")
- ✅ **Only mark as fabrication** (ALL conditions must be met):
  1. Explicitly mentions specific time, place, and people
  2. This specific event **directly conflicts** with clearly documented historical records
  3. The conflict cannot be reconciled through reasonable interpretation
  
  Examples:
  - ❌ Historical record: "Zhang Wei and Li Ming never met" → Story: "Last time I met Zhang Wei..." → **CRITICAL**
  - ❌ Historical record: "Protagonist cannot swim" → Story: "He remembered teaching his sister to swim at the beach last year" → **CRITICAL**
  - ⚠️ Story: "He thought of a certain summer from his childhood" (no specific time/place) → **Do NOT mark**
  - ⚠️ Story: "This feeling was very familiar, as if he had experienced it before" (psychological feeling) → **Do NOT mark**

[Severity Judgment Rules - AI-driven]
As an intelligent validator, comprehensively consider these factors for each issue:

1. **Reader Perception**: Would an average reader immediately notice this issue?
2. **Story Continuity Impact**: Does this issue severely break story continuity?
3. **Character Importance**: Is the involved character one with an established behavioral profile (see list above)?
4. **Issue Type**: Broken causality and fabricated facts are typically more serious

Provide your judgment directly in the `severity` field, and briefly explain your reasoning in the `reasoning` field.

[Output Format - JSON]
{{
  "issues": [
    {{
      "dimension": "geographic/career/personality/temporal/commitment/causal/fabrication",
      "severity": "CRITICAL/WARNING",
      "reasoning": "Reasoning for severity judgment (what factors were considered)",
      "description": "Specific description of the issue",
      "fix_suggestion": "Suggested fix"
    }}
  ],
  "should_retry": true/false,
  "retry_reason": "If retry suggested, briefly explain why"
}}

[Retry Judgment Rules]
- `should_retry` is your comprehensive judgment: consider issue count, severity, and impact on reader experience
- Generally, clear causality breaks or fabricated facts should trigger retry
- Also consider retry cost: if issues are minor and fixable with small edits, may not need retry

[Notes]
- Only report issues you are certain about, do not over-speculate
- If constraint information is empty or insufficient, do not report issues for that dimension
- If no issues found, return {{"issues": [], "should_retry": false}}
- Return ONLY JSON, no other text"""
