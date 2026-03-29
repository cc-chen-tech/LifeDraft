"""Simplified RoundSystemMixin facade for backward compatibility.

This module provides the RoundSystemMixin class that delegates to
specialized service classes while maintaining the original interface.

The mixin is designed to be inherited by GameLoop. It assumes the
following attributes exist on `self`:
- player_state: PlayerState
- ai_generator: EventGenerator
- language: str
- current_event: Optional[GameEvent]
- _generating: bool
- _generating_start_time: Optional[float]
- _GENERATION_TIMEOUT: float
- event_callback: Optional[Callable]
- result_callback: Optional[Callable]
- story_service: StoryService
- character_creator: CharacterCreator
- summary_selector: HistoricalSummarySelector
- relationship_service: RelationshipMCPService
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from src.ai.models import GameEvent
from src.game.round.character_introduction import CharacterIntroductionService
from src.game.round.choice_processor import RoundChoiceProcessor
from src.game.round.event_generator import RoundEventGenerator
from src.game.round.finalizer import RoundFinalizer

if TYPE_CHECKING:
    from src.ai.generator import EventGenerator
    from src.game.character_creator import CharacterCreator
    from src.game.historical_summary_selector import HistoricalSummarySelector
    from src.game.state import PlayerState
    from src.game.story_service import StoryService
    from src.mcp.relationship_service import RelationshipMCPService

logger = logging.getLogger(__name__)


class RoundSystemMixin:
    """Mixin class providing Multi-Round System functionality.

    This is a facade that delegates to specialized service classes:
    - CharacterIntroductionService: Character generation and introduction
    - RoundEventGenerator: Event generation
    - RoundChoiceProcessor: Choice processing
    - RoundFinalizer: Week finalization
    """

    # Type hints for attributes expected from the concrete class (GameLoop)
    player_state: "PlayerState"
    ai_generator: "EventGenerator"
    language: str
    story_service: "StoryService"
    character_creator: "CharacterCreator"
    summary_selector: "HistoricalSummarySelector"
    relationship_service: "RelationshipMCPService"

    def _init_round_services(self) -> None:
        """Initialize round system services. Call this in __init__."""
        # Character introduction service
        self._char_intro_service = CharacterIntroductionService(
            player_state_getter=lambda: self.player_state,
            character_creator=self.character_creator,
        )

        # Event generator service
        self._event_generator_service = RoundEventGenerator(
            player_state_getter=lambda: self.player_state,
            ai_generator=self.ai_generator,
            language_getter=lambda: self.language,
            character_introduction_service=self._char_intro_service,
            summary_selector=self.summary_selector,
            relationship_service=self.relationship_service,
            event_callback=getattr(self, "event_callback", None),
        )

        # Choice processor service
        self._choice_processor = RoundChoiceProcessor(
            player_state_getter=lambda: self.player_state,
            ai_generator=self.ai_generator,
            language_getter=lambda: self.language,
            story_service=self.story_service,
            current_event_getter=lambda: self._event_generator_service.current_event,
            current_event_setter=lambda e: setattr(
                self._event_generator_service, "current_event", e
            ),
            result_callback=getattr(self, "result_callback", None),
        )

        # Finalizer service
        self._finalizer = RoundFinalizer(
            player_state_getter=lambda: self.player_state,
            ai_generator=self.ai_generator,
            language_getter=lambda: self.language,
            story_service=self.story_service,
            character_creator=self.character_creator,
        )

        logger.info("Round system services initialized")

    # ==================== Event Generation ====================

    @property
    def current_event(self) -> Optional[GameEvent]:
        """Get current event from event generator service."""
        if hasattr(self, "_event_generator_service"):
            return self._event_generator_service.current_event
        return getattr(self, "_current_event", None)

    @current_event.setter
    def current_event(self, value: Optional[GameEvent]) -> None:
        """Set current event on event generator service."""
        if hasattr(self, "_event_generator_service"):
            self._event_generator_service.current_event = value
        self._current_event = value

    def generate_round_event(
        self,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        session: Optional[Any] = None,
    ) -> Optional[GameEvent]:
        """Generate an event for the current round. Delegates to RoundEventGenerator."""
        if not hasattr(self, "_event_generator_service"):
            self._init_round_services()
        return self._event_generator_service.generate_round_event(
            stream_callback=stream_callback,
            status_callback=status_callback,
            session=session,
        )

    # ==================== Character Introduction ====================

    def _maybe_generate_new_character(self, probability: float = 0.08) -> Optional[Dict[str, Any]]:
        """Generate new character with probability. Delegates to CharacterIntroductionService."""
        if not hasattr(self, "_char_intro_service"):
            self._init_round_services()
        return self._char_intro_service.maybe_generate_new_character(probability)

    def _determine_introduction_context(self, new_person: Dict[str, Any]) -> str:
        """Determine introduction context. Delegates to CharacterIntroductionService."""
        if not hasattr(self, "_char_intro_service"):
            self._init_round_services()
        return self._char_intro_service.determine_introduction_context(new_person)

    def _calculate_introduction_priority(self, new_person: Dict[str, Any]) -> int:
        """Calculate introduction priority. Delegates to CharacterIntroductionService."""
        if not hasattr(self, "_char_intro_service"):
            self._init_round_services()
        return self._char_intro_service.calculate_introduction_priority(new_person)

    def _check_introduction_opportunity(self) -> Optional[Dict[str, Any]]:
        """Check for introduction opportunity. Delegates to CharacterIntroductionService."""
        if not hasattr(self, "_char_intro_service"):
            self._init_round_services()
        return self._char_intro_service.check_introduction_opportunity()

    def _matches_introduction_scene(self, intro_context: str) -> bool:
        """Check if matches introduction scene. Delegates to CharacterIntroductionService."""
        if not hasattr(self, "_char_intro_service"):
            self._init_round_services()
        return self._char_intro_service.matches_introduction_scene(intro_context)

    def _introduce_pending_character(
        self, pending_entry: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Introduce pending character. Delegates to CharacterIntroductionService."""
        if not hasattr(self, "_char_intro_service"):
            self._init_round_services()
        return self._char_intro_service.introduce_pending_character(pending_entry)

    # ==================== Choice Processing ====================

    def make_round_choice(
        self,
        option_index: int,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Process round choice. Delegates to RoundChoiceProcessor."""
        if not hasattr(self, "_choice_processor"):
            self._init_round_services()
        return self._choice_processor.make_round_choice(
            option_index=option_index,
            stream_callback=stream_callback,
            status_callback=status_callback,
            finalize_week_callback=self._finalize_week,
        )

    def make_custom_choice(
        self,
        custom_text: str,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Process custom choice. Delegates to RoundChoiceProcessor."""
        if not hasattr(self, "_choice_processor"):
            self._init_round_services()
        return self._choice_processor.make_custom_choice(
            custom_text=custom_text,
            stream_callback=stream_callback,
            status_callback=status_callback,
            finalize_week_callback=self._finalize_week,
        )

    # ==================== Finalization ====================

    def _finalize_week(
        self,
        result: Dict[str, Any],
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Finalize week. Delegates to RoundFinalizer."""
        if not hasattr(self, "_finalizer"):
            self._init_round_services()
        return self._finalizer.finalize_week(result, status_callback)

    def _generate_weekly_summary_for_round_system(self) -> Dict[str, Any]:
        """Generate weekly summary. Delegates to RoundFinalizer."""
        if not hasattr(self, "_finalizer"):
            self._init_round_services()
        return self._finalizer.generate_weekly_summary()

    def compress_round_story(self, story: str, choice: str) -> Dict[str, Any]:
        """Compress story. Delegates to RoundFinalizer."""
        if not hasattr(self, "_finalizer"):
            self._init_round_services()
        return self._finalizer.compress_round_story(story, choice)

    def get_round_info(self) -> Dict[str, Any]:
        """Get round info. Delegates to RoundFinalizer."""
        if not hasattr(self, "_finalizer"):
            self._init_round_services()
        return self._finalizer.get_round_info()

    # ==================== Helper Methods ====================

    def _generate_custom_choice_effects(
        self, event_description: str, custom_text: str
    ) -> Dict[str, Any]:
        """Generate custom choice effects. Delegates to choice processor."""
        if not hasattr(self, "_choice_processor"):
            self._init_round_services()
        return self._choice_processor._generate_custom_choice_effects(
            event_description, custom_text
        )

    def _generate_custom_choice_result(
        self, event_description: str, custom_text: str
    ) -> Dict[str, Any]:
        """Generate custom choice result. Delegates to choice processor."""
        if not hasattr(self, "_choice_processor"):
            self._init_round_services()
        return self._choice_processor._generate_custom_choice_result(event_description, custom_text)

    def _generate_story_continuation(
        self,
        event_description: str,
        chosen_option: str,
        effects: Dict[str, Any],
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Generate story continuation. Delegates to choice processor."""
        if not hasattr(self, "_choice_processor"):
            self._init_round_services()
        return self._choice_processor._generate_story_continuation(
            event_description, chosen_option, effects, stream_callback
        )

    def _check_and_fix_missing_attributes(self) -> None:
        """Check and fix missing attributes. Delegates to finalizer."""
        if not hasattr(self, "_finalizer"):
            self._init_round_services()
        return self._finalizer._check_and_fix_missing_attributes()

    def _generate_family_members_details(self, old_format_members: list) -> list:
        """Generate family member details. Delegates to finalizer."""
        if not hasattr(self, "_finalizer"):
            self._init_round_services()
        return self._finalizer._generate_family_members_details(old_format_members)
