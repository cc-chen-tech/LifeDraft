"""
Character creation and profile prompts.

Contains:
- get_character_setting_prompt: Character setting generation
- get_relationship_person_prompt: Single relationship person generation
- get_relationships_summary_prompt: Relationships summary generation
- get_initial_attributes_prompt: Initial character attributes
- get_opening_story_prompt: Opening story generation
- get_character_profile_synthesis_prompt: Behavioral profile synthesis
"""

from typing import Any, Dict, List, Optional

from src.ai.prompt_sanitizer import sanitize_life_vision, sanitize_player_name


def get_character_profile_synthesis_prompt(
    character_name: str,
    character_settings_traits: List[str],
    behavioral_evidence: List[str],
    existing_profile: Optional[Dict[str, Any]],
    language: str,
) -> str:
    """
    Build prompt for character behavioral profile synthesis.

    Called once per week per character, this prompt asks the AI to aggregate
    behavioral evidence (from stories) into a concise character profile that
    can be used as a constraint in future story generation.

    Args:
        character_name: Name of the character
        character_settings_traits: Original personality traits from character creation
        behavioral_evidence: List of behavioral observation strings from this week's stories
        existing_profile: Existing profile dict (None if first synthesis)
        language: Language code ('zh' or 'en')

    Returns:
        Synthesis prompt string
    """
    # 清洗角色名称输入，防止 prompt 注入
    sanitized_character_name = sanitize_player_name(character_name)
    traits_str = (
        "、".join(character_settings_traits) if character_settings_traits else "未设定"
    )

    evidence_str = (
        "\n".join(f"  - {e}" for e in behavioral_evidence)
        if behavioral_evidence
        else "（无新证据）"
    )

    existing_section = ""
    if existing_profile:
        if language == "zh":
            existing_section = f"""
【已有画像（需在此基础上更新）】
- 行为特征：{', '.join(existing_profile.get('behavioral_traits', []))}
- 说话风格：{existing_profile.get('speech_style', '未记录')}
- 决策倾向：{', '.join(existing_profile.get('decision_patterns', []))}
- 情绪特征：{', '.join(existing_profile.get('emotional_tendencies', []))}
- 行为红线：{', '.join(existing_profile.get('behavioral_boundaries', []))}
- 总结约束：{existing_profile.get('constraint_text', '')}
"""
        else:
            existing_section = f"""
[Existing Profile (update based on this)]
- Behavioral Traits: {', '.join(existing_profile.get('behavioral_traits', []))}
- Speech Style: {existing_profile.get('speech_style', 'Not recorded')}
- Decision Patterns: {', '.join(existing_profile.get('decision_patterns', []))}
- Emotional Tendencies: {', '.join(existing_profile.get('emotional_tendencies', []))}
- Behavioral Boundaries: {', '.join(existing_profile.get('behavioral_boundaries', []))}
- Summary Constraint: {existing_profile.get('constraint_text', '')}
"""

    if language == "zh":
        return f"""请为角色「{sanitized_character_name}」合成/更新行为画像。

【初始性格设定】{traits_str}

【本周行为证据】
{evidence_str}
{existing_section}
【你的任务】
综合初始设定和实际行为表现，生成这个角色的行为画像。画像应反映角色在故事中**实际展现**的行为模式，而非仅仅复述初始设定。

**关键原则**：
1. 行为画像应从具体行为中归纳，不是简单重复性格词
2. behavioral_boundaries（行为红线）是最重要的字段 — 定义这个角色"绝对不会做什么"
3. constraint_text 必须是一段完整的、可直接注入AI提示词的约束描述
4. 允许角色有适度成长和变化，但核心性格基调应保持稳定
5. 如果已有画像，在其基础上微调，不要每次重写

【输出格式 - JSON】
{{
  "behavioral_traits": ["3-5个行为特征标签，如'冲突回避型'、'善于共情'"],
  "speech_style": "说话风格描述，如'温和但坚定，偶尔用比喻'",
  "decision_patterns": ["2-4个决策倾向，如'优先考虑他人感受'、'风险厌恶型'"],
  "emotional_tendencies": ["2-3个情绪特征，如'表面平静但内心波动大'"],
  "behavioral_boundaries": ["2-4个行为红线，如'绝不在公开场合发怒'、'不会主动伤害弱者'"],
  "constraint_text": "一段50-100字的综合约束描述，告诉未来的故事生成AI这个角色应该如何表现。例如：'{sanitized_character_name}是一个表面温和但内心坚定的人，面对冲突时倾向于先退让再迂回解决。他说话柔和但逻辑清晰，绝不会在众人面前大声争吵或做出冲动决定。'"
}}

- 只返回JSON，不要其他文本"""
    else:
        return f"""Synthesize/update a behavioral profile for character "{sanitized_character_name}".

[Initial Personality Traits] {traits_str}

[This Week's Behavioral Evidence]
{evidence_str}
{existing_section}
[Your Task]
Combine initial settings and actual behavioral evidence to generate this character's behavioral profile. The profile should reflect patterns **actually demonstrated** in stories, not just restate initial traits.

**Key Principles**:
1. Profiles should be induced from concrete behaviors, not simple trait repetition
2. behavioral_boundaries is the most important field — defines what this character would "NEVER do"
3. constraint_text must be a complete, directly injectable prompt constraint
4. Allow moderate character growth, but core personality tone should be stable
5. If existing profile exists, fine-tune it, don't rewrite from scratch

[Output Format - JSON]
{{
  "behavioral_traits": ["3-5 behavioral trait labels"],
  "speech_style": "description of speaking style",
  "decision_patterns": ["2-4 decision tendencies"],
  "emotional_tendencies": ["2-3 emotional characteristics"],
  "behavioral_boundaries": ["2-4 absolute behavioral boundaries, things character would NEVER do"],
  "constraint_text": "A 50-100 word comprehensive constraint description telling future story AI how this character should behave."
}}

- Return ONLY JSON, no other text"""


