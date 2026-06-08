"""Music API degradation contracts for 2026-06-08 endpoint crashes."""


def test_music_recommendation_degradation_payload_is_json_safe() -> None:
    from src.api.routers.music import build_degraded_music_recommendation_response

    response = build_degraded_music_recommendation_response(
        RuntimeError("502 Bad Gateway <html>upstream crashed</html>")
    )

    assert response.songs == []
    assert response.mood == "unavailable"
    assert response.scene_type == "degraded"
    assert response.music_brief is not None
    assert response.music_brief["degraded"] is True
    assert "502" in response.music_brief["error"]
    assert "<html>" not in response.music_brief["error"]
