"""Import validation tests for the 6 new Claude-Code-inspired modules.

Tests that all new module paths are reachable and export expected symbols.
"""
import pytest


class TestDirectImports:
    """Test that each new module can be directly imported."""

    def test_import_model_fallback_classes(self):
        from src.ai.model_fallback import FallbackChain, ModelFallbackConfig
        assert FallbackChain is not None
        assert ModelFallbackConfig is not None

    def test_import_truncation_recovery_classes(self):
        from src.ai.truncation_recovery import TruncationRecovery, TruncationRecoveryConfig
        assert TruncationRecovery is not None
        assert TruncationRecoveryConfig is not None

    def test_import_generation_state_classes(self):
        from src.ai.generation_state import GenerationState, StateTracker, TransitionReason
        assert GenerationState is not None
        assert StateTracker is not None
        assert TransitionReason is not None

    def test_import_feature_flags(self):
        from config.feature_flags import get_feature, set_feature, reset_features, FeatureFlags, FEATURE_DEFAULTS
        assert get_feature is not None
        assert set_feature is not None
        assert reset_features is not None
        assert FEATURE_DEFAULTS is not None

    def test_import_parallel_postprocessor(self):
        from src.game.parallel_postprocessor import ParallelPostProcessor, PostProcessingResult
        assert ParallelPostProcessor is not None
        assert PostProcessingResult is not None

    def test_import_reactive_compressor(self):
        from src.ai.reactive_compressor import ReactiveCompressor, CompactionResult
        assert ReactiveCompressor is not None
        assert CompactionResult is not None


class TestModuleConstants:
    """Test that module-level constants are importable."""

    def test_import_default_budget_trim_order(self):
        from src.ai.reactive_compressor import DEFAULT_BUDGET_TRIM_ORDER
        assert isinstance(DEFAULT_BUDGET_TRIM_ORDER, list)
        assert len(DEFAULT_BUDGET_TRIM_ORDER) > 0

    def test_import_protected_fields(self):
        from src.ai.reactive_compressor import PROTECTED_FIELDS
        assert isinstance(PROTECTED_FIELDS, list)
        assert "established_facts" in PROTECTED_FIELDS

    def test_import_env_var_map(self):
        from config.feature_flags import _ENV_VAR_MAP
        assert isinstance(_ENV_VAR_MAP, dict)
        assert "constraint_harness" in _ENV_VAR_MAP

    def test_import_continuation_prompts(self):
        from src.ai.truncation_recovery import DEFAULT_CONTINUATION_PROMPT_ZH, DEFAULT_CONTINUATION_PROMPT_EN
        assert isinstance(DEFAULT_CONTINUATION_PROMPT_ZH, str)
        assert isinstance(DEFAULT_CONTINUATION_PROMPT_EN, str)

    def test_import_transition_reason_enum_values(self):
        from src.ai.generation_state import TransitionReason
        assert TransitionReason.INITIAL.value == "initial"
        assert TransitionReason.HARNESS_RETRY.value == "harness_retry"
        assert TransitionReason.TEMPERATURE_ADJUST.value == "temperature_adjust"
        assert TransitionReason.CONTEXT_COMPACT.value == "context_compact"
        assert TransitionReason.TRUNCATION_RECOVERY.value == "truncation_recovery"
        assert TransitionReason.MODEL_FALLBACK.value == "model_fallback"


class TestDataclassInstantiation:
    """Test that dataclasses can be instantiated with required fields."""

    def test_model_fallback_config_instantiation(self):
        from src.ai.model_fallback import ModelFallbackConfig
        config = ModelFallbackConfig(
            primary_model="gpt-4",
            fallback_models=["gpt-4-turbo", "gpt-3.5-turbo"],
        )
        assert config.primary_model == "gpt-4"
        assert config.max_fallback_attempts == 3  # default

    def test_truncation_recovery_config_instantiation(self):
        from src.ai.truncation_recovery import TruncationRecoveryConfig
        config = TruncationRecoveryConfig()
        assert config.max_continuations == 3  # default

    def test_generation_state_instantiation(self):
        from src.ai.generation_state import GenerationState, TransitionReason
        state = GenerationState(
            attempt=0,
            transition_reason=TransitionReason.INITIAL,
            temperature=0.85,
            context_budget_factor=1.0,
            model_used="gpt-4",
        )
        assert state.attempt == 0
        assert state.temperature == 0.85

    def test_post_processing_result_instantiation(self):
        from src.game.parallel_postprocessor import PostProcessingResult
        result = PostProcessingResult()
        assert result.compression_result is None
        assert result.vector_stored is False
        assert result.errors == []

    def test_compaction_result_instantiation(self):
        from src.ai.reactive_compressor import CompactionResult
        result = CompactionResult(
            original_token_count=5000,
            compressed_token_count=3000,
        )
        assert result.original_token_count == 5000
        assert result.removed_sections == []  # default


class TestIntegrationImports:
    """Test that new modules will be importable from existing modules after integration.
    
    These tests are expected to FAIL until Phase 3 integration is complete (TDD red phase).
    They are marked with xfail to indicate they are known-failing until implementation.
    """

    @pytest.mark.xfail(reason="Phase 3 Task 12: AIClient integration not yet done")
    def test_client_has_call_with_fallback(self):
        from src.ai.client import AIClient
        assert hasattr(AIClient, 'call_with_fallback')

    @pytest.mark.xfail(reason="Phase 3 Task 14: Settings integration not yet done")
    def test_settings_has_feature_flags(self):
        from config.settings import Settings
        settings = Settings()
        assert hasattr(settings, 'FEATURE_FLAGS')

    @pytest.mark.xfail(reason="Phase 3 Task 14: Settings integration not yet done")
    def test_settings_has_model_fallback_chain(self):
        from config.settings import Settings
        settings = Settings()
        assert hasattr(settings, 'MODEL_FALLBACK_CHAIN')


class TestCrossModuleImports:
    """Test that new modules can import from each other and from existing modules."""

    def test_feature_flags_importable_from_config(self):
        """feature_flags is in config/ package, verify config.__init__ doesn't break."""
        import config
        from config.feature_flags import get_feature
        assert get_feature is not None

    def test_reactive_compressor_constants_exist(self):
        """Verify reactive_compressor has the expected constants for integration."""
        from src.ai.reactive_compressor import DEFAULT_BUDGET_TRIM_ORDER, PROTECTED_FIELDS
        # These should be non-overlapping
        for protected in PROTECTED_FIELDS:
            assert protected not in DEFAULT_BUDGET_TRIM_ORDER, \
                f"Protected field '{protected}' should not be in trim order"
