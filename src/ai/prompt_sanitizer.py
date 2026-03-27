"""Prompt 注入防护工具"""

import re
from typing import Optional

# 最大用户输入长度
MAX_USER_INPUT_LENGTH = 500
MAX_NAME_LENGTH = 50


def sanitize_user_input(text: str, max_length: int = MAX_USER_INPUT_LENGTH) -> str:
    """清洗用户输入，防止 prompt 注入

    Args:
        text: 用户输入的文本
        max_length: 最大允许长度

    Returns:
        清洗后的文本
    """
    if not text:
        return text

    # 1. 长度限制
    text = text[:max_length]

    # 2. 移除可能的系统指令注入模式
    # 移除试图覆盖系统角色的模式
    injection_patterns = [
        r"(?i)ignore\s+(all\s+)?previous\s+instructions?",
        r"(?i)you\s+are\s+now\s+",
        r"(?i)system\s*:\s*",
        r"(?i)assistant\s*:\s*",
        r"(?i)forget\s+(everything|all)",
        r"(?i)new\s+instructions?\s*:",
        r"(?i)override\s+(system|prompt)",
    ]
    for pattern in injection_patterns:
        text = re.sub(pattern, "[filtered]", text)

    # 3. 移除控制字符（保留换行和基本空白）
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return text.strip()


def sanitize_player_name(name: str) -> str:
    """清洗玩家名称

    Args:
        name: 玩家名称

    Returns:
        清洗后的名称
    """
    return sanitize_user_input(name, max_length=MAX_NAME_LENGTH)


def wrap_user_input(text: str, label: str = "用户输入") -> str:
    """用明确的边界标记包裹用户输入

    Args:
        text: 用户输入文本
        label: 边界标记的标签名

    Returns:
        包裹后的文本
    """
    sanitized = sanitize_user_input(text)
    return f"<{label}>{sanitized}</{label}>"


def sanitize_life_vision(vision: str) -> str:
    """清洗人生愿景输入

    Args:
        vision: 人生愿景文本

    Returns:
        清洗后的人生愿景
    """
    return sanitize_user_input(vision, max_length=MAX_USER_INPUT_LENGTH)


def sanitize_custom_action(action: str) -> str:
    """清洗自定义行动输入

    Args:
        action: 自定义行动文本

    Returns:
        清洗后的行动文本
    """
    return sanitize_user_input(action, max_length=MAX_USER_INPUT_LENGTH)


def sanitize_user_choice(choice: str) -> str:
    """清洗用户选择文本

    Args:
        choice: 用户选择的选项文本

    Returns:
        清洗后的选择文本
    """
    return sanitize_user_input(choice, max_length=MAX_USER_INPUT_LENGTH)
