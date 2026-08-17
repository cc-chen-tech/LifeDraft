"""
World state extraction and ending prompts.

Contains:
- get_ending_prompt: Ending narrative generation
- get_world_extraction_prompt: World state extraction from stories
"""

import json
from typing import Any, Dict, List, Optional, Sequence

from src.utils.financial_narrative import sanitize_authoritative_fact_records

_DAILY_WORLD_PATCH_EXAMPLE = (
    '{"fact_updates": [], "foreshadowing_seeds": [], "habit_updates": [], '
    '"location_updates": [], "career_updates": [], "commitment_updates": [], '
    '"causal_updates": []}'
)


def _daily_option_patches_example(options: Sequence[Any]) -> str:
    return "{}" if not options else f'{{"0": {_DAILY_WORLD_PATCH_EXAMPLE}}}'


def get_daily_world_projection_prompt(
    story: str,
    options: Sequence[Any],
    language: str,
    tracked_state: Optional[Dict[str, Any]] = None,
) -> str:
    """Request a typed story patch and one conditional patch per daily option."""
    options_json = json.dumps(list(options), ensure_ascii=False, default=str)
    tracked_json = json.dumps(tracked_state or {}, ensure_ascii=False, default=str)
    option_patches_example = _daily_option_patches_example(options)
    if language == "zh":
        return f"""从已接受的每日故事中提取派生世界变化。故事正文已发生的变化放入 story_patch；每个选项只在该选项被玩家选择后才发生的变化放入 option_patches 对应索引。不得猜测，也不得把选择后的变化写入 story_patch。

故事原文：
{story}

选项（JSON 数组，索引从 0 开始）：
{options_json}

已跟踪的派生状态（仅作识别参考）：
{tracked_json}

只返回 JSON：
{{
  "schema_version": 1,
  "story_patch": {_DAILY_WORLD_PATCH_EXAMPLE},
  "option_patches": {option_patches_example}
}}

每个字段必须是数组；option_patches 不得包含不存在的选项索引；无变化时使用空数组。"""
    return f"""Extract derived world changes from this accepted daily story. Put changes already true in story_patch. Put changes that become true only if the player chooses an option in option_patches at that option's zero-based index. Do not infer facts or place option outcomes in story_patch.

Story:
{story}

Options (JSON array, zero-based indexes):
{options_json}

Tracked derived state (recognition reference only):
{tracked_json}

Return JSON only:
{{
  "schema_version": 1,
  "story_patch": {_DAILY_WORLD_PATCH_EXAMPLE},
  "option_patches": {option_patches_example}
}}

Every category must be an array. Do not include unknown option indexes. Use empty arrays for no change."""


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


