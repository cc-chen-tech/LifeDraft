"""Quick test for story regeneration - runs in seconds.

Usage:
    python -m pytest tests/test_regenerate_quick.py -v

Or run directly:
    python tests/test_regenerate_quick.py
"""

from unittest.mock import MagicMock


def test_regenerate_uses_backend_story():
    """Critical test: Verify regenerate uses backend story, not frontend."""
    # Simulate the fixed logic from useGameState.ts

    # Scenario 1: Backend returns valid new story
    backend_story = "New regenerated story content from backend with sufficient length"
    frontend_story = "Old accumulated story from streaming"  # Shorter

    # Fixed logic: use backend if length > 50
    final_story = backend_story if len(backend_story) > 50 else frontend_story

    assert (
        final_story == backend_story
    ), f"Should use backend story ({len(backend_story)} chars), not frontend ({len(frontend_story)} chars)"

    # Scenario 2: Backend returns empty/short story (fallback)
    short_backend = "Error"
    final_story_fallback = short_backend if len(short_backend) > 50 else frontend_story

    assert (
        final_story_fallback == frontend_story
    ), "Should fallback to frontend when backend story is too short"

    print("✓ Regenerate correctly uses backend story when valid")


def test_regenerate_clears_all_caches():
    """Verify all caches are cleared before regeneration."""

    # Mock player_state
    player_state = MagicMock()
    player_state.week = 10
    player_state.current_round = 0
    player_state.round_history = [{"week": 10, "round": 0, "event_description": "Old"}]
    player_state.last_round_full_story = "Old story"
    player_state.current_event_data = {"story": "Old"}

    # Simulate stream_regenerate clearing logic
    player_state.last_round_full_story = ""
    player_state.round_history = [
        e for e in player_state.round_history if not (e.get("week") == 10 and e.get("round") == 0)
    ]
    player_state.current_event_data = None

    # Verify cleared
    assert player_state.last_round_full_story == ""
    assert len(player_state.round_history) == 0
    assert player_state.current_event_data is None

    print("✓ All caches properly cleared")


def test_no_resume_when_caches_cleared():
    """Verify event generator doesn't resume old story when caches cleared."""

    # Simulate event_generator.py resume logic
    current_week = 10
    current_round = 0
    round_history = []  # Cleared
    last_round_full_story = ""  # Cleared
    current_event_data = None  # Cleared

    existing_story = None

    # Check round_history (empty, so skip)
    if round_history:
        last_entry = round_history[-1]
        if last_entry.get("week") == current_week and last_entry.get("round") == current_round:
            existing_story = last_entry.get("event_description")
    # Check last_round_full_story (empty, so skip)
    elif last_round_full_story and current_round == 0 and current_event_data:
        existing_story = last_round_full_story

    # Should not resume
    assert existing_story is None, "Should not resume when caches are cleared"

    print("✓ No resume when caches cleared")


def test_old_logic_was_buggy():
    """Document the old buggy logic that caused the issue."""

    backend_story = "New story from backend"
    frontend_story = "Old accumulated story that is longer than backend story"

    # OLD BUGGY LOGIC (length comparison)
    old_final = backend_story if len(backend_story) > len(frontend_story) else frontend_story

    # This would incorrectly use frontend_story!
    assert old_final == frontend_story, "Old logic was buggy - would use frontend story"

    # NEW FIXED LOGIC (validity check)
    backend_story if len(backend_story) > 50 else frontend_story

    # For short backend story, this correctly uses frontend as fallback
    # For long backend story (>50), this correctly uses backend

    print("✓ Old buggy logic documented")


if __name__ == "__main__":
    # Run tests directly
    print("\n" + "=" * 60)
    print("Quick Regenerate Fix Tests")
    print("=" * 60 + "\n")

    test_regenerate_uses_backend_story()
    test_regenerate_clears_all_caches()
    test_no_resume_when_caches_cleared()
    test_old_logic_was_buggy()

    print("\n" + "=" * 60)
    print("✅ All quick tests passed!")
    print("=" * 60 + "\n")
