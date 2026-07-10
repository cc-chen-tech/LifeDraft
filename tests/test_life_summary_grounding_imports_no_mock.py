"""Import reachability for life-summary grounding production paths."""


def test_life_summary_grounding_paths_are_reachable() -> None:
    from src.api.routers.gameplay.summary import generate_summary
    from src.services.life_summary_grounding import (
        build_life_summary_prompt,
        validate_or_fallback_life_summary,
    )

    assert callable(generate_summary)
    assert callable(build_life_summary_prompt)
    assert callable(validate_or_fallback_life_summary)

