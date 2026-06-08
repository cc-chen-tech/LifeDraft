"""Summary generation prompts."""

from typing import Any, Dict, List, Optional

from config.prompts._helpers import _build_time_context, _format_people_names


def _build_weekly_summary_time_guard(
    game_date_info: Optional[Dict[str, Any]], language: str
) -> str:
    if not game_date_info:
        return ""

    total_week = game_date_info.get("total_week")
    date_string = game_date_info.get("date_string", "")
    date_string_en = game_date_info.get("date_string_en", "")

    if language == "zh":
        next_week = total_week + 1 if isinstance(total_week, int) else "下一"
        current_label = f"第{total_week}周" if isinstance(total_week, int) else "当前周"
        return f"""
【周总结时间边界】
- 本总结只覆盖{date_string or current_label}这一周的周一、周中、周末三个回合。
- 不得把下一周写进本周总结，不得把本周周末写成“周日（第{next_week}周）”。
- 禁止写成“周日（第2周）”这类把日期推进到下一周的表达。"""

    next_week_en = total_week + 1 if isinstance(total_week, int) else "next"
    current_label_en = f"Week {total_week}" if isinstance(total_week, int) else "the current week"
    return f"""
[Weekly Summary Time Boundary]
- This summary covers only {date_string_en or current_label_en}: Monday, midweek, and weekend.
- Do not include next week in this week's summary, and do not label this week's weekend as Sunday of Week {next_week_en}."""


def get_ending_prompt(
    final_state: Dict[str, Any], decision_history: list, language: str = "en"
) -> str:
    """Generate prompt for ending narrative."""

    if language == "zh":
        return f"""根据以下游戏结果，生成一段人生总结（200-300字）：

最终状态：{final_state}
关键决策：{decision_history[-10:] if len(decision_history) > 10 else decision_history}

总结应该回顾这段人生旅程，突出关键转折点和最终成就。"""
    else:
        return f"""Generate a life summary (200-300 words) based on the following game results:

Final State: {final_state}
Key Decisions: {decision_history[-10:] if len(decision_history) > 10 else decision_history}

The summary should review this life journey, highlighting key turning points and final achievements."""