def get_world_extraction_prompt(
    story: str,
    choice: str,
    language: str,
    established_facts: Optional[list] = None,
    character_habits: Optional[list] = None,
) -> str:
    """
    Generate prompt for world state extraction only:
    fact_updates, foreshadowing_seeds, habit_updates, location_updates,
    career_updates, commitment_updates, causal_updates.

    This is the detail-extraction half of the original get_story_compression_prompt,
    designed to run in parallel with get_narrative_compression_prompt.
    """
    # Build established facts context
    facts_context = ""
    safe_established_facts = sanitize_authoritative_fact_records(established_facts)
    if safe_established_facts:
        if language == "zh":
            lines = ["\n【当前已建立的世界事实】"]
            for f in safe_established_facts:
                cat = {"location": "地点", "role": "角色", "situation": "事务"}.get(
                    f.get("category", ""), "事实"
                )
                lines.append(f"- 【{cat}】{f.get('subject', '')}：{f.get('fact', '')}")
            facts_context = "\n".join(lines)
        else:
            lines = ["\n[Current Established Facts]"]
            for f in safe_established_facts:
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
        return f"""请从以下故事中提取世界状态变化：事实更新、伏笔种子、人物习惯、位置变动、职业变动、承诺约定、因果链。

故事原文：
{story}

玩家的选择："{choice}"{facts_context}{habits_context}

【输出要求 - 必须返回JSON格式】
{{
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
      "habit": "习惯描述",
      "category": "behavioral/speech/emotional/social/lifestyle",
      "strength": "strong/moderate/emerging",
      "origin": "习惯来源简述"
    }},
    {{
      "action": "strengthen/weaken/remove/change",
      "character": "角色名",
      "habit": "已有的习惯描述"
    }}
  ],
  "location_updates": [
    {{
      "character": "人物名",
      "action": "move/confirm",
      "from": "原位置",
      "to": "新位置",
      "reason": "移动原因",
      "mode": "resident/visiting/traveling"
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
      "action": "new/fulfilled/broken/expired",
      "description": "承诺/约定的具体内容",
      "parties": ["涉及的人物名"],
      "deadline_week": -1,
      "importance": "critical/normal/minor"
    }}
  ],
  "causal_updates": [
    {{
      "action": "new/resolved",
      "cause": "触发事件描述",
      "expected_consequence": "预期后果",
      "characters": ["涉及的人物名"]
    }}
  ]
}}

【提取规则】
- 世界事实：只提取重要的、会影响后续故事的事实，不要提取细枝末节
- 伏笔种子：每次最多1-2个，只提取有回响潜力的元素，普通日常可为空
- 人物习惯：只记录有叙事价值的习惯，主角和NPC均可
- 位置/职业/承诺/因果：只记录明确提到的变化，不要推测
- 各字段无变化时返回空数组

只返回JSON，不要其他文本"""
    else:
        return f"""Extract world state changes from the following story: fact updates, foreshadowing seeds, character habits, location changes, career changes, commitments, and causal chains.

Original story:
{story}

Player's choice: "{choice}"{facts_context}{habits_context}

[Output - MUST return JSON format]
{{
  "fact_updates": [
    {{
      "action": "new/update/remove",
      "subject": "Subject name (character/location/org)",
      "fact": "Specific fact about this subject",
      "category": "role/location/situation"
    }}
  ],
  "foreshadowing_seeds": [
    {{
      "description": "One-sentence description of the foreshadowing element",
      "original_context": "Brief scene context (30 chars max)",
      "seed_type": "mystery/relationship/warning/opportunity/consequence/character_return",
      "related_characters": ["character names"],
      "obfuscation_level": 0.5,
      "narrative_weight": "minor/supporting/major",
      "recycle_method": "revelation/confirmation/ironic_twist/escalation/echo"
    }}
  ],
  "habit_updates": [
    {{
      "action": "new/strengthen/weaken/remove/change",
      "character": "character name",
      "habit": "habit description",
      "category": "behavioral/speech/emotional/social/lifestyle",
      "strength": "strong/moderate/emerging"
    }}
  ],
  "location_updates": [
    {{
      "character": "character name",
      "action": "move/confirm",
      "from": "previous location",
      "to": "new location",
      "reason": "reason for move",
      "mode": "resident/visiting/traveling"
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
      "action": "new/fulfilled/broken/expired",
      "description": "specific content of commitment",
      "parties": ["character names"],
      "deadline_week": -1,
      "importance": "critical/normal/minor"
    }}
  ],
  "causal_updates": [
    {{
      "action": "new/resolved",
      "cause": "triggering event description",
      "expected_consequence": "expected consequence",
      "characters": ["character names"]
    }}
  ]
}}

[Extraction Rules]
- World facts: Only extract important facts affecting future stories, not trivial details
- Foreshadowing: At most 1-2 seeds per story, only elements with genuine echo potential
- Habits: Only record narratively valuable habits, both protagonist and NPCs
- Location/career/commitment/causal: Only record explicitly mentioned changes, do not speculate
- Return empty arrays for unchanged fields

Return ONLY JSON, no other text"""