# ==================== Character Setting Prompts ====================


def get_character_setting_prompt(
    setting_type: str,
    player_name: str,
    life_vision: str,
    previous_settings: Dict[str, Any],
    language: str = "zh",
    feedback: Optional[str] = None,
) -> str:
    """Build prompt for generating a specific character setting.

    Args:
        setting_type: One of 'era', 'age', 'gender', 'world', 'family',
                      'relationships', 'traits', 'wealth'.
        player_name: Player's chosen name.
        life_vision: Player's life vision text.
        previous_settings: Already-generated settings dict.
        language: 'zh' or 'en'.
        feedback: Optional user feedback for regeneration.

    Returns:
        The assembled prompt string.
    """
    import json as _json

    # 清洗用户输入，防止 prompt 注入
    sanitized_player_name = sanitize_player_name(player_name)
    sanitized_life_vision = sanitize_life_vision(life_vision)

    if language == "zh":
        base_context = f"""
玩家姓名：{sanitized_player_name}
人生愿景：{sanitized_life_vision}

已生成的设定：
{_json.dumps(previous_settings, ensure_ascii=False, indent=2)}
"""
        prompts = {
            "era": f"""{base_context}
{'【用户明确要求：' + feedback + '，必须严格按照用户要求生成时代背景】' if feedback else '请生成一个时代背景设定（公元年份）。考虑玩家的人生愿景，选择一个合适的时代。'}
{'注意：用户反馈优先于人生愿景，必须遵循用户的具体要求。' if feedback else ''}
返回JSON格式：
{{
    "year": <具体的公元年份数字>,
    "era_description": "时代背景的简短描述（50-100字）",
    "world_context": "世界大环境的描述（50-100字）"
}}
""",
            "age": f"""{base_context}
请生成玩家的起始年龄。考虑时代背景和人生愿景，选择一个合适的年龄。

**重要**：必须根据已生成的时代年份计算出生年份！
- 例如：如果时代是1990年，年龄是25岁，那么出生年份必须是1965年
- 出生年份 = 时代年份 - 年龄

返回JSON格式：
{{
    "age": <具体年龄数字>,
    "birth_year": <根据时代年份计算出的出生年份>,
    "age_description": "这个年龄段的特征描述（30-50字）"
}}
""",
            "gender": f"""{base_context}
请生成玩家的性别设定。
返回JSON格式：
{{
    "gender": "<男/女/其他>",
    "gender_description": "性别相关的社会背景描述（30-50字）"
}}
""",
            "world": f"""{base_context}
请生成社会和世界情况的详细设定。包括科技水平、社会制度、经济状况等。
返回JSON格式：
{{
    "world_description": "社会和世界情况的详细描述（100-150字）",
    "technology_level": "科技水平描述",
    "social_system": "社会制度描述",
    "economy": "经济状况描述"
}}
""",
            "family": f"""{base_context}
请生成家庭情况设定。包括家庭成员、家庭经济状况、家庭关系等。

**重要**：家庭成员必须包含具体姓名，不要用"父母"、"爸爸"这样的模糊称呼。

返回JSON格式：
{{
    "family_description": "家庭情况的详细描述（100-150字）",
    "family_members": [
        {{"name": "父亲全名", "role": "父亲", "relationship": "与主角的关系描述"}},
        {{"name": "母亲全名", "role": "母亲", "relationship": "与主角的关系描述"}}
    ],
    "family_economy": "家庭经济状况",
    "family_relationships": "家庭成员关系描述"
}}
""",
            "relationships": f"""{base_context}
注意：关系设定现在采用逐个生成人物的方式，此提示词已不再使用。
请使用 generate_single_relationship_person() 方法逐个生成人物。
""",
            "traits": f"""{base_context}
请生成个人特点设定。包括性格、能力、兴趣、优缺点等。
返回JSON格式：
{{
    "traits_description": "个人特点的详细描述（100-150字）",
    "personality": "性格特点",
    "abilities": "能力特长",
    "interests": "兴趣爱好",
    "strengths": "优点",
    "weaknesses": "缺点"
}}
""",
            "wealth": f"""{base_context}
请根据角色的家庭背景、时代背景、年龄和能力，生成角色的初始财富和货币单位。

要求：
1. 财富金额（wealth）：根据家庭经济状况、时代背景、年龄和角色能力合理设定（1000-1000000）
   - 富裕家庭 → 财富较高（50000-200000）
   - 中产家庭 → 财富中等（20000-80000）
   - 贫困家庭 → 财富较低（1000-15000，但绝对不能为0）
   - 现代时代 → 财富金额较高
   - 古代时代 → 财富金额较低
   - 年龄较大 → 可能有更多积累
   - 商业/投资能力强 → 可能有更多收入
   - **重要：财富金额绝对不能为0，最低应为1000**
2. 货币单位（currency）：根据时代背景和世界设定选择合适的货币单位
   - 现代中国：人民币（¥）
   - 现代美国：美元（$）
   - 古代中国：两、文、贯等
   - 古代欧洲：金币、银币等
   - 未来/科幻：信用点、星币等
   - 其他时代/地区：根据设定选择合适的货币单位

返回JSON格式：
{{
    "wealth": <根据家庭背景和时代合理设定的财富数值>,
    "currency": "<货币符号，如：¥/$/金币/信用点等>",
    "currency_name": "<货币名称，如：人民币/美元/金币/信用点等>",
    "wealth_description": "财富来源和初始经济状况的详细描述（50-100字）"
}}

**重要提醒：wealth 字段必须是正整数，范围在 1000-1000000 之间，绝对不能为 0。**
""",
        }
    else:
        base_context = f"""
Player Name: {sanitized_player_name}
Life Vision: {sanitized_life_vision}

Generated Settings:
{_json.dumps(previous_settings, indent=2)}
"""
        prompts = {
            "era": f"""{base_context}
Generate an era setting (year AD). Consider the player's life vision and choose an appropriate era.
Return JSON format:
{{
    "year": <specific year as a number>,
    "era_description": "Brief description of the era (50-100 words)",
    "world_context": "Description of the world context (50-100 words)"
}}
""",
            "age": f"""{base_context}
Generate the player's starting age. Consider the era and life vision.

**IMPORTANT**: You MUST calculate the birth year based on the generated era year!
- Example: If era is 1990 and age is 25, then birth_year MUST be 1965
- birth_year = era_year - age

Return JSON format:
{{
    "age": <specific age number>,
    "birth_year": <calculated birth year based on era>,
    "age_description": "Description of this age stage (30-50 words)"
}}
""",
            "gender": f"""{base_context}
Generate the player's gender setting.
Return JSON format:
{{
    "gender": "<Male/Female/Other>",
    "gender_description": "Social context related to gender (30-50 words)"
}}
""",
            "world": f"""{base_context}
Generate detailed world and society setting. Include technology level, social system, economy, etc.
Return JSON format:
{{
    "world_description": "Detailed description of world and society (100-150 words)",
    "technology_level": "Technology level description",
    "social_system": "Social system description",
    "economy": "Economy description"
}}
""",
            "family": f"""{base_context}
Generate family setting. Include family members, economic status, relationships, etc.
Return JSON format:
{{
    "family_description": "Detailed family description (100-150 words)",
    "family_members": ["Member1", "Member2"],
    "family_economy": "Family economic status",
    "family_relationships": "Family relationship description"
}}
""",
            "relationships": f"""{base_context}
Note: Relationships are now generated one person at a time. This prompt is no longer used.
Please use generate_single_relationship_person() method to generate people one by one.
""",
            "traits": f"""{base_context}
Generate personal traits. Include personality, abilities, interests, strengths, weaknesses.
Return JSON format:
{{
    "traits_description": "Detailed traits description (100-150 words)",
    "personality": "Personality traits",
    "abilities": "Abilities and talents",
    "interests": "Interests and hobbies",
    "strengths": "Strengths",
    "weaknesses": "Weaknesses"
}}
""",
            "wealth": f"""{base_context}
Generate the character's initial wealth and currency unit based on family background, era, age, and abilities.

Requirements:
1. Wealth amount (wealth): Reasonably set based on family economy, era, age, and character abilities (1000-1000000)
   - Wealthy family → higher wealth (50000-200000)
   - Middle-class family → moderate wealth (20000-80000)
   - Poor family → lower wealth (1000-15000, but NEVER 0)
   - Modern era → higher wealth amount
   - Ancient era → lower wealth amount
   - Older age → may have more savings
   - Strong business/investment abilities → may have more income
   - **IMPORTANT: Wealth amount must NEVER be 0, minimum should be 1000**
2. Currency unit (currency): Choose appropriate currency unit based on era and world setting
   - Modern China: RMB (¥)
   - Modern USA: Dollar ($)
   - Ancient China: Liang, Wen, Guan, etc.
   - Ancient Europe: Gold coins, Silver coins, etc.
   - Future/Sci-fi: Credits, Star coins, etc.
   - Other eras/regions: Choose appropriate currency unit based on setting

Return JSON format:
{{
    "wealth": <wealth amount based on family background and era>,
    "currency": "<currency symbol, e.g.: $/¥/gold coins/credits>",
    "currency_name": "<currency name, e.g.: Dollar/Yuan/Gold Coin/Credit>",
    "wealth_description": "Detailed description of wealth source and initial economic status (50-100 words)"
}}

**IMPORTANT REMINDER: The wealth field must be a positive integer between 1000-1000000, and must NEVER be 0.**
""",
        }

    prompt = prompts.get(setting_type, "")

    if feedback:
        if language == "zh":
            prompt += (
                f"\n\n用户反馈：{feedback}\n请根据反馈重新生成，确保满足用户的要求。"
            )
        else:
            prompt += f"\n\nUser Feedback: {feedback}\nPlease regenerate based on the feedback to meet user requirements."

    return prompt


