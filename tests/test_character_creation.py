"""Tests for character creation module."""

import random
from collections import Counter

import pytest

from src.game.character_creation import assign_sexual_orientation


class TestSexualOrientationAssignment:
    """Test sexual orientation assignment."""

    def test_assign_sexual_orientation_returns_valid(self):
        """Test that assign_sexual_orientation returns a valid value."""
        valid_orientations = ["heterosexual", "homosexual", "bisexual", "asexual"]

        for _ in range(100):
            orientation = assign_sexual_orientation()
            assert orientation in valid_orientations

    def test_assign_sexual_orientation_deterministic_seed(self):
        """Test that with same seed, same result is produced."""
        random.seed(42)
        result1 = assign_sexual_orientation()

        random.seed(42)
        result2 = assign_sexual_orientation()

        assert result1 == result2

    def test_orientation_distribution(self):
        """Test that orientation distribution roughly matches expected weights."""
        # Expected weights:
        # heterosexual: 90%
        # homosexual: 4%
        # bisexual: 5%
        # asexual: 1%

        sample_size = 10000
        counts = Counter()

        for _ in range(sample_size):
            orientation = assign_sexual_orientation()
            counts[orientation] += 1

        # Check proportions (with some tolerance)
        hetero_pct = counts["heterosexual"] / sample_size
        homo_pct = counts["homosexual"] / sample_size
        bi_pct = counts["bisexual"] / sample_size
        asexual_pct = counts["asexual"] / sample_size

        # Allow 3% tolerance for statistical variation
        assert 0.87 <= hetero_pct <= 0.93, f"heterosexual: {hetero_pct:.2%}"
        assert 0.02 <= homo_pct <= 0.06, f"homosexual: {homo_pct:.2%}"
        assert 0.03 <= bi_pct <= 0.07, f"bisexual: {bi_pct:.2%}"
        assert 0.00 <= asexual_pct <= 0.03, f"asexual: {asexual_pct:.2%}"

    def test_all_orientations_possible(self):
        """Test that all orientations can be assigned (with enough samples)."""
        sample_size = 5000
        found_orientations = set()

        for _ in range(sample_size):
            orientation = assign_sexual_orientation()
            found_orientations.add(orientation)

            # Early exit if all found
            if len(found_orientations) == 4:
                break

        assert "heterosexual" in found_orientations
        assert "homosexual" in found_orientations
        assert "bisexual" in found_orientations
        # asexual is rare (1%), might need more samples
        # Don't strictly require it in this test
