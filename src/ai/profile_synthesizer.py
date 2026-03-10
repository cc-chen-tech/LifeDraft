"""Character behavioral profile synthesis service.

Extracts AI-driven character profiling logic from game_loop.py into
the AI layer where it belongs.
"""

import logging
from typing import Any, Dict, List, Optional

from src.ai.client import AIClient
from src.ai.system_prompts import get_system_prompt
from src.ai.utils import extract_json

logger = logging.getLogger(__name__)


class ProfileSynthesizer:
    """Character behavioral profile synthesis - AI concern extracted from GameLoop."""

    def __init__(self, client: AIClient):
        self.client = client

    def synthesize(
        self,
        char_name: str,
        traits: List[str],
        evidence: List[str],
        existing_profile: Optional[Dict[str, Any]],
        language: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Synthesize a character behavioral profile from evidence.

        Args:
            char_name: Character name
            traits: Initial personality traits from settings
            evidence: List of behavioral evidence strings
            existing_profile: Existing profile dict (or None)
            language: Language code

        Returns:
            New profile dict, or None on failure
        """
        from config.prompts import get_character_profile_synthesis_prompt

        prompt = get_character_profile_synthesis_prompt(
            character_name=char_name,
            character_settings_traits=traits,
            behavioral_evidence=evidence,
            existing_profile=existing_profile,
            language=language,
        )

        sys_prompt = get_system_prompt("profile_synthesizer", language)

        try:
            response = self.client.call(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=4096,
            )

            data = extract_json(response)
            if not data:
                return None

            old_count = 0
            if existing_profile:
                old_count = existing_profile.get("evidence_count", 0)

            return {
                "character": char_name,
                "behavioral_traits": data.get("behavioral_traits", [])[:5],
                "speech_style": data.get("speech_style", ""),
                "decision_patterns": data.get("decision_patterns", [])[:4],
                "emotional_tendencies": data.get("emotional_tendencies", [])[:3],
                "behavioral_boundaries": data.get("behavioral_boundaries", [])[:4],
                "constraint_text": data.get("constraint_text", ""),
                "evidence_count": old_count + 1,
            }

        except Exception as e:
            logger.error(f"Profile synthesis failed for {char_name}: {e}")
            return None