# ==================== Character Creation Prompts ====================


def get_relationship_person_prompt(
    player_name: str,
    life_vision: str,
    previous_settings: Dict[str, Any],
    existing_people: list,
    person_index: int,
    total_needed: int,
    language: str = "zh",
    feedback: Optional[str] = None,
) -> str:
    """Generate prompt for creating a single relationship person."""
    import json as _json

    # 清洗用户输入，防止 prompt 注入
    sanitized_player_name = sanitize_player_name(player_name)
    sanitized_life_vision = sanitize_life_vision(life_vision)

    base_context = f"""
玩家姓名：{sanitized_player_name}
人生愿景：{sanitized_life_vision}

已生成的设定：
{_json.dumps(previous_settings, ensure_ascii=False, indent=2)}

已生成的关系人物（{len(existing_people)}/{total_needed}）：
{_json.dumps(existing_people, ensure_ascii=False, indent=2) if existing_people else "暂无"}
"""

    if language == "zh":
        prompt = f"""{base_context}
请生成第{person_index + 1}个关系人物（共需要{total_needed}个）。

**CRITICAL REQUIREMENTS - 必须严格遵守：**
1. **绝对禁止**使用"有一些朋友"、"几个朋友"、"一些朋友"等泛泛描述
2. 必须根据玩家的性格特点、家庭背景、时代背景和人生愿景来生成
3. 必须与已生成的人物不同（避免重复角色和姓名）
4. 必须具体、生动、有故事性

**⚠️ 人物命名规则 - 必须严格匹配时代背景：**
- 古代中国：使用古风名字，如"李青云"、"王婉儿"、"赵明轩"、"沈若兰"
- 现代中国：使用现代中文名字，如"张伟"、"李娜"、"王明"、"刘婷"
- 民国时期：使用民国风格名字，如"林徽音"、"陈独秀"、"宋美龄"
- 欧美西方：使用英文名字，如"John Smith"、"Emma Watson"、"Michael Brown"
- 日本：使用日文名字，如"田中一郎"、"佐藤美咲"、"山田太郎"
- 韩国：使用韩文名字，如"金智秀"、"朴俊浩"、"李秀贤"
- **绝对禁止**在古代背景使用现代名字，或在现代背景使用不符合地域文化的名字！

**角色类型建议**（根据已生成的人物选择不同的类型）：
- 如果还没有：大学室友/同学、导师/老师、同事/工作伙伴、青梅竹马、邻居、亲戚等
- 根据玩家的背景选择合适的角色类型

**返回JSON格式（完整角色属性）：**
{{
    "name": "具体姓名（必须严格匹配时代和地域文化，不能与已生成人物重复）",
    "role": "具体角色定位（如：大学室友、创业伙伴、青梅竹马、同事、邻居等）",
    "relationship_desc": "详细的关系描述（50-100字）：如何认识、关系特点、对玩家的影响、互动方式等",
    "age": <具体年龄数字>,
    "gender": "<男/女>",
    "occupation": "<职业>",
    "personality_traits": ["<性格特点1>", "<性格特点2>", "<性格特点3>"],
    "temperament": "<sanguine/choleric/melancholic/phlegmatic/balanced>",
    "mood": <0-100之间的数值>,
    "mood_stability": <0-100之间的数值>,
    "social_status": "<student/ordinary/professional/leader/elite>",
    "influence": <0-100之间的数值>,
    "competence": <0-100之间的数值>,
    "specialty": ["<专长1>", "<专长2>"],
    "affinity": <0-100之间的数值>,
    "trust": <0-100之间的数值>,
    "respect": <0-100之间的数值>
}}

**气质类型说明：**
- sanguine(多血质)：热情活泼、善于交际、乐观开朗
- choleric(胆汁质)：直接果断、有领导力、急躁冲动
- melancholic(抑郁质)：深思熟虑、敏感细腻、完美主义
- phlegmatic(粘液质)：温和稳重、耐心包容、不急不躁
- balanced(均衡)：各方面比较平衡

现在请生成第{person_index + 1}个关系人物：
"""
    else:
        prompt = f"""{base_context}
Generate the {person_index + 1}th relationship person (need {total_needed} total).

**CRITICAL REQUIREMENTS:**
1. **ABSOLUTELY FORBIDDEN** to use vague descriptions like "some friends", "a few friends"
2. Must be based on player's personality, family background, era, and life vision
3. Must be different from already generated people (avoid duplicate roles and names)
4. Must be specific, vivid, and story-like

**⚠️ NAMING RULES - Names MUST match the era and cultural background:**
- Ancient China: Use classical Chinese names, e.g., "李青云", "王婉儿", "赵明轩"
- Modern China: Use modern Chinese names, e.g., "张伟", "李娜", "王明"
- Republican Era China: Use Republican-era style names, e.g., "林徽音", "陈独秀"
- Western/European: Use English names, e.g., "John Smith", "Emma Watson", "Michael Brown"
- Japan: Use Japanese names, e.g., "田中一郎", "佐藤美咲", "山田太郎"
- Korea: Use Korean names, e.g., "金智秀", "朴俊浩", "李秀贤"
- **ABSOLUTELY FORBIDDEN** to use modern names in ancient settings, or culturally mismatched names!

**Role Type Suggestions** (choose different types based on existing people):
- If not yet: college roommate/classmate, mentor/teacher, colleague/work partner, childhood friend, neighbor, relative, etc.
- Choose appropriate role type based on player's background

**Return JSON format (full character attributes):**
{{
    "name": "Specific name (MUST strictly match era and cultural background, cannot duplicate existing people)",
    "role": "Specific role (e.g., college roommate, business partner, childhood friend, colleague, neighbor, etc.)",
    "relationship_desc": "Detailed relationship description (50-100 words): how you met, relationship characteristics, impact on player, interaction style",
    "age": 25,
    "gender": "Male/Female",
    "occupation": "Occupation",
    "personality_traits": ["trait1", "trait2", "trait3"],
    "temperament": "sanguine/choleric/melancholic/phlegmatic/balanced",
    "mood": 60,
    "mood_stability": 70,
    "social_status": "student/ordinary/professional/leader/elite",
    "influence": 30,
    "competence": 50,
    "specialty": ["specialty1", "specialty2"],
    "affinity": 55,
    "trust": 50,
    "respect": 50
}}

**Temperament Types:**
- sanguine: Enthusiastic, sociable, optimistic
- choleric: Direct, decisive, leadership-oriented
- melancholic: Thoughtful, sensitive, perfectionist
- phlegmatic: Calm, patient, tolerant
- balanced: Well-rounded in all aspects

Now generate the {person_index + 1}th relationship person:
"""

    if feedback:
        if language == "zh":
            prompt += f"\n\n用户反馈：{feedback}\n请根据反馈重新生成这个人物的信息。"
        else:
            prompt += f"\n\nUser Feedback: {feedback}\nPlease regenerate this person's information based on the feedback."

    return prompt


