"""AI utility functions - shared helpers for JSON extraction and AI calls."""

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON object from a text response that may contain non-JSON content.

    Handles common AI response patterns:
    - Pure JSON responses
    - JSON wrapped in ```json ... ``` code blocks
    - JSON embedded within explanatory text

    Args:
        text: Raw text potentially containing JSON

    Returns:
        Parsed JSON dict, or None if extraction fails
    """
    if not text:
        return None

    text = text.strip()

    # Try 1: Direct JSON parse
    try:
        result1: Dict[str, Any] = json.loads(text)
        return result1
    except json.JSONDecodeError:
        pass

    # Try 2: Extract from ```json ... ``` code block (backticks)
    if "```json" in text:
        try:
            json_str = text.split("```json")[1].split("```")[0].strip()
            result2: Dict[str, Any] = json.loads(json_str)  # type: ignore[no-any-return]
            return result2
        except (IndexError, json.JSONDecodeError):
            pass

    # Try 3: Extract from ``` ... ``` code block (backticks)
    if "```" in text:
        try:
            json_str = text.split("```")[1].split("```")[0].strip()
            result3: Dict[str, Any] = json.loads(json_str)  # type: ignore[no-any-return]
            return result3
        except (IndexError, json.JSONDecodeError):
            pass

    # Try 3.5: Extract from '''json ... ''' code block (single quotes - some models use this)
    if "'''json" in text:
        try:
            json_str = text.split("'''json")[1].split("'''")[0].strip()
            result4: Dict[str, Any] = json.loads(json_str)  # type: ignore[no-any-return]
            return result4
        except (IndexError, json.JSONDecodeError):
            pass

    if "'''" in text:
        try:
            json_str = text.split("'''")[1].split("'''")[0].strip()
            result5: Dict[str, Any] = json.loads(json_str)  # type: ignore[no-any-return]
            return result5
        except (IndexError, json.JSONDecodeError):
            pass

    # Try 4: Find JSON object pattern in text
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            result6: Dict[str, Any] = json.loads(json_match.group())  # type: ignore[no-any-return]
            return result6
        except json.JSONDecodeError:
            pass

    logger.warning(f"Failed to extract JSON from text (length={len(text)}): {text[:200]}...")
    return None
