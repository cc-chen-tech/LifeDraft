"""
Prompt templates for AI story generation.

This package provides all prompt generation functions for the story game.
Organized by functional domain for better maintainability.

Modules:
- _helpers: Internal helper functions for context building
- story_prompts: Story and event generation prompts
- summary_prompts: Summary generation prompts
- world_prompts: World state extraction and ending prompts
- validation_prompts: Consistency validation prompts
- character_prompts: Character creation and profile prompts

Usage:
    from config.prompts import get_event_generation_prompt
    from config.prompts import get_weekly_summary_prompt
    # etc.
"""

# Helper functions (exported for use in other modules)
from config.prompts._helpers import (
    _build_character_habits_context,
    _build_continuation_mandate,
    _build_established_facts_context,
    _build_foreshadowing_context,
    _build_full_character_context,
    _build_logic_constraints,
    _build_new_character_intro_context,
    _build_pending_storylines_context,
    _build_time_context,
    _build_world_model_constraints,
    _collect_available_people,
    _format_effects,
    _format_people_names,
)

# Character creation and profile prompts
from config.prompts.character_prompts import (
    get_character_profile_synthesis_prompt,
    get_character_setting_prompt,
    get_initial_attributes_prompt,
    get_opening_story_prompt,
    get_relationship_person_prompt,
    get_relationships_summary_prompt,
    get_story_origin_prompt,
)

# Story generation prompts
from config.prompts.story_prompts import (
    get_event_generation_prompt,
    get_options_only_prompt,
    get_relationship_event_context,
    get_result_generation_prompt,
    get_round_event_prompt,
    get_story_only_prompt,
)

# Summary generation prompts
from config.prompts.summary_prompts import (
    get_combined_choice_postprocess_prompt,
    get_four_week_summary_prompt,
    get_narrative_compression_prompt,
    get_story_compression_prompt,
    get_weekly_summary_prompt,
    get_yearly_summary_prompt,
)

# Validation prompts
from config.prompts.validation_prompts import (
    get_consistency_validation_prompt,
    get_story_analysis_prompt,
)

# World state and ending prompts
from config.prompts.world_prompts import get_ending_prompt, get_world_extraction_prompt

__all__ = [
    # Story prompts
    "get_event_generation_prompt",
    "get_result_generation_prompt",
    "get_options_only_prompt",
    "get_story_only_prompt",
    "get_relationship_event_context",
    "get_round_event_prompt",
    # Summary prompts
    "get_four_week_summary_prompt",
    "get_yearly_summary_prompt",
    "get_story_compression_prompt",
    "get_narrative_compression_prompt",
    "get_combined_choice_postprocess_prompt",
    "get_weekly_summary_prompt",
    # World prompts
    "get_ending_prompt",
    "get_world_extraction_prompt",
    # Validation prompts
    "get_story_analysis_prompt",
    "get_consistency_validation_prompt",
    # Character prompts
    "get_character_profile_synthesis_prompt",
    "get_character_setting_prompt",
    "get_story_origin_prompt",
    "get_relationship_person_prompt",
    "get_relationships_summary_prompt",
    "get_initial_attributes_prompt",
    "get_opening_story_prompt",
    # Helper functions
    "_collect_available_people",
    "_format_people_names",
    "_build_new_character_intro_context",
    "_build_time_context",
    "_build_pending_storylines_context",
    "_build_continuation_mandate",
    "_build_character_habits_context",
    "_build_foreshadowing_context",
    "_build_logic_constraints",
    "_build_established_facts_context",
    "_build_world_model_constraints",
    "_build_full_character_context",
    "_format_effects",
]