def get_relationships_summary_prompt(
    player_name: str,
    life_vision: str,
    previous_settings: Dict[str, Any],
    key_people: list,
    language: str = "zh",
) -> str:
    """Generate prompt for creating a relationships summary."""
    import json as _json

    # 清洗用户输入，防止 prompt 注入
    sanitized_player_name = sanitize_player_name(player_name)
    sanitized_life_vision = sanitize_life_vision(life_vision)

    base_context = f"""
玩家姓名：{sanitized_player_name}
人生愿景：{sanitized_life_vision}

已生成的设定：
{_json.dumps(previous_settings, ensure_ascii=False, indent=2)}

已生成的所有关系人物：
{_json.dumps(key_people, ensure_ascii=False, indent=2)}
"""

    if language == "zh":
        return f"""{base_context}
请根据以上所有关系人物，生成一段详细的社会关系总结描述（100-150字）。

要求：
1. 必须具体描述这些关系的建立过程、特点、对玩家的意义
2. 必须提到每个人物的姓名和角色
3. 必须生动、有故事性，绝对不能泛泛而谈
4. 绝对禁止使用"有一些朋友"、"几个朋友"等泛泛描述

返回JSON格式：
{{
    "relationships_description": "详细描述（100-150字）"
}}
"""
    else:
        return f"""{base_context}
Based on all the relationship people above, generate a detailed social relationships summary (100-150 words).

Requirements:
1. Must specifically describe how these relationships were established, their characteristics, and significance to the player
2. Must mention each person's name and role
3. Must be vivid and story-like, absolutely cannot be vague
4. Absolutely forbidden to use vague descriptions like "some friends", "a few friends"

Return JSON format:
{{
    "relationships_description": "Detailed description (100-150 words)"
}}
"""