def get_four_week_summary_prompt(
    stories: list,
    decisions: list,
    character_settings: Optional[Dict[str, Any]] = None,
    language: str = "zh",
    game_date_info: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate prompt for 4-week summary.

    Args:
        stories: List of story descriptions from the past 4 weeks
        decisions: List of decisions made in the past 4 weeks
        character_settings: Character background settings
        language: Language code
        game_date_info: Game-internal date info for time context

    Returns:
        Formatted prompt string
    """
    stories_text = "\n\n".join([f"第{i+1}周：{s}" for i, s in enumerate(stories)])
    decisions_text = "\n".join(
        [f"- {d.get('choice', '')}（{d.get('event', '')[:30]}...）" for d in decisions]
    )

    time_context = _build_time_context(game_date_info, language)

    if language == "zh":
        return f"""请基于以下4周的故事和决策，生成一个简洁的总结（100-150字）：{time_context}

【过去4周的故事】
{stories_text}

【做出的决策】
{decisions_text}

请总结这段时间的主要经历、重要决策和其影响。总结中需包含时间信息。仅返回总结文字，不要其他内容。"""
    else:
        return f"""Generate a concise summary (100-150 words) based on the following 4 weeks of stories and decisions:{time_context}

[Stories from the past 4 weeks]
{stories_text}

[Decisions made]
{decisions_text}

Summarize the main experiences, important decisions, and their impacts during this period. Include time context in the summary. Return only the summary text."""


def get_yearly_summary_prompt(
    four_week_summaries: list,
    character_settings: Optional[Dict[str, Any]] = None,
    start_week: int = 0,
    end_week: int = 47,
    language: str = "zh",
    game_date_info: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate prompt for 48-week (yearly) summary.

    Args:
        four_week_summaries: List of 4-week summaries (up to 12)
        character_settings: Character background settings
        start_week: Starting week number
        end_week: Ending week number
        language: Language code
        game_date_info: Game-internal date info for time context

    Returns:
        Formatted prompt string
    """
    summaries_text = "\n\n".join(
        [
            f"第{i+1}个月：{s.get('summary', s) if isinstance(s, dict) else s}"
            for i, s in enumerate(four_week_summaries)
        ]
    )

    time_context = _build_time_context(game_date_info, language)

    if language == "zh":
        return f"""请基于以下12个月（48周）的总结，生成一个年度回顾（200-300字）：{time_context}

【每月总结】
{summaries_text}

请总结这一年的主要成就、重要转折点、人物成长和变化。突出最具影响力的事件和决策。总结中需包含时间范围信息。仅返回总结文字，不要其他内容。"""
    else:
        return f"""Generate a yearly review (200-300 words) based on the following 12 months (48 weeks) of summaries:{time_context}

[Monthly Summaries]
{summaries_text}

Summarize this year's main achievements, important turning points, character growth and changes. Highlight the most impactful events and decisions. Include time range info in the summary. Return only the summary text."""


def get_story_compression_prompt(
    story: str,
    choice: str,
    language: str,
    pending_storylines: Optional[list] = None,
    established_facts: Optional[list] = None,
    character_habits: Optional[list] = None,
) -> str:
    """
    Generate prompt to compress a story into a 200-character summary,
    evaluate storyline status, judge if event is concluded, extract/update world facts,
    and track character habit changes.

    Args:
        story: The full story text (1500-2000 chars)
        choice: The player's choice text
        language: Language code ('zh' or 'en')
        pending_storylines: Current list of pending storylines for evaluation
        established_facts: Current established world facts for consistency tracking
        character_habits: Current character habits for tracking changes

    Returns:
        Prompt for story compression with storyline, event conclusion, fact and habit evaluation
    """
    # Build pending storylines context for AI evaluation
    pending_context = ""
    if pending_storylines:
        if language == "zh":
            lines = ["\n【当前未完结的剧情线】"]
            for sl in pending_storylines:
                lines.append(
                    f"- [{sl.get('importance', 'medium')}] {sl.get('description', '')}"
                )
            pending_context = "\n".join(lines)
        else:
            lines = ["\n[Current Pending Storylines]"]
            for sl in pending_storylines:
                lines.append(
                    f"- [{sl.get('importance', 'medium')}] {sl.get('description', '')}"
                )
            pending_context = "\n".join(lines)

    # Build established facts context
    facts_context = ""
    if established_facts:
        if language == "zh":
            lines = ["\n【当前已建立的世界事实】"]
            for f in established_facts:
                cat = {"location": "地点", "role": "角色", "situation": "事务"}.get(
                    f.get("category", ""), "事实"
                )
                lines.append(f"- 【{cat}】{f.get('subject', '')}：{f.get('fact', '')}")
            facts_context = "\n".join(lines)
        else:
            lines = ["\n[Current Established Facts]"]
            for f in established_facts:
                cat = {
                    "location": "Location",
                    "role": "Role",
                    "situation": "Situation",
                }.get(f.get("category", ""), "Fact")
                lines.append(f"- [{cat}] {f.get('subject', '')}: {f.get('fact', '')}")
            facts_context = "\n".join(lines)

    # Build character habits context
    habits_context = ""
    if character_habits:
        if language == "zh":
            lines = ["\n【当前已记录的人物习惯】"]
            for h in character_habits:
                lines.append(
                    f"- {h.get('character', '')}：{h.get('habit', '')}（{h.get('category', '')}，{h.get('strength', 'moderate')}）"
                )
            habits_context = "\n".join(lines)
        else:
            lines = ["\n[Current Character Habits]"]
            for h in character_habits:
                lines.append(
                    f"- {h.get('character', '')}: {h.get('habit', '')} ({h.get('category', '')}, {h.get('strength', 'moderate')})"
                )
            habits_context = "\n".join(lines)

    if language == "zh":
        return f"""请将以下故事压缩为500字以内的摘要，判断事件是否已完结，评估剧情线状态，并提取伏笔种子。

故事原文：
{story}

玩家的选择："{choice}"{pending_context}{facts_context}{habits_context}

【输出要求 - 必须返回JSON格式】
{{
  "summary": "压缩后的500字摘要，第三人称视角，保留核心人物、关键事件、人物决定和重要对话内容",
  "event_concluded": true,
  "storyline_updates": [
    {{
      "action": "new",
      "description": "本轮产生的新的重要剧情线（尚未解决的事件）",
      "importance": "high或medium",
      "related_characters": ["涉及的人物名"]
    }},
    {{
      "action": "resolved",
      "description": "之前的某个剧情线已解决"
    }},
    {{
      "action": "continues",
      "description": "之前的某个剧情线继续发展中"
    }}
  ],
  "fact_updates": [
    {{
      "action": "new",
      "subject": "主体名（人物/地点/组织）",
      "fact": "关于该主体的具体事实",
      "category": "role/location/situation"
    }},
    {{
      "action": "update",
      "subject": "已有主体名",
      "fact": "更新后的事实",
      "category": "role/location/situation"
    }},
    {{
      "action": "remove",
      "subject": "不再有效的主体名"
    }}
  ],
  "foreshadowing_seeds": [
    {{
      "description": "伏笔内容描述（一句话概括，包含具体的人/物/事）",
      "original_context": "简述伏笔发生时的场景（30字内）",
      "seed_type": "mystery/relationship/warning/opportunity/consequence/character_return",
      "related_characters": ["涉及的人物名"],
      "obfuscation_level": 0.5,
      "narrative_weight": "minor/supporting/major",
      "recycle_method": "revelation/confirmation/ironic_twist/escalation/echo"
    }}
  ],
  "habit_updates": [
    {{
      "action": "new",
      "character": "角色名",
      "habit": "习惯描述（如：每天早起跑步、说话前习惯性摸下巴、遇到压力时会独自喝酒）",
      "category": "behavioral/speech/emotional/social/lifestyle",
      "strength": "strong/moderate/emerging",
      "origin": "习惯来源简述（如：从小养成、失恋后开始、工作压力所致）"
    }},
    {{
      "action": "strengthen",
      "character": "角色名",
      "habit": "已有的习惯描述"
    }},
    {{
      "action": "weaken",
      "character": "角色名",
      "habit": "已有的习惯描述",
      "reason": "习惯减弱的原因"
    }},
    {{
      "action": "remove",
      "character": "角色名",
      "habit": "已有的习惯描述",
      "reason": "习惯消失的原因"
    }},
    {{
      "action": "change",
      "character": "角色名",
      "old_habit": "原习惯描述",
      "new_habit": "新习惯描述",
      "reason": "习惯变化的原因",
      "category": "behavioral/speech/emotional/social/lifestyle",
      "strength": "strong/moderate/emerging"
    }}
  ],
  "location_updates": [
    {{
      "character": "人物名",
      "action": "move",
      "from": "原位置（城市或区域）",
      "to": "新位置（城市或区域）",
      "reason": "移动原因（出差/搬家/旅行/回老家等）",
      "mode": "resident/visiting/traveling"
    }},
    {{
      "character": "人物名",
      "action": "confirm",
      "location": "确认的位置",
      "reason": "故事中明确提及某人在某地"
    }}
  ],
  "career_updates": [
    {{
      "character": "人物名",
      "action": "new/promote/transfer/quit/fired",
      "new_role": "新职位/角色",
      "employer": "雇主/公司名",
      "level": "intern/junior/mid/senior/lead/executive"
    }}
  ],
  "commitment_updates": [
    {{
      "action": "new",
      "description": "承诺/约定的具体内容",
      "parties": ["涉及的人物名"],
      "deadline_week": -1,
      "importance": "critical/normal/minor"
    }},
    {{
      "action": "fulfilled/broken/expired",
      "description": "已有承诺的描述（需与之前记录匹配）"
    }}
  ],
  "causal_updates": [
    {{
      "action": "new",
      "cause": "触发事件描述（如：得罪了部门主管）",
      "expected_consequence": "预期后果（如：可能影响晋升评审）",
      "characters": ["涉及的人物名"]
    }},
    {{
      "action": "resolved",
      "cause": "已有因果链的原因描述（需与之前记录匹配）",
      "resolution": "实际结果描述"
    }}
  ]
}}

【事件完结判断规则 - event_concluded】
- **true**: 本轮事件已达到自然结局，主角的选择导致了明确的结果，没有重大悬念或未解决的危机
- **false**: 本轮事件仍在发展中，存在以下情况之一：
  - 冲突尚未解决（如争吵后未和解、危机未解除）
  - 重要决定的后果尚未呈现（如刚做出重大选择，结果待定）
  - 事件被中断或推迟（如谈判被打断、计划被延迟）
  - 故事留下了明显的悬念（如检查结果还没出、等待回复）
  - 人物关系发生了重大变化但未达到新的平衡
判断核心：读完故事后，读者是否会自然地想"然后呢？"。如果会，则 event_concluded 为 false。

【剧情线评估规则】
1. 如果本轮故事中有重要事件尚未解决（如冲突未解决、重要决定待续、人物关系变化未完结），添加 action:"new"
2. 如果本轮故事解决了之前某个未完结的剧情线，添加 action:"resolved"
3. 如果本轮故事延续了之前某个剧情线，添加 action:"continues"
4. importance: "high"表示影响主角人生走向的重大事件，"medium"表示值得关注但不紧迫的事件
5. 如果本轮是普通日常事件，storyline_updates 可以为空数组

【世界事实提取规则】
1. 提取故事中明确建立的事实：人物的角色/职业/身份、地理位置、正在进行的事务
2. category 分类："role"（人物角色/职业/身份）、"location"（人物所在位置）、"situation"（正在进行的事务/状态）
3. 如果某个主体的事实发生了变化（如换了工作、搬了家、职责变化），使用 action:"update"
4. 如果某个事实不再有效（如人物离开、事务结束），使用 action:"remove"
5. 只提取重要的、会影响后续故事的事实，不要提取细枝末节

【伏笔种子提取规则 - foreshadowing_seeds】
从故事中提取"埋下了种子但没有完全展开"的元素，它们可能在未来回响。学习经典文学中的伏笔艺术：

类型说明与范例：
- **mystery** 神秘元素：意味深长的话、神秘物件、未解之谜。如《红楼梦》中"假作真时真亦假"的谶语
- **relationship** 关系暗线：暗流涌动的情感、未说出口的秘密、隐藏的动机。如某人异常的一瞬犹豫
- **warning** 警告预兆：微妙的警示、不祥的细节、无意间的忠告。如"老人说过这条路晚上不能走"
- **opportunity** 潜在机会：被忽略的线索、潜在的合作者、未探索的方向。如某人随手给的一张名片
- **consequence** 行为种子：可能产生连锁反应的决定、得罪了某人、做了承诺。如《冰与火之歌》中"凤凰磐石"的叙事种子
- **character_return** 人物线索：离开时留下的悬念、新人物的神秘背景。如《基督山伯爵》中消失的水手

字段说明：
- obfuscation_level (0.0-1.0): 隐蔽度。
  0.0-0.3=明显线索（读者容易关注），0.4-0.6=中等隐蔽（看似随意的细节），0.7-1.0=极度隐蔽（重读时才能发现）
- narrative_weight: 叙事权重。
  minor=点缀性回响，supporting=支线级别，major=影响主线走向
- recycle_method: 回收方式。
  revelation=揭露秘密，confirmation=验证前兆，ironic_twist=讽刺性反转，escalation=事态升级，echo=微妙呼应

注意：
- 伏笔与剧情线不同：剧情线是"必须跟进的主线/支线"，伏笔是"可能在未来回响的微妙线索"
- 不是每个故事都有伏笔，只提取真正有回响潜力的元素
- 每次最多提取 1-2 个伏笔种子，普通日常故事可以为空数组
- 好的伏笔应该满足："埋线时看似无意，回收时恰如其分"

【人物习惯提取规则 - habit_updates】
识别故事中角色展现出的行为习惯、言语习惯、情绪模式、社交风格或生活方式，以及已有习惯的变化。

1. category 分类：
   - behavioral：行为习惯（如每天早起、做事前先列计划、紧张时咬指甲）
   - speech：言语习惯（如说话爱用成语、口头禅、总是先否定再肯定）
   - emotional：情绪模式（如容易共情、遇到挫折先冷静、爱哭）
   - social：社交习惯（如主动帮助陌生人、不喜欢大型聚会、总是做调解者）
   - lifestyle：生活方式（如每天跑步、喜欢在深夜看书、烹饪解压）
2. strength 程度：
   - strong：根深蒂固的习惯（长期行为，很难改变）
   - moderate：明显的习惯（多次出现，已成模式）
   - emerging：初现的习惯（刚形成，可能会发展也可能消退）
3. action 类型：
   - new：故事中首次展现的新习惯
   - strengthen：已有习惯在故事中被强化（如更频繁地出现）
   - weaken：已有习惯因事件而减弱
   - remove：习惯因重大事件而消失（如戒烟成功）
   - change：习惯因事件而转变为另一个习惯（如从"独自喝闷酒"变为"和朋友倾诉"）
4. 只记录有叙事价值的习惯，不要记录过于琐碎的细节
5. 主角和NPC的习惯都可以记录
6. 如果故事中没有展现值得记录的习惯，habit_updates 可以为空数组

【位置变动提取规则 - location_updates】
识别故事中人物的地理位置变化或确认。
1. action 类型：
   - move：人物从一个地点移动到另一个地点（出差、搬家、旅行、回老家等）
   - confirm：故事中明确提到某人在某个地点（无移动，但确认了位置信息）
2. mode 类型（仅 move 时填写）：
   - resident：长期居住（搬家、定居）
   - visiting：短期拜访或出差
   - traveling：旅行途中
3. 只记录明确提到的位置变化，不要推测
4. 如果没有位置变动，location_updates 为空数组

【职业变动提取规则 - career_updates】
识别故事中人物的职业、职位、工作状态变化。
1. action 类型：
   - new：首次提到某人的职业/工作
   - promote：升职
   - transfer：调岗/转部门
   - quit：辞职
   - fired：被解雇
2. level 职级（尽量判断）：intern（实习）、junior（初级）、mid（中级）、senior（高级）、lead（主管）、executive（高管）
3. 只记录明确提到的职业变化，不要推测
4. 如果没有职业变动，career_updates 为空数组

【承诺约定提取规则 - commitment_updates】
识别故事中人物做出的承诺、约定、债务，以及已有承诺的兑现/违背。
1. action 类型：
   - new：新的承诺或约定（如"答应请吃饭"、"承诺帮忙搬家"、"借了一笔钱"）
   - fulfilled：已有承诺被兑现（★重要：如果故事中人物完成了之前的承诺，必须标记为 fulfilled）
   - broken：已有承诺被违背（★重要：如果人物明确拒绝或无法完成承诺，标记为 broken）
   - expired：已有承诺过期未兑现（仅当承诺超时且无任何处理时才使用）
2. importance 重要性：
   - critical：影响重要人物关系或人生走向的承诺
   - normal：一般性承诺
   - minor：随口说的小事
3. deadline_week：如果承诺有明确时限，填写周数；无明确时限填 -1
4. ★关键判断准则：
   - 如果故事中人物实际完成了之前的承诺（如"参加了约定的仪式"、"按约定交付了物品"），必须提取为 fulfilled
   - 如果承诺在故事中被处理（兑现、违背、或协商变更），不要标记为 expired
   - expired 仅用于：承诺超时且故事中完全未提及处理的情况
5. 如果没有新的承诺或承诺变动，commitment_updates 为空数组

【因果链提取规则 - causal_updates】
识别故事中可能产生后续连锁反应的行为或决定，以及已有因果链的解决。
1. action 类型：
   - new：新的因果关系（某个行为可能导致后续后果，如"拒绝了经理的要求"→"可能影响绩效"）
   - resolved：之前的因果链已经产生了结果或被化解
2. 与伏笔(foreshadowing)的区别：因果链是"有明确预期后果的行为"，伏笔是"潜在但不确定的叙事线索"
3. 只记录有叙事价值的因果关系，不要记录每个小决定
4. 如果没有新的因果链或因果变动，causal_updates 为空数组

7. 只返回JSON，不要其他文本"""
    else:
        return f"""Compress the following story into a summary of 500 characters or less, judge if the event is concluded, evaluate storyline status, and extract foreshadowing seeds.

Original story:
{story}

Player's choice: "{choice}"{pending_context}{facts_context}{habits_context}

[Output - MUST return JSON format]
{{
  "summary": "Compressed 500-char summary in third person, preserving core characters, key events, decisions and important dialogue",
  "event_concluded": true,
  "storyline_updates": [
    {{
      "action": "new",
      "description": "New important storyline from this round (unresolved event)",
      "importance": "high or medium",
      "related_characters": ["character names involved"]
    }},
    {{
      "action": "resolved",
      "description": "A previous storyline that got resolved"
    }},
    {{
      "action": "continues",
      "description": "A previous storyline that continues developing"
    }}
  ],
  "fact_updates": [
    {{
      "action": "new",
      "subject": "Subject name (character/location/org)",
      "fact": "Specific fact about this subject",
      "category": "role/location/situation"
    }},
    {{
      "action": "update",
      "subject": "Existing subject name",
      "fact": "Updated fact",
      "category": "role/location/situation"
    }},
    {{
      "action": "remove",
      "subject": "Subject name no longer valid"
    }}
  ],
  "foreshadowing_seeds": [
    {{
      "description": "One-sentence description of the foreshadowing element (include specific person/object/event)",
      "original_context": "Brief scene context when it was planted (30 chars max)",
      "seed_type": "mystery/relationship/warning/opportunity/consequence/character_return",
      "related_characters": ["character names involved"],
      "obfuscation_level": 0.5,
      "narrative_weight": "minor/supporting/major",
      "recycle_method": "revelation/confirmation/ironic_twist/escalation/echo"
    }}
  ],
  "habit_updates": [
    {{
      "action": "new",
      "character": "character name",
      "habit": "habit description (e.g., always jogs in the morning, strokes chin before speaking, drinks alone under stress)",
      "category": "behavioral/speech/emotional/social/lifestyle",
      "strength": "strong/moderate/emerging",
      "origin": "brief origin of habit (e.g., childhood habit, started after breakup, work stress)"
    }},
    {{
      "action": "strengthen",
      "character": "character name",
      "habit": "existing habit description"
    }},
    {{
      "action": "weaken",
      "character": "character name",
      "habit": "existing habit description",
      "reason": "why the habit weakened"
    }},
    {{
      "action": "remove",
      "character": "character name",
      "habit": "existing habit description",
      "reason": "why the habit disappeared"
    }},
    {{
      "action": "change",
      "character": "character name",
      "old_habit": "old habit description",
      "new_habit": "new habit description",
      "reason": "why the habit changed",
      "category": "behavioral/speech/emotional/social/lifestyle",
      "strength": "strong/moderate/emerging"
    }}
  ],
  "location_updates": [
    {{
      "character": "character name",
      "action": "move",
      "from": "previous location (city or region)",
      "to": "new location (city or region)",
      "reason": "reason for move (business trip/relocation/travel/visiting hometown etc.)",
      "mode": "resident/visiting/traveling"
    }},
    {{
      "character": "character name",
      "action": "confirm",
      "location": "confirmed location",
      "reason": "story explicitly mentions someone being at a location"
    }}
  ],
  "career_updates": [
    {{
      "character": "character name",
      "action": "new/promote/transfer/quit/fired",
      "new_role": "new position/role",
      "employer": "employer/company name",
      "level": "intern/junior/mid/senior/lead/executive"
    }}
  ],
  "commitment_updates": [
    {{
      "action": "new",
      "description": "specific content of commitment/agreement",
      "parties": ["character names involved"],
      "deadline_week": -1,
      "importance": "critical/normal/minor"
    }},
    {{
      "action": "fulfilled/broken/expired",
      "description": "description of existing commitment (must match previous record)"
    }}
  ],
  "causal_updates": [
    {{
      "action": "new",
      "cause": "triggering event description (e.g., offended the department manager)",
      "expected_consequence": "expected consequence (e.g., may affect promotion review)",
      "characters": ["character names involved"]
    }},
    {{
      "action": "resolved",
      "cause": "cause description of existing causal chain (must match previous record)",
      "resolution": "actual outcome description"
    }}
  ]
}}

[Event Conclusion Rules - event_concluded]
- **true**: The event reached a natural resolution. The player's choice led to a clear outcome with no major suspense or unresolved crisis.
- **false**: The event is still developing, with one of these situations:
  - Conflict unresolved (e.g., argument not reconciled, crisis not averted)
  - Consequences of an important decision not yet revealed
  - Event interrupted or postponed
  - Story left with obvious suspense (e.g., awaiting results, waiting for a reply)
  - Major relationship change hasn't reached a new equilibrium
Core judgment: After reading the story, would the reader naturally think "What happens next?" If yes, event_concluded is false.

[Storyline Evaluation Rules]
1. If this round has important unresolved events (conflicts, pending decisions, relationship changes), add action:"new"
2. If this round resolved a previous pending storyline, add action:"resolved"
3. If this round continued a previous storyline, add action:"continues"
4. importance: "high" for life-changing events, "medium" for noteworthy but not urgent events
5. If this round is an ordinary daily event, storyline_updates can be an empty array

[World Fact Extraction Rules]
1. Extract clearly established facts: character roles/jobs/identities, geographic locations, ongoing affairs
2. category: "role" (character role/job/identity), "location" (where someone is), "situation" (ongoing affairs/status)
3. If a subject's fact changed (job change, relocation, role change), use action:"update"
4. If a fact is no longer valid (character left, affair ended), use action:"remove"
5. Only extract important facts that affect future stories, not trivial details

[Foreshadowing Seed Extraction Rules - foreshadowing_seeds]
Extract "seeds planted but not fully explored" that can echo back much later. Learn from the art of foreshadowing in classic literature:

Type Descriptions & Examples:
- **mystery**: Mysterious elements (cryptic remark, mysterious object, unsolved riddle). Like prophecies in "A Dream of Red Mansions"
- **relationship**: Relationship undercurrents (hidden feelings, unspoken secrets, concealed motives). Like a character's brief but telling hesitation
- **warning**: Warnings or omens (subtle warnings, ominous details, casual advice). Like "the old man said never walk this road at night"
- **opportunity**: Potential opportunities (overlooked clues, potential allies, unexplored directions). Like a business card casually given
- **consequence**: Action seeds (chain-reaction decisions, offending someone, making promises). Like narrative seeds in "A Song of Ice and Fire"
- **character_return**: Character threads (suspense when someone leaves, new character's mysterious background). Like the vanished sailor in "The Count of Monte Cristo"

Field Descriptions:
- obfuscation_level (0.0-1.0): Concealment level.
  0.0-0.3=obvious clue (reader easily notices), 0.4-0.6=moderate concealment (seemingly casual detail), 0.7-1.0=deeply hidden (only noticed on re-read)
- narrative_weight: Narrative importance.
  minor=decorative echo, supporting=subplot level, major=affects main plot direction
- recycle_method: Recovery method.
  revelation=reveal a secret, confirmation=validate a premonition, ironic_twist=ironic reversal, escalation=situation escalates, echo=subtle resonance

Note:
- Foreshadowing differs from storylines: storylines are "active plots to follow", foreshadowing is "subtle threads that might echo in the future"
- Not every story has foreshadowing, only extract elements with genuine echo potential
- Extract at most 1-2 seeds per story, ordinary daily stories can have an empty array
- Good foreshadowing satisfies: "seems casual when planted, feels perfect when recovered"

[Character Habit Extraction Rules - habit_updates]
Identify behavioral habits, speech patterns, emotional patterns, social styles, or lifestyle habits displayed by characters in the story, as well as changes to existing habits.

1. category:
   - behavioral: Action habits (e.g., always makes lists before starting, bites nails when nervous)
   - speech: Speech patterns (e.g., loves using idioms, has catchphrases, always denies before affirming)
   - emotional: Emotional patterns (e.g., easily empathetic, stays calm under pressure, tendency to cry)
   - social: Social habits (e.g., helps strangers proactively, avoids large gatherings, always mediates)
   - lifestyle: Lifestyle habits (e.g., daily jogging, late-night reading, stress-cooking)
2. strength:
   - strong: Deep-rooted habit (long-term behavior, hard to change)
   - moderate: Notable habit (appeared multiple times, established pattern)
   - emerging: Emerging habit (just forming, may develop or fade)
3. action types:
   - new: First-time display of a new habit in the story
   - strengthen: Existing habit reinforced in the story
   - weaken: Existing habit weakened due to events
   - remove: Habit disappeared due to major event (e.g., successfully quit smoking)
   - change: Habit transformed into another habit (e.g., from 'drinking alone' to 'confiding in friends')
4. Only record narratively valuable habits, not trivial details
5. Both protagonist and NPC habits can be recorded
6. If no notable habits are displayed, habit_updates can be an empty array

[Location Update Extraction Rules - location_updates]
Identify geographic location changes or confirmations of characters in the story.
1. action types:
   - move: Character moved from one place to another (business trip, relocation, travel, visiting hometown etc.)
   - confirm: Story explicitly mentions someone being at a specific location (no movement, but position confirmed)
2. mode types (only for move):
   - resident: Long-term residence (relocation, settling down)
   - visiting: Short-term visit or business trip
   - traveling: In transit/traveling
3. Only record explicitly mentioned location changes, do not speculate
4. If no location changes, location_updates should be an empty array

[Career Update Extraction Rules - career_updates]
Identify career, position, or employment status changes of characters.
1. action types:
   - new: First mention of someone's job/career
   - promote: Promotion
   - transfer: Department/role transfer
   - quit: Resignation
   - fired: Termination
2. level (estimate when possible): intern, junior, mid, senior, lead, executive
3. Only record explicitly mentioned career changes, do not speculate
4. If no career changes, career_updates should be an empty array

[Commitment Extraction Rules - commitment_updates]
Identify promises, agreements, or debts made by characters, and fulfillment/violation of existing commitments.
1. action types:
   - new: New commitment or agreement (e.g., "promised to treat to dinner", "agreed to help move", "borrowed money")
   - fulfilled: Existing commitment was fulfilled
   - broken: Existing commitment was broken
   - expired: Existing commitment expired without being fulfilled
2. importance levels:
   - critical: Commitments affecting key relationships or life direction
   - normal: Regular commitments
   - minor: Casually mentioned small things
3. deadline_week: If commitment has explicit deadline, fill in week number; otherwise -1
4. If no new or changed commitments, commitment_updates should be an empty array

[Causal Chain Extraction Rules - causal_updates]
Identify actions or decisions that may cause chain reactions, and resolution of existing causal chains.
1. action types:
   - new: New causal relationship (an action may lead to consequences, e.g., "refused manager's request" -> "may affect performance review")
   - resolved: Previous causal chain has produced results or been resolved
2. Difference from foreshadowing: Causal chains are "actions with clearly expected consequences"; foreshadowing is "potential but uncertain narrative threads"
3. Only record narratively valuable causal relationships, not every small decision
4. If no new or changed causal chains, causal_updates should be an empty array

7. Return ONLY JSON, no other text"""


def get_narrative_compression_prompt(
    story: str,
    choice: str,
    language: str,
    pending_storylines: Optional[list] = None,
) -> str:
    """
    Generate prompt for narrative compression only:
    summary + event_concluded + storyline_updates.

    This is the lightweight half of the original get_story_compression_prompt,
    designed to run in parallel with get_world_extraction_prompt.
    """
    # Build pending storylines context
    pending_context = ""
    if pending_storylines:
        if language == "zh":
            lines = ["\n【当前未完结的剧情线】"]
            for sl in pending_storylines:
                lines.append(
                    f"- [{sl.get('importance', 'medium')}] {sl.get('description', '')}"
                )
            pending_context = "\n".join(lines)
        else:
            lines = ["\n[Current Pending Storylines]"]
            for sl in pending_storylines:
                lines.append(
                    f"- [{sl.get('importance', 'medium')}] {sl.get('description', '')}"
                )
            pending_context = "\n".join(lines)

    if language == "zh":
        return f"""请将以下故事压缩为500字以内的摘要，判断事件是否已完结，并评估剧情线状态。

故事原文：
{story}

玩家的选择："{choice}"{pending_context}

【输出要求 - 必须返回JSON格式】
{{
  "summary": "压缩后的500字摘要，第三人称视角，保留核心人物、关键事件、人物决定和重要对话内容",
  "event_concluded": true,
  "storyline_updates": [
    {{
      "action": "new",
      "description": "本轮产生的新的重要剧情线（尚未解决的事件）",
      "importance": "high或medium",
      "related_characters": ["涉及的人物名"]
    }},
    {{
      "action": "resolved",
      "description": "之前的某个剧情线已解决"
    }},
    {{
      "action": "continues",
      "description": "之前的某个剧情线继续发展中"
    }}
  ]
}}

【事件完结判断规则 - event_concluded】
- **true**: 本轮事件已达到自然结局，主角的选择导致了明确的结果，没有重大悬念或未解决的危机
- **false**: 本轮事件仍在发展中，存在以下情况之一：
  - 冲突尚未解决（如争吵后未和解、危机未解除）
  - 重要决定的后果尚未呈现（如刚做出重大选择，结果待定）
  - 事件被中断或推迟（如谈判被打断、计划被延迟）
  - 故事留下了明显的悬念（如检查结果还没出、等待回复）
  - 人物关系发生了重大变化但未达到新的平衡
判断核心：读完故事后，读者是否会自然地想"然后呢？"。如果会，则 event_concluded 为 false。

【剧情线评估规则】
1. 如果本轮故事中有重要事件尚未解决（如冲突未解决、重要决定待续、人物关系变化未完结），添加 action:"new"
2. 如果本轮故事解决了之前某个未完结的剧情线，添加 action:"resolved"
3. 如果本轮故事延续了之前某个剧情线，添加 action:"continues"
4. importance: "high"表示影响主角人生走向的重大事件，"medium"表示值得关注但不紧迫的事件
5. 如果本轮是普通日常事件，storyline_updates 可以为空数组

只返回JSON，不要其他文本"""
    else:
        return f"""Compress the following story into a summary of 500 characters or less, judge if the event is concluded, and evaluate storyline status.

Original story:
{story}

Player's choice: "{choice}"{pending_context}

[Output - MUST return JSON format]
{{
  "summary": "Compressed 500-char summary in third person, preserving core characters, key events, decisions and important dialogue",
  "event_concluded": true,
  "storyline_updates": [
    {{
      "action": "new",
      "description": "New important storyline from this round (unresolved event)",
      "importance": "high or medium",
      "related_characters": ["character names involved"]
    }},
    {{
      "action": "resolved",
      "description": "A previous storyline that got resolved"
    }},
    {{
      "action": "continues",
      "description": "A previous storyline that continues developing"
    }}
  ]
}}

[Event Conclusion Rules - event_concluded]
- **true**: The event reached a natural resolution with no major suspense or unresolved crisis.
- **false**: The event is still developing (conflict unresolved, consequences not yet revealed, event interrupted, obvious suspense, or major relationship change hasn't stabilized).
Core judgment: Would the reader naturally think "What happens next?" If yes, event_concluded is false.

[Storyline Evaluation Rules]
1. If this round has important unresolved events, add action:"new"
2. If this round resolved a previous pending storyline, add action:"resolved"
3. If this round continued a previous storyline, add action:"continues"
4. importance: "high" for life-changing events, "medium" for noteworthy but not urgent events
5. If ordinary daily event, storyline_updates can be an empty array

Return ONLY JSON, no other text"""


def get_weekly_summary_prompt(
    rounds: list,
    character_settings: Optional[Dict[str, Any]],
    language: str,
    game_date_info: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate prompt for weekly summary generation.

    Args:
        rounds: List of round records [{"summary": ..., "choice": ..., "effects": ...}]
        character_settings: Character background settings
        language: Language code ('zh' or 'en')

    Returns:
        Prompt for weekly summary generation
    """
    # Format rounds into readable text
    round_names_zh = ["周一", "周中", "周末"]
    round_names_en = ["Monday", "Midweek", "Weekend"]

    rounds_text = ""
    for r in rounds:
        round_idx = r.get("round", 0)
        continuation = r.get("story_continuation", "")
        if language == "zh":
            round_name = (
                round_names_zh[round_idx] if round_idx < 3 else f"第{round_idx+1}轮"
            )
            rounds_text += f"""\n【{round_name}】
经历：{r.get('summary', '')}
选择：{r.get('choice', '')}
效果：{_format_effects(r.get('effects', {}), language)}
"""
            if continuation:
                cont_brief = (
                    continuation[:200] + "..."
                    if len(continuation) > 200
                    else continuation
                )
                rounds_text += f"后续发展：{cont_brief}\n"
        else:
            round_name = (
                round_names_en[round_idx] if round_idx < 3 else f"Round {round_idx+1}"
            )
            rounds_text += f"""\n[{round_name}]
Experience: {r.get('summary', '')}
Choice: {r.get('choice', '')}
Effects: {_format_effects(r.get('effects', {}), language)}
"""
            if continuation:
                cont_brief = (
                    continuation[:200] + "..."
                    if len(continuation) > 200
                    else continuation
                )
                rounds_text += f"Follow-up: {cont_brief}\n"

    # Get character name if available
    char_name = ""
    if character_settings and "name" in character_settings:
        char_name = character_settings["name"]

    time_context = _build_time_context(game_date_info, language)
    time_guard = _build_weekly_summary_time_guard(game_date_info, language)

    if language == "zh":
        prompt = f"""你是人生模拟游戏的周总结生成器。{time_context}
{time_guard}

本周经历：{rounds_text}

请生成：
1. 周总结文本（200字，描述这一周的整体经历和成长，包含时间信息）
2. 根据本周的决策模式，给出额外属性加成（可选）

【输出JSON格式】
{{
    "summary": "本周总结文本...",
    "bonus_effects": {{"energy": 0, "mood": 0, "knowledge": 0, "wealth": 0}}
}}

【加成规则】
- 如果3次选择都偏向学习/工作 -> knowledge +5
- 如果3次选择都偏向休闲/享乐 -> mood +5, energy +5
- 如果选择冒险/挑战 -> 随机+10/-10
- 如果选择都关注人际关系 -> 无直接加成（关系已在每轮结算）
- 普通混合选择 -> 无额外加成（全部为0）

注意：只返回有效的JSON，不要任何其他文本。"""
    else:
        prompt = f"""You are a weekly summary generator for a life simulation game.{time_context}
{time_guard}

This Week's Experience:{rounds_text}

Please generate:
1. Weekly summary text (200 words, describing overall experience and growth, including time context)
2. Based on decision patterns, provide bonus attribute effects (optional)

[Output JSON Format]
{{
    "summary": "Weekly summary text...",
    "bonus_effects": {{"energy": 0, "mood": 0, "knowledge": 0, "wealth": 0}}
}}

[Bonus Rules]
- If all 3 choices lean toward learning/work -> knowledge +5
- If all 3 choices lean toward leisure/enjoyment -> mood +5, energy +5  
- If choices involve risk/challenge -> random +10/-10
- If choices focus on relationships -> no direct bonus (relationships settled per round)
- Mixed choices -> no extra bonus (all zeros)

Note: Return ONLY valid JSON, no other text."""

    return prompt


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
        "en": {
            "energy": "Energy",
            "mood": "Mood",
            "knowledge": "Knowledge",
            "wealth": "Wealth",
        },
    }

    for key in ["energy", "mood", "knowledge", "wealth"]:
        val = effects.get(key, 0)
        if val != 0:
            label = labels.get(language, labels["en"]).get(key, key)
            sign = "+" if val > 0 else ""
            parts.append(f"{label}{sign}{val}")

    return "、".join(parts) if parts else ("无" if language == "zh" else "None")
