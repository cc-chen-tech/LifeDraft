"""Decision processing and result generation."""

import logging
from typing import Any, Dict, List, Optional

from config.prompts import get_result_generation_prompt
from src.ai.generator import EventGenerator
from src.ai.system_prompts import get_system_prompt
from src.game.state import PlayerState

logger = logging.getLogger(__name__)


# ==================== 角色属性变化逻辑 ====================


def calculate_character_effects(
    effects: Dict[str, Any], player_state: PlayerState
) -> Dict[str, Dict[str, int]]:
    """
    根据事件效果计算对各角色的影响。

    Args:
        effects: 事件效果字典，可能包含 relationships 和 character_effects
        player_state: 当前玩家状态

    Returns:
        角色效果字典 {name: {affinity: x, trust: y, respect: z, mood: w}}
    """
    character_effects: dict[str, Any] = {}

    # 从 effects 中提取 relationships 变化
    relationships = effects.get("relationships", {})

    # 从 effects 中提取更详细的 character_effects（如果有）
    detailed_effects = effects.get("character_effects", {})

    # 处理 relationships 变化：将关系变化转为 affinity 变化
    for name, change in relationships.items():
        if name not in character_effects:
            character_effects[name] = {}
        character_effects[name]["affinity"] = change

        # 根据亲密度变化计算衔生影响
        if change > 0:
            # 正面互动带来信任和尊重的轻微提升
            character_effects[name]["trust"] = max(1, change // 3)
            character_effects[name]["respect"] = max(1, change // 4)
            character_effects[name]["mood"] = max(
                1, change // 2
            )  # 角色也会因正面互动而开心
        elif change < 0:
            # 负面互动带来信任和尊重的下降
            character_effects[name]["trust"] = min(-1, change // 2)
            character_effects[name]["respect"] = min(-1, change // 3)
            character_effects[name]["mood"] = min(
                -1, change
            )  # 角色也会因负面互动而情绪低落

    # 处理更详细的 character_effects（覆盖或补充）
    for name, char_effect in detailed_effects.items():
        if name not in character_effects:
            character_effects[name] = {}
        character_effects[name].update(char_effect)

    return character_effects


def apply_character_effects(
    player_state: PlayerState,
    character_effects: Dict[str, Dict[str, int]],
    interaction_summary: str = "",
) -> List[Dict[str, Any]]:
    """
    应用角色属性变化并检查触发事件。

    Args:
        player_state: 玩家状态
        character_effects: 角色效果字典
        interaction_summary: 互动简述

    Returns:
        触发的特殊事件列表
    """
    triggered_events = []

    for name, effects in character_effects.items():
        # 更新角色属性
        success = player_state.update_character_relationship(
            name=name,
            affinity_change=effects.get("affinity", 0),
            trust_change=effects.get("trust", 0),
            respect_change=effects.get("respect", 0),
            mood_change=effects.get("mood", 0),
            interaction_summary=interaction_summary,
        )

        if success:
            # 检查是否触发特殊事件
            character = player_state.get_character(name)
            if character:
                event_types = [
                    "deep_friendship",
                    "conflict",
                    "help_request",
                    "secret_sharing",
                    "betrayal_risk",
                ]
                for event_type in event_types:
                    if character.check_event_trigger(event_type):
                        triggered_events.append(
                            {
                                "name": name,
                                "event_type": event_type,
                                "character": character,
                                "affinity": character.affinity,
                                "trust": character.trust,
                            }
                        )

    return triggered_events


def get_character_interaction_context(
    player_state: PlayerState, involved_names: List[str]
) -> str:
    """
    获取涉及角色的上下文信息。

    Args:
        player_state: 玩家状态
        involved_names: 涉及的角色名字列表

    Returns:
        角色上下文字符串
    """
    if not involved_names:
        return ""

    context_parts = []
    for name in involved_names:
        character = player_state.get_character(name)
        if character:
            context_parts.append(character.to_context_string())

    if context_parts:
        return "【本次互动涉及的角色】\n" + "\n\n".join(context_parts)
    return ""


def process_decision(
    player_state: PlayerState,
    event_description: str,
    chosen_option_index: int,
    event_options: list,
    language: str = "en",
    generate_result_text: bool = True,
    ai_generator: Optional[EventGenerator] = None,
) -> Dict[str, Any]:
    """
    Process a player's decision and update state.

    Args:
        player_state: Current player state
        event_description: Description of the event
        chosen_option_index: Index of the chosen option (0-based)
        event_options: List of option dictionaries with 'text' and 'effects'
        language: Language for result text generation
        generate_result_text: Whether to generate AI result text
        ai_generator: Optional AI generator for result text

    Returns:
        Dictionary with:
        - result_text: Description of the outcome
        - effects_applied: The effects that were applied
        - success: Whether the decision was valid
        - triggered_events: List of triggered character events
    """
    if chosen_option_index < 0 or chosen_option_index >= len(event_options):
        raise ValueError(f"Invalid option index: {chosen_option_index}")

    chosen_option = event_options[chosen_option_index]
    effects = chosen_option.get("effects", {})

    # Apply effects to player
    energy_change = effects.get("energy", 0)
    mood_change = effects.get("mood", 0)
    knowledge_change = effects.get("knowledge", 0)
    wealth_change = effects.get("wealth", 0)
    relationships_change = effects.get("relationships", {})

    player_state.update(
        energy=energy_change,
        mood=mood_change,
        knowledge=knowledge_change,
        wealth=wealth_change,
        relationships=relationships_change,
    )

    # 同步 relationships 到 characters
    player_state.sync_relationships_to_characters()

    # 计算并应用角色属性变化
    character_effects = calculate_character_effects(effects, player_state)
    interaction_summary = f"选择了: {chosen_option.get('text', '')[:20]}"
    triggered_events = apply_character_effects(
        player_state, character_effects, interaction_summary
    )

    # Validate state after update
    try:
        player_state.validate_state()
    except ValueError as e:
        logger.error(f"State validation failed after decision: {e}")

    # Record decision in history
    decision_record = {
        "week": player_state.week,
        "event": event_description,
        "choice": chosen_option.get("text", ""),
        "effects": effects.copy(),
        "character_effects": character_effects if character_effects else None,
    }
    player_state.decision_history.append(decision_record)

    # Update week in decision record if not set
    if "week" not in decision_record or decision_record["week"] != player_state.week:
        decision_record["week"] = player_state.week

    # Generate result text
    result_text = ""
    if generate_result_text:
        if ai_generator:
            try:
                prompt = get_result_generation_prompt(
                    event_description, chosen_option.get("text", ""), effects, language
                )
                result_text = ai_generator.generate_completion(
                    prompt=prompt,
                    system_prompt=get_system_prompt("narrative_summary", language),
                    temperature=0.7,
                    max_tokens=4096,
                )
            except Exception as e:
                logger.warning(f"Failed to generate result text: {e}")
                result_text = _generate_fallback_result(effects, language)
        else:
            result_text = _generate_fallback_result(effects, language)

    return {
        "result_text": result_text,
        "effects_applied": effects.copy(),
        "success": True,
        "triggered_events": triggered_events,
    }


def _generate_fallback_result(effects: Dict[str, Any], language: str) -> str:
    """Generate a simple fallback result text based on effects."""
    changes = []

    if effects.get("energy", 0) != 0:
        val = effects["energy"]
        changes.append(
            f"Energy {'+' if val > 0 else ''}{val}"
            if language == "en"
            else f"精力{'+' if val > 0 else ''}{val}"
        )

    if effects.get("mood", 0) != 0:
        val = effects["mood"]
        changes.append(
            f"Mood {'+' if val > 0 else ''}{val}"
            if language == "en"
            else f"情绪{'+' if val > 0 else ''}{val}"
        )

    if effects.get("knowledge", 0) != 0:
        val = effects["knowledge"]
        changes.append(
            f"Knowledge {'+' if val > 0 else ''}{val}"
            if language == "en"
            else f"学识{'+' if val > 0 else ''}{val}"
        )

    if effects.get("wealth", 0) != 0:
        val = effects["wealth"]
        changes.append(
            f"Wealth {'+' if val > 0 else ''}¥{abs(val):,}"
            if language == "en"
            else f"财富{'+' if val > 0 else ''}¥{abs(val):,}"
        )

    if language == "en":
        return f"Your choice has consequences: {', '.join(changes)}."
    else:
        return f"你的选择带来了后果：{', '.join(changes)}。"
