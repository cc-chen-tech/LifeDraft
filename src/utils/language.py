"""Language detection utilities."""

from typing import Any, Dict


def detect_language_from_state(state_data: Dict[str, Any]) -> str:
    """
    从游戏状态推断语言（基于era_description字符判断）。

    Args:
        state_data: 游戏状态字典，包含 character_settings

    Returns:
        语言代码：'zh' 或 'en'

    Logic:
        - 如果 era_description 全部是 ASCII 字符（不含中文），返回 'en'
        - 否则返回 'zh'（默认）
    """
    character_settings = state_data.get("character_settings", {})
    if not character_settings:
        return "zh"

    era_desc = character_settings.get("era", {}).get("era_description", "")
    if era_desc and all(ord(c) < 128 for c in era_desc.replace(" ", "")):
        return "en"

    return "zh"
