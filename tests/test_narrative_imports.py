"""Import validation for all narrative system lazy imports.

These modules are imported lazily inside StoryGenerator._init_narrative_systems().
If any import path breaks, the system silently fails at runtime.
This test catches those failures early.
"""


def test_style_engine_imports():
    """Style manifest, prompt builder, and validator must be importable."""
    from src.ai.narrative.style_manifest import get_style
    from src.ai.narrative.style_prompt_builder import StyleAwarePromptBuilder
    from src.ai.narrative.style_validator import StyleAwareValidator

    assert get_style is not None
    assert StyleAwarePromptBuilder is not None
    assert StyleAwareValidator is not None


def test_epic_narrative_imports():
    """Character arc, world breathing, conflict tower, fate echo must be importable."""
    from src.ai.narrative.character_arc import CharacterArcEngine
    from src.ai.narrative.world_breathing import WorldBreathingEngine
    from src.ai.narrative.conflict_tower import ConflictTower
    from src.ai.narrative.fate_echo import FateEchoDatabase

    assert CharacterArcEngine is not None
    assert WorldBreathingEngine is not None
    assert ConflictTower is not None
    assert FateEchoDatabase is not None


def test_creative_enhancement_imports():
    """Emotional arc, novelty scorer, foreshadowing, preference learner must be importable."""
    from src.ai.creative.emotional_arc import EmotionalArcAnalyzer
    from src.ai.creative.novelty_scorer import NoveltyScorer
    from src.ai.creative.foreshadowing_tech import ForeshadowingTechniqueLibrary, HookInjector
    from src.ai.creative.preference_learner import PreferenceLearner

    assert EmotionalArcAnalyzer is not None
    assert NoveltyScorer is not None
    assert ForeshadowingTechniqueLibrary is not None
    assert HookInjector is not None
    assert PreferenceLearner is not None


def test_harness_imports():
    """Constraint harness subsystems must be importable."""
    from src.ai.harness import default_registry
    from src.ai.harness.diagnostics import ConstraintViolationDiagnostic
    from src.ai.harness.metrics import HarnessMetrics
    from src.ai.harness.preflight_checker import PreflightChecker
    from src.ai.harness.retry_controller import RetryController
    from src.ai.harness.validation_pipeline import ValidationPipeline

    assert default_registry is not None
    assert ConstraintViolationDiagnostic is not None
    assert HarnessMetrics is not None
    assert PreflightChecker is not None
    assert RetryController is not None
    assert ValidationPipeline is not None
