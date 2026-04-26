"""RoundSystemMixin contract tests.

No mocks. Verifies that the facade mixin correctly delegates to
specialized round services and exposes the expected interface.
"""

from src.game.round.system_mixin import RoundSystemMixin


# ---------------------------------------------------------------------------
# Concrete class that mixes in RoundSystemMixin
# ---------------------------------------------------------------------------

class ConcreteGameLoop(RoundSystemMixin):
    """Minimal concrete class for testing the mixin in isolation.

    Provides all attributes that RoundSystemMixin expects to find on ``self``.
    """

    def __init__(self, language: str = "zh"):
        # Attributes expected by RoundSystemMixin
        from src.ai.generator import EventGenerator
        from src.game.character_creation import CharacterCreator
        from src.game.state.player_state import PlayerState

        self.language = language
        self.player_state = PlayerState(  # type: ignore[call-arg]
            player_name="TestHero",
            week=0,
            age=25,
            current_round=0,
            rounds_per_week=3,
            energy=70,
            mood=60,
            knowledge=50,
            wealth=10000,
        )
        self.ai_generator = EventGenerator()
        self.current_event = None
        self._current_event = None
        self._generating = False
        self._generating_start_time = None
        self._GENERATION_TIMEOUT = 60.0
        self.event_callback = None
        self.result_callback = None

        # StoryService needs EventGenerator
        from src.game.story_service import StoryService
        self.story_service = StoryService(
            ai_generator=self.ai_generator, language=language
        )

        # CharacterCreator takes ai_generator (EventGenerator) and language
        self.character_creator = CharacterCreator(
            ai_generator=self.ai_generator, language=language
        )

        from src.game.historical_summary_selector import HistoricalSummarySelector
        self.summary_selector = HistoricalSummarySelector()

        from src.mcp.relationship_service import RelationshipMCPService
        self.relationship_service = RelationshipMCPService()

        # Initialize round services
        self._init_round_services()


# ===================================================================
# Contract tests
# ===================================================================


class TestRoundSystemMixinInitialization:
    """Verify that _init_round_services sets up all services."""

    def test_init_creates_char_intro_service(self):
        loop = ConcreteGameLoop()
        assert hasattr(loop, "_char_intro_service")
        assert loop._char_intro_service is not None

    def test_init_creates_event_generator_service(self):
        loop = ConcreteGameLoop()
        assert hasattr(loop, "_event_generator_service")
        assert loop._event_generator_service is not None

    def test_init_creates_choice_processor(self):
        loop = ConcreteGameLoop()
        assert hasattr(loop, "_choice_processor")
        assert loop._choice_processor is not None

    def test_init_creates_finalizer(self):
        loop = ConcreteGameLoop()
        assert hasattr(loop, "_finalizer")
        assert loop._finalizer is not None

    def test_init_is_idempotent(self):
        """Calling _init_round_services multiple times should not raise."""
        loop = ConcreteGameLoop()
        # Second call should be safe (services already initialized)
        loop._init_round_services()
        assert loop._char_intro_service is not None
        assert loop._event_generator_service is not None
        assert loop._choice_processor is not None
        assert loop._finalizer is not None

    def test_lazy_init_on_first_access(self):
        """Services should be lazily initialized if needed.

        We test by accessing a method that triggers lazy init.
        Since our class initializes in __init__, we create a minimal
        subclass that does NOT initialize services.
        """
        class LazyGameLoop(RoundSystemMixin):
            language = "zh"

            def __init__(self):
                from src.ai.generator import EventGenerator
                from src.game.state.player_state import PlayerState
                from src.game.story_service import StoryService
                from src.game.character_creation import CharacterCreator
                from src.game.historical_summary_selector import HistoricalSummarySelector
                from src.mcp.relationship_service import RelationshipMCPService

                self.player_state = PlayerState(  # type: ignore[call-arg]
                    player_name="TestHero",
                    week=0,
                    age=25,
                    current_round=0,
                    rounds_per_week=3,
                    energy=70,
                    mood=60,
                    knowledge=50,
                    wealth=10000,
                )
                self.ai_generator = EventGenerator()
                self.current_event = None
                self._generating = False
                self._generating_start_time = None
                self._GENERATION_TIMEOUT = 60.0
                self.event_callback = None
                self.result_callback = None
                self.story_service = StoryService(
                    ai_generator=self.ai_generator, language="zh"
                )
                self.character_creator = CharacterCreator(
                    ai_generator=self.ai_generator, language="zh"
                )
                self.summary_selector = HistoricalSummarySelector()
                self.relationship_service = RelationshipMCPService()
                # Note: not calling _init_round_services here

        loop = LazyGameLoop()
        # Before lazy init, services should not exist
        assert not hasattr(loop, "_char_intro_service")

        # Accessing a method should trigger lazy init
        context = loop._determine_introduction_context(
            {"name": "Test", "role": "朋友"}
        )
        assert isinstance(context, str)
        # After lazy init, services should exist
        assert hasattr(loop, "_char_intro_service")