def get_initial_attributes_prompt(
    character_settings: Dict[str, Any],
    language: str = "zh",
) -> str:
    """Generate prompt for creating initial character attributes."""
    traits = character_settings.get("traits", {})
    personality = traits.get("personality", "")
    abilities = traits.get("abilities", "")
    strengths = traits.get("strengths", "")
    weaknesses = traits.get("weaknesses", "")
    traits_description = traits.get("traits_description", "")

    family = character_settings.get("family", {})
    family_economy = family.get("family_economy", "")
    family_description = family.get("family_description", "")

    era = character_settings.get("era", {})
    era_description = era.get("era_description", "")
    world_context = era.get("world_context", "")

    age = character_settings.get("age", {}).get("age", 22)

    if language == "zh":
        return f"""根据以下角色特点，生成初始的核心属性数值：

角色特点：
- 年龄：{age}岁
- 性格：{personality}
- 能力：{abilities}
- 优点：{strengths}
- 缺点：{weaknesses}
- 特点描述：{traits_description}

家庭背景：
- 家庭经济：{family_economy}
- 家庭描述：{family_description}

时代背景：
- 时代描述：{era_description}
- 世界背景：{world_context}

请根据角色的性格、能力、家庭背景和时代背景，合理生成初始属性值：
- 精力（energy）：反映角色的体力和活力水平（0-100）
- 情绪（mood）：反映角色的心理状态和乐观程度（0-100）
- 学识（knowledge）：反映角色的知识水平和学习能力（0-100）
- 财富（wealth）：反映角色的初始经济状况（0-1000000，根据家庭背景、时代背景和年龄合理设定）

返回JSON格式：
{{
  "energy": 70,
  "mood": 60,
  "knowledge": 50,
  "wealth": 10000
}}

要求：
1. 精力、情绪、学识范围：0-100
2. 财富范围：0-1000000，需根据以下因素合理设定：
   - 家庭经济状况（富裕家庭 → 财富较高，贫困家庭 → 财富较低）
   - 时代背景（现代 → 财富较高，古代 → 财富较低）
   - 年龄（年龄较大 → 可能有更多积累）
   - 角色能力（能力强 → 可能有更多收入）
3. 性格外向/乐观 → mood较高
4. 能力强/有天赋 → knowledge较高
5. 体力好/年轻 → energy较高
6. 性格内向/悲观 → mood较低
7. 能力弱/缺乏经验 → knowledge较低
8. 体弱/年长 → energy较低
"""
    else:
        return f"""Based on the following character traits, generate initial core attribute values:

Character Traits:
- Age: {age} years old
- Personality: {personality}
- Abilities: {abilities}
- Strengths: {strengths}
- Weaknesses: {weaknesses}
- Traits Description: {traits_description}

Family Background:
- Family Economy: {family_economy}
- Family Description: {family_description}

Era Background:
- Era Description: {era_description}
- World Context: {world_context}

Please generate initial attribute values based on the character's personality, abilities, family background, and era:
- Energy: Reflects the character's physical strength and vitality (0-100)
- Mood: Reflects the character's psychological state and optimism (0-100)
- Knowledge: Reflects the character's knowledge level and learning ability (0-100)
- Wealth: Reflects the character's initial economic status (0-1000000, reasonably set based on family background, era, and age)

Return JSON format:
{{
  "energy": 70,
  "mood": 60,
  "knowledge": 50,
  "wealth": 10000
}}

Requirements:
1. Energy, mood, knowledge range: 0-100
2. Wealth range: 0-1000000, reasonably set based on:
   - Family economy (wealthy family → higher wealth, poor family → lower wealth)
   - Era background (modern → higher wealth, ancient → lower wealth)
   - Age (older → may have more savings)
   - Character abilities (strong abilities → may have more income)
3. Extroverted/optimistic personality → higher mood
4. Strong abilities/talented → higher knowledge
5. Good physical condition/young → higher energy
6. Introverted/pessimistic personality → lower mood
7. Weak abilities/lack of experience → lower knowledge
8. Weak physical condition/older → lower energy
"""