def get_scheduled_commitment_extraction_prompt(
    story: str,
    current_week: int,
    current_round: int,
    language: str = "zh",
) -> str:
    """
    Generate prompt for extracting scheduled commitments with specific time points.

    从故事中提取带有具体时间点的承诺，用于创建预定事件。

    Args:
        story: 故事文本
        current_week: 当前周数
        current_round: 当前轮次
        language: 语言

    Returns:
        提示词字符串
    """
    if language == "zh":
        return f"""请从以下故事中识别角色做出的带有具体时间点的承诺/约定。

故事原文：
{story}

当前时间：第{current_week + 1}周，轮次{current_round}（0=周一, 1=周中, 2=周末）

【输出要求 - 必须返回JSON格式】
{{
  "scheduled_commitments": [
    {{
      "description": "承诺的具体内容（简明扼要）",
      "parties": ["涉及的人物名"],
      "time_reference": "原文中的时间表述",
      "scheduled_week": 计算后的周数（整数）,
      "scheduled_round": 计算后的轮次（0/1/2）,
      "importance": "critical/normal/minor",
      "event_hint": "事件应该包含的内容提示"
    }}
  ]
}}

【识别规则】
1. 只提取有明确时间点的承诺，例如：
   - "下周三我一定去" → scheduled_week=current_week+1, scheduled_round=0
   - "这周末见" → scheduled_week=current_week, scheduled_round=2
   - "三天后给你答复" → 根据当前轮次计算
   - "明天" → current_round+1
   - "下周一" → current_week+1, round=0
   - "下下周" → current_week+2
   - "下月初一" → current_week+4, round=0（一个月≈4周）
   - "下月中旬" → current_week+6, round=1
   - "下月底" → current_week+8, round=2
   - "两个月后" → current_week+8, round=0

2. 不提取模糊承诺：
   - "有机会"、"改天"、"以后"、"找时间" → 不提取
   - "尽快"、"尽早" → 不提取
   - "下次"（无具体时间）→ 不提取

3. 重要程度判断：
   - critical: 涉及重要人物、重大事件、明确约定的时间地点
   - normal: 普通的承诺和约定
   - minor: 随意的、不太重要的约定

4. 事件提示应描述：
   - 承诺兑现时应该发生什么
   - 涉及哪些人物
   - 可能的场景

【时间计算规则】
- 这周一/今天: week={current_week}, round=0
- 这周中: week={current_week}, round=1
- 这周末: week={current_week}, round=2
- 下周一: week={current_week+1}, round=0
- 下周中: week={current_week+1}, round=1
- 下周末: week={current_week+1}, round=2
- 下下周: week={current_week+2}
- 下月初/下月初一: week={current_week+4}, round=0（1个月≈4周）
- 下月中旬: week={current_week+6}, round=1
- 下月底/下月末: week={current_week+8}, round=2
- X个月后: week={current_week}+X*4, round=0
- 明天: round=(current_round+1)%3, week根据进位调整
- 后天: round=(current_round+2)%3, week根据进位调整
- X天后: 需要计算周数和轮次

如果没有识别到符合条件的承诺，返回空数组：
{{"scheduled_commitments": []}}

只返回JSON，不要其他文本。"""
    else:
        return f"""Extract commitments with specific time points from the following story.

Story:
{story}

Current time: Week {current_week}, Round {current_round} (0=Monday, 1=Midweek, 2=Weekend)

[Output - MUST return JSON format]
{{
  "scheduled_commitments": [
    {{
      "description": "Specific content of the commitment (concise)",
      "parties": ["character names involved"],
      "time_reference": "Original time expression in text",
      "scheduled_week": Calculated week number (integer),
      "scheduled_round": Calculated round number (0/1/2),
      "importance": "critical/normal/minor",
      "event_hint": "Hint for what the event should contain"
    }}
  ]
}}

[Recognition Rules]
1. Only extract commitments with specific time points:
   - "next Monday" → scheduled_week={current_week+1}, scheduled_round=0
   - "this weekend" → scheduled_week={current_week}, scheduled_round=2
   - "in three days" → calculate based on current round
   - "tomorrow" → current_round+1
   - "next week" → current_week+1

2. Do NOT extract vague commitments:
   - "sometime", "when I have time", "later" → skip
   - "soon", "as soon as possible" → skip
   - "next time" (without specific time) → skip

3. Importance levels:
   - critical: Important people, major events, specific time/place
   - normal: Regular commitments
   - minor: Casual, less important agreements

4. Event hint should describe:
   - What should happen when the commitment is fulfilled
   - Which characters are involved
   - Possible scenarios

[Time Calculation Rules]
- This Monday/today: week={current_week}, round=0
- This midweek: week={current_week}, round=1
- This weekend: week={current_week}, round=2
- Next Monday: week={current_week+1}, round=0
- Next midweek: week={current_week+1}, round=1
- Next weekend: week={current_week+1}, round=2
- Tomorrow: round=(current_round+1)%3, adjust week if needed
- Day after tomorrow: round=(current_round+2)%3, adjust week if needed
- In X days: Calculate week and round

If no qualifying commitments found, return empty array:
{{"scheduled_commitments": []}}

Return ONLY JSON, no other text."""
