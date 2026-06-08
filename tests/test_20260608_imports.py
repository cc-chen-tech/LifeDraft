"""Import contracts for the 2026-06-08 live UX regression fixes."""


def test_relationship_authority_helpers_are_importable() -> None:
    from src.game import relationship_authority

    assert callable(relationship_authority.build_required_cast_constraints)
    assert callable(relationship_authority.validate_required_cast_coverage)
    assert callable(relationship_authority.canonicalize_key_person_candidate)


def test_music_quality_helpers_are_importable() -> None:
    from src.services.music_service import dedupe_music_candidates

    assert callable(dedupe_music_candidates)
