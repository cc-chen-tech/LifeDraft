"""AI event generator - Facade pattern.

This module was refactored from a 1174-line God Class into a lightweight
facade that delegates to focused sub-services:
  - StoryGenerator:   story text generation (two-stage pipeline Step 1)
  - OptionGenerator:  option generation + validation (Step 2)
  - SummaryGenerator: compression, weekly/monthly/yearly summaries
  - StoryRewriter:    segment rewriting + full regeneration

All existing public method signatures are preserved for backward compatibility.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from config.settings import PRESETS_DIR, settings
from src.ai.cache import EventCache
from src.ai.client import AIClient
from src.ai.models import GameEvent
from src.ai.option_generator import OptionGenerator
from src.ai.story_generator import StoryGenerator
from src.ai.story_rewriter import StoryRewriter
from src.ai.summary_generator import SummaryGenerator

logger = logging.getLogger(__name__)


class EventGenerator:
    """Facade - delegates to focused sub-services.

    Preserves backward compatibility for all existing callers.
    All AI calls go through ``self.ai_client`` (AIClient).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        use_cache: bool = True,
        quality_level=None,
    ):
        """
        Initialize the event generator.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: OpenAI model name (defaults to settings)
            use_cache: Whether to use event cache
            quality_level: Story generation quality level (fast/expert/master)
        """
        # Core AI client (new abstraction)
        self.ai_client = AIClient(api_key, model)

        # Cache
        self.use_cache = use_cache and settings.CACHE_EVENTS
        self.cache = EventCache() if self.use_cache else None

        # Preset events
        self.preset_events = self._load_preset_events()

        # Sub-services
        self.story_gen = StoryGenerator(self.ai_client, quality_level=quality_level)
        self.option_gen = OptionGenerator(self.ai_client)
        self.summary_gen = SummaryGenerator(self.ai_client)
        self.rewriter = StoryRewriter(self.ai_client)

    # ==================== Backward-Compatible AI Calling ====================

    def _call_ai(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        stream_callback: Optional[Callable[[str], None]] = None,
        model: Optional[str] = None,
    ) -> str:
        """Backward-compatible private AI call (delegates to AIClient)."""
        return self.ai_client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream_callback=stream_callback,
            model=model,
        )

    def generate_completion(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.8,
        max_tokens: int = 2000,
        stream_callback: Optional[Callable[[str], None]] = None,
        model: Optional[str] = None,
        retry_count: int = 1,
        language: str = "zh",
    ) -> str:
        """Public AI text generation interface.

        Args:
            prompt: User prompt text
            system_prompt: System prompt text
            temperature: Generation temperature
            max_tokens: Maximum tokens
            stream_callback: Optional streaming callback
            model: Optional model override
            retry_count: Number of attempts (1 = no retry, 2+ = retry with error feedback)
            language: Language for error feedback messages
        """
        if retry_count > 1:
            return self.ai_client.call_with_retry(
                system_prompt=system_prompt,
                user_prompt=prompt,
                retry_count=retry_count,
                temperature=temperature,
                max_tokens=max_tokens,
                stream_callback=stream_callback,
                model=model,
                language=language,
            )
        return self.ai_client.call(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream_callback=stream_callback,
            model=model,
        )

    def generate_completion_json(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant. Return valid JSON.",
        temperature: float = 0.8,
        max_tokens: int = 2000,
        model: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Public AI JSON generation interface."""
        return self.ai_client.call_json(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.8,
        max_tokens: int = 2000,
        model: Optional[str] = None,
    ):
        """Public AI streaming interface - returns raw stream object.

        Use this when you need direct access to the stream object
        (e.g., for UI streaming display).

        Returns:
            OpenAI stream object that yields chunks
        """
        use_model = model or self.ai_client.model
        client = self.ai_client.require_openai_client()
        return client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

    # ==================== Preset Events ====================

    def _load_preset_events(self) -> Dict[str, Any]:
        """Load preset events from JSON file."""
        preset_file = PRESETS_DIR / "events.json"
        if preset_file.exists():
            try:
                with open(preset_file, "r", encoding="utf-8") as f:
                    return json.load(f)  # type: ignore[no-any-return]
            except Exception as e:
                logger.warning(f"Failed to load preset events: {e}")
        return {}

    def _get_preset_milestone_event(self, week: int, language: str) -> Optional[GameEvent]:
        """Get preset milestone event if available."""
        if not self.preset_events:
            return None

        milestone_events = self.preset_events.get("milestone_events", [])
        for event_data in milestone_events:
            if event_data.get("week") == week:
                lang_data = event_data.get(language)
                if lang_data:
                    try:
                        return GameEvent(**lang_data)
                    except Exception as e:
                        logger.warning(f"Failed to parse preset milestone event: {e}")
        return None

    # ==================== Delegated Methods ====================

    def generate_event(
        self,
        player_state: Dict[str, Any],
        language: str = "en",
        retry_count: int = 3,
        week: Optional[int] = None,
        character_settings: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        force: bool = False,
        four_week_summary: Optional[str] = None,
        yearly_summary: Optional[str] = None,
        opening_story: Optional[str] = None,
        last_event_description: Optional[str] = None,
        game_date_info: Optional[Dict[str, Any]] = None,
        pending_storylines: Optional[list] = None,
        established_facts: Optional[list] = None,
        last_event_concluded: bool = True,
        last_round_full_story: str = "",
        activated_foreshadowing: Optional[Dict[str, Any]] = None,
        character_habits: Optional[list] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> GameEvent:
        """Generate a game event based on player state."""
        # Check for preset milestone events first
        if week is not None:
            preset_event = self._get_preset_milestone_event(week, language)
            if preset_event:
                logger.info(f"Using preset milestone event for 第{week + 1}周")
                return preset_event

        # Check cache (bypass if force is True)
        if self.cache and not force:
            cached_event = self.cache.get(player_state, language)
            if cached_event:
                logger.info("Using cached event")
                return cached_event

        return self.story_gen.generate_event(
            player_state=player_state,
            language=language,
            retry_count=retry_count,
            character_settings=character_settings,
            stream_callback=stream_callback,
            four_week_summary=four_week_summary,
            yearly_summary=yearly_summary,
            opening_story=opening_story,
            last_event_description=last_event_description,
            game_date_info=game_date_info,
            pending_storylines=pending_storylines,
            established_facts=established_facts,
            last_event_concluded=last_event_concluded,
            last_round_full_story=last_round_full_story,
            activated_foreshadowing=activated_foreshadowing,
            character_habits=character_habits,
            option_generator=self.option_gen,
            cache=self.cache,
            status_callback=status_callback,
        )

    def generate_round_event(
        self,
        player_state: Dict[str, Any],
        language: str,
        round_number: int,
        round_context: str,
        character_settings: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        relationship_events: Optional[list] = None,
        historical_weekly_summary: Optional[str] = None,
        historical_yearly_summary: Optional[str] = None,
        game_date_info: Optional[Dict[str, Any]] = None,
        pending_storylines: Optional[list] = None,
        established_facts: Optional[list] = None,
        last_event_concluded: bool = True,
        last_round_full_story: str = "",
        activated_foreshadowing: Optional[Dict[str, Any]] = None,
        character_habits: Optional[list] = None,
        world_model=None,
        new_character: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> GameEvent:
        """Generate a single round's story and options."""
        return self.story_gen.generate_round_event(
            player_state=player_state,
            language=language,
            round_number=round_number,
            round_context=round_context,
            character_settings=character_settings,
            stream_callback=stream_callback,
            relationship_events=relationship_events,
            historical_weekly_summary=historical_weekly_summary,
            historical_yearly_summary=historical_yearly_summary,
            game_date_info=game_date_info,
            pending_storylines=pending_storylines,
            established_facts=established_facts,
            last_event_concluded=last_event_concluded,
            last_round_full_story=last_round_full_story,
            activated_foreshadowing=activated_foreshadowing,
            character_habits=character_habits,
            world_model=world_model,
            option_generator=self.option_gen,
            new_character=new_character,
            status_callback=status_callback,
        )

    def generate_options_only(
        self,
        story_description: str,
        player_state: Dict[str, Any],
        character_settings: Optional[Dict[str, Any]] = None,
        language: str = "zh",
        retry_count: int = 3,
    ) -> GameEvent:
        """Generate options for an existing story."""
        return self.option_gen.generate_options_only(
            story_description=story_description,
            player_state=player_state,
            character_settings=character_settings,
            language=language,
            retry_count=retry_count,
        )

    def compress_story(
        self,
        story: str,
        choice: str,
        language: str,
        pending_storylines: Optional[list] = None,
        established_facts: Optional[list] = None,
        character_habits: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Compress a story into a summary and evaluate storyline status."""
        return self.summary_gen.compress_story(
            story=story,
            choice=choice,
            language=language,
            pending_storylines=pending_storylines,
            established_facts=established_facts,
            character_habits=character_habits,
        )

    def compress_narrative(
        self,
        story: str,
        choice: str,
        language: str,
        pending_storylines: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Narrative compression only (parallel-friendly)."""
        return self.summary_gen.compress_narrative(
            story=story,
            choice=choice,
            language=language,
            pending_storylines=pending_storylines,
        )

    def extract_world_updates(
        self,
        story: str,
        choice: str,
        language: str,
        established_facts: Optional[list] = None,
        character_habits: Optional[list] = None,
    ) -> Dict[str, Any]:
        """World state extraction only (parallel-friendly)."""
        return self.summary_gen.extract_world_updates(
            story=story,
            choice=choice,
            language=language,
            established_facts=established_facts,
            character_habits=character_habits,
        )

    def generate_weekly_summary(
        self,
        rounds: List[Dict[str, Any]],
        character_settings: Optional[Dict[str, Any]],
        language: str,
        game_date_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate weekly summary and bonus effects."""
        return self.summary_gen.generate_weekly_summary(
            rounds=rounds,
            character_settings=character_settings,
            language=language,
            game_date_info=game_date_info,
        )

    def generate_four_week_summary(
        self,
        stories: List[str],
        decisions: List[Dict[str, Any]],
        character_settings: Optional[Dict[str, Any]] = None,
        language: str = "zh",
        game_date_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a summary for the past 4 weeks."""
        return self.summary_gen.generate_four_week_summary(
            stories=stories,
            decisions=decisions,
            character_settings=character_settings,
            language=language,
            game_date_info=game_date_info,
        )

    def generate_yearly_summary(
        self,
        four_week_summaries: List[Dict[str, Any]],
        character_settings: Optional[Dict[str, Any]] = None,
        start_week: int = 0,
        end_week: int = 47,
        language: str = "zh",
        game_date_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a yearly summary based on 4-week summaries."""
        return self.summary_gen.generate_yearly_summary(
            four_week_summaries=four_week_summaries,
            character_settings=character_settings,
            start_week=start_week,
            end_week=end_week,
            language=language,
            game_date_info=game_date_info,
        )

    def rewrite_story_segment(
        self,
        full_story: str,
        segment_to_replace: str,
        user_instruction: str,
        character_settings: Optional[Dict[str, Any]],
        story_context: str,
        language: str = "zh",
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        world_model=None,
        player_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Rewrite a specified segment of the story."""
        return self.rewriter.rewrite_story_segment(
            full_story=full_story,
            segment_to_replace=segment_to_replace,
            user_instruction=user_instruction,
            character_settings=character_settings,
            story_context=story_context,
            language=language,
            stream_callback=stream_callback,
            status_callback=status_callback,
            world_model=world_model,
            player_state=player_state,
        )

    def regenerate_story(
        self,
        player_state: Dict[str, Any],
        character_settings: Optional[Dict[str, Any]],
        story_context: str,
        language: str = "zh",
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        world_model=None,
        opening_story: Optional[str] = None,
        last_event_description: Optional[str] = None,
    ) -> str:
        """Regenerate the entire round's story."""
        return self.rewriter.regenerate_story(
            player_state=player_state,
            character_settings=character_settings,
            story_context=story_context,
            language=language,
            stream_callback=stream_callback,
            status_callback=status_callback,
            world_model=world_model,
            opening_story=opening_story,
            last_event_description=last_event_description,
        )

    # ==================== Backward Compat Helpers ====================

    @staticmethod
    def _get_phase_from_state(player_state: Dict[str, Any]) -> str:
        """Determine life phase from player state."""
        return StoryGenerator._get_phase_from_state(player_state)

    @staticmethod
    def _clean_summary_text(summary: str) -> str:
        """Clean summary text (delegates to SummaryGenerator)."""
        return SummaryGenerator._clean_summary_text(summary)

    @staticmethod
    def _extract_summary_from_raw(content: str, original_story: str, language: str) -> str:
        """Extract summary from raw response (delegates to SummaryGenerator)."""
        return SummaryGenerator._extract_summary_from_raw(content, original_story, language)
