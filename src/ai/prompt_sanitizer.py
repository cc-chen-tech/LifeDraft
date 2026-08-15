"""Prompt 注入防护工具"""

import re

from src.api.input_limits import LIFE_VISION_MAX_CHARS, NAME_MAX_CHARS

MAX_USER_INPUT_LENGTH = LIFE_VISION_MAX_CHARS
MAX_NAME_LENGTH = NAME_MAX_CHARS
_PROMPT_CONTROL_RE = re.compile(
    r"(?i)(?:ignore\s+(?:all\s+)?(?:previous|prior|system|developer)?\s*"
    r"(?:instruction|prompt|context)|system\s*:|assistant\s*:|user\s*:|"
    r"(?:无视|忽略|跳过|绕过|忘记|(?:停止|不再|请勿|不要|勿|拒绝)\s*(?:再)?\s*遵循)\s*(?:(?:以上|前文|上文|之前|此前|先前|前面)(?:\s*的)?(?:\s*所有)?|所有)?\s*(?:系统)?\s*(?:指令|提示|要求)|"
    r"(?:只|全部)\s*(?:返回|输出|回答|写|留).{0,8}(?:空白|留空|一行|为空)|"
    r"后续(?:回答|内容|输出).{0,12}(?:留空|空白|只|全部)|"
    r"切换身份|扮演\s*(?:系统|助手)|提示词|系统说明)"
)


class PromptInputTooLongError(ValueError):
    """Raised when sanitization would otherwise change input by truncation."""

    def __init__(self, original_text: str, limit: int) -> None:
        self.original_text = original_text
        self.limit = limit
        self.actual_length = len(original_text)
        super().__init__(
            f"user input exceeds {limit} characters (actual: {self.actual_length})"
        )


def sanitize_user_input(
    text: str,
    max_length: int = MAX_USER_INPUT_LENGTH,
    *,
    enforce_length: bool = True,
) -> str:
    """清洗用户输入，防止 prompt 注入

    Args:
        text: 用户输入的文本
        max_length: 最大允许长度

    Returns:
        清洗后的文本
    """
    if not text:
        return text

    # 1. Never change user meaning by silently slicing the submitted value.
    if enforce_length and len(text) > max_length:
        raise PromptInputTooLongError(text, max_length)

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
        r"忽略\s*(?:以上|之前|此前|所有)?\s*(?:的)?\s*(?:要求|指令|提示)",
        r"(?:系统|助手|用户)\s*[：:]",
        r"(?:覆盖|替换|改写)\s*(?:系统|之前|此前)?\s*(?:指令|提示|要求)",
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


def sanitize_persisted_player_name(name: str) -> str:
    """Sanitize a trusted saved name without applying new-write limits.

    Existing saves are intentionally not migrated or truncated. New requests are
    still constrained by the API model before persistence.
    """
    return sanitize_user_input(
        name,
        max_length=MAX_NAME_LENGTH,
        enforce_length=False,
    )


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


def sanitize_persisted_life_vision(vision: str) -> str:
    """Build a safe, bounded prompt projection without mutating an old save."""
    sanitized = sanitize_user_input(
        vision,
        max_length=MAX_USER_INPUT_LENGTH,
        enforce_length=False,
    )
    if "[filtered]" in sanitized or _PROMPT_CONTROL_RE.search(sanitized):
        return ""
    return sanitized[:MAX_USER_INPUT_LENGTH].rstrip()


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