class TestCurrentEventProperty:
    """Contract tests for the current_event property delegation."""

    def test_current_event_getter_from_service(self):
        loop = ConcreteGameLoop()
        # Should return the event from event_generator_service
        event = loop.current_event
        # Initially None since no event generated
        assert event is None or hasattr(event, "event_description")

    def test_current_event_setter_updates_service(self):
        loop = ConcreteGameLoop()
        from src.ai.models import EventOption, GameEvent

        test_event = GameEvent(
            event_description="Test event for setter verification.",
            options=[
                EventOption(
                    text="Option A",
                    effects={"energy": 0},
                    likely_choice=True,
                ),
                EventOption(
                    text="Option B",
                    effects={"energy": 0},
                    likely_choice=False,
                ),
            ],
        )
        loop.current_event = test_event
        # Should be readable back
        assert loop.current_event is test_event
        assert loop.current_event.event_description == "Test event for setter verification."

    def test_current_event_setter_updates_fallback(self):
        """Setting current_event should also update _current_event fallback."""
        loop = ConcreteGameLoop()
        from src.ai.models import EventOption, GameEvent

        test_event = GameEvent(
            event_description="Fallback test.",
            options=[
                EventOption(
                    text="Opt", effects={"energy": 0}, likely_choice=True
                ),
                EventOption(
                    text="Opt2", effects={"energy": 0}, likely_choice=False
                ),
            ],
        )
        loop.current_event = test_event
        assert loop._current_event is test_event


class TestEventGenerationDelegation:
    """Contract tests for generate_round_event."""

    def test_generate_round_event_method_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop.generate_round_event)

    def test_generate_round_event_signature(self):
        """Method should accept optional stream_callback, status_callback, session."""
        import inspect

        sig = inspect.signature(ConcreteGameLoop.generate_round_event)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "stream_callback" in params
        assert "status_callback" in params
        assert "session" in params


class TestChoiceProcessingDelegation:
    """Contract tests for choice processing methods."""

    def test_make_round_choice_method_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop.make_round_choice)

    def test_make_round_choice_signature(self):
        """Method should accept option_index plus optional callbacks."""
        import inspect

        sig = inspect.signature(ConcreteGameLoop.make_round_choice)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "option_index" in params
        assert "stream_callback" in params
        assert "status_callback" in params

    def test_make_custom_choice_method_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop.make_custom_choice)

    def test_make_custom_choice_signature(self):
        """Method should accept custom_text plus optional callbacks."""
        import inspect

        sig = inspect.signature(ConcreteGameLoop.make_custom_choice)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "custom_text" in params
        assert "stream_callback" in params
        assert "status_callback" in params


class TestCharacterIntroductionDelegation:
    """Contract tests for character introduction delegation methods."""

    def test_maybe_generate_new_character_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._maybe_generate_new_character)

    def test_determine_introduction_context_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._determine_introduction_context)

    def test_calculate_introduction_priority_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._calculate_introduction_priority)

    def test_check_introduction_opportunity_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._check_introduction_opportunity)

    def test_matches_introduction_scene_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._matches_introduction_scene)

    def test_introduce_pending_character_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._introduce_pending_character)

    def test_maybe_generate_new_character_returns_none_or_dict(self):
        loop = ConcreteGameLoop()
        result = loop._maybe_generate_new_character(probability=0.0)
        # With probability=0, should always return None
        assert result is None

    def test_determine_introduction_context_returns_string(self):
        loop = ConcreteGameLoop()
        result = loop._determine_introduction_context(
            {"name": "Friend", "role": "同事"}
        )
        assert isinstance(result, str)
        assert result in ("work", "social", "education", "location_change", "random")

    def test_calculate_introduction_priority_returns_int(self):
        loop = ConcreteGameLoop()
        result = loop._calculate_introduction_priority(
            {"name": "Friend", "role": "朋友", "affinity": 50}
        )
        assert isinstance(result, int)
        assert 0 <= result <= 10

    def test_check_introduction_opportunity_returns_none_or_dict(self):
        loop = ConcreteGameLoop()
        result = loop._check_introduction_opportunity()
        # With no pending characters, should return None
        assert result is None

    def test_matches_introduction_scene_returns_bool(self):
        loop = ConcreteGameLoop()
        result = loop._matches_introduction_scene("random")
        assert isinstance(result, bool)

    def test_introduce_pending_character_returns_none_for_bad_entry(self):
        loop = ConcreteGameLoop()
        result = loop._introduce_pending_character({"no_data": True})
        assert result is None


class TestFinalizationDelegation:
    """Contract tests for week finalization methods."""

    def test_finalize_week_method_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._finalize_week)

    def test_generate_weekly_summary_method_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._generate_weekly_summary_for_round_system)

    def test_compress_round_story_method_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop.compress_round_story)

    def test_get_round_info_method_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop.get_round_info)

    def test_get_round_info_returns_dict(self):
        loop = ConcreteGameLoop()
        result = loop.get_round_info()
        assert isinstance(result, dict)


class TestHelperMethodsDelegation:
    """Contract tests for helper delegation methods."""

    def test_generate_custom_choice_effects_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._generate_custom_choice_effects)

    def test_generate_custom_choice_result_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._generate_custom_choice_result)

    def test_generate_story_continuation_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._generate_story_continuation)

    def test_check_and_fix_missing_attributes_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._check_and_fix_missing_attributes)

    def test_generate_family_members_details_exists(self):
        loop = ConcreteGameLoop()
        assert callable(loop._generate_family_members_details)


class TestRoundSystemMixinTypeHints:
    """Verify the type hint attributes exist as expected."""

    def test_class_has_type_hint_attributes(self):
        """Type hints are class-level annotations that document expected attributes."""
        annotations = RoundSystemMixin.__dict__.get("__annotations__", {})
        expected = [
            "player_state",
            "ai_generator",
            "language",
            "story_service",
            "character_creator",
            "summary_selector",
            "relationship_service",
        ]
        for attr in expected:
            assert attr in annotations, (
                f"Type hint for '{attr}' missing from RoundSystemMixin.__annotations__"
            )
