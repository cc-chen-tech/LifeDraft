"""Focused feature-flag contracts for newly introduced gates."""

from config.feature_flags import get_feature, reset_features, set_feature


def test_daily_world_projection_flag_defaults_off_and_can_be_enabled() -> None:
    reset_features()
    try:
        assert get_feature("daily_world_projection_v1") is False
        set_feature("daily_world_projection_v1", True)
        assert get_feature("daily_world_projection_v1") is True
    finally:
        reset_features()