def get_opening_story_prompt(
    character_settings: Dict[str, Any],
    player_name: str,
    life_vision: str,
    formatted_family_members: str,
    language: str = "zh",
) -> str:
    """Generate prompt for creating the opening story.

    Args:
        character_settings: All character settings.
        player_name: Player's name.
        life_vision: Player's life vision.
        formatted_family_members: Pre-formatted family members string.
        language: Language code.
    """
    # 清洗用户输入，防止 prompt 注入
    sanitized_player_name = sanitize_player_name(player_name)
    sanitized_life_vision = sanitize_life_vision(life_vision)

    era = character_settings.get("era", {})
    age_info = character_settings.get("age", {})
    gender = character_settings.get("gender", {})
    world = character_settings.get("world", {})
    family = character_settings.get("family", {})
    relationships = character_settings.get("relationships", {})
    traits = character_settings.get("traits", {})
    wealth = character_settings.get("wealth", {})

    if language == "zh":
        return f"""请基于以下角色设定，生成一个生动的开场故事（300-400字）。

【角色信息】
姓名：{sanitized_player_name}
人生愿景：{sanitized_life_vision}

【时代背景】
{era.get('era_description', '')}，{era.get('year', '')}年
{era.get('world_context', '')}

【基本信息】
年龄：{age_info.get('age', '')}岁
性别：{gender.get('gender', '')}

【世界设定】
{world.get('world_description', '')}
社会制度：{world.get('social_system', '')}
科技水平：{world.get('technology_level', '')}

【家庭背景】
{family.get('family_description', '')}
家庭成员：{formatted_family_members}
经济状况：{family.get('family_economy', '')}

【社会关系】
{relationships.get('relationships_description', '')}

【个人特点】
{traits.get('traits_description', '')}
性格：{traits.get('personality', '')}
优点：{traits.get('strengths', '')}
缺点：{traits.get('weaknesses', '')}

【财富状况】
当前财富：{wealth.get('currency', '')}{wealth.get('wealth', '')}
{wealth.get('wealth_description', '')}

请生成一个引人入胜的开场故事，要求：
1. 以第三人称视角叙述
2. 生动描绘角色所处的环境和氛围
3. 展现角色的性格特点和当前状态
4. 暗示角色的人生愿景和未来可能性
5. 自然融入时代背景、家庭情况和人际关系
6. 以一个关键时刻或场景作为故事开端
7. 只返回故事文本，不要任何JSON格式或其他标记
"""
    else:
        return f"""Generate a vivid opening story (300-400 words) based on the following character settings.

【Character Info】
Name: {sanitized_player_name}
Life Vision: {sanitized_life_vision}

【Era】
{era.get('era_description', '')}, Year {era.get('year', '')}
{era.get('world_context', '')}

【Basic Info】
Age: {age_info.get('age', '')}
Gender: {gender.get('gender', '')}

【World Setting】
{world.get('world_description', '')}
Social System: {world.get('social_system', '')}
Tech Level: {world.get('technology_level', '')}

【Family】
{family.get('family_description', '')}
Members: {formatted_family_members}
Economy: {family.get('family_economy', '')}

【Relationships】
{relationships.get('relationships_description', '')}

【Traits】
{traits.get('traits_description', '')}
Personality: {traits.get('personality', '')}
Strengths: {traits.get('strengths', '')}
Weaknesses: {traits.get('weaknesses', '')}

【Wealth】
Current: {wealth.get('currency', '')}{wealth.get('wealth', '')}
{wealth.get('wealth_description', '')}

Generate an engaging opening story with:
1. Third-person narrative
2. Vivid environment and atmosphere
3. Character personality and current state
4. Hints at life vision and future possibilities
5. Natural integration of era, family, and relationships
6. Start with a key moment or scene
7. Return ONLY the story text, no JSON or markup
"""
