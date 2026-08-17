"""No-mock producer/consumer contracts for regeneration audio state."""

from pathlib import Path

from src.api.schemas import VoiceReadingSettingsResponse, VoiceReadingSettingsUpdateRequest
import pytest

pytestmark = [pytest.mark.unit]



ROOT = Path(__file__).resolve().parents[1]


def test_voice_setting_contract_preserves_selected_voice_color() -> None:
    assert "selected_voice_color" in VoiceReadingSettingsUpdateRequest.model_fields
    assert "selected_voice_color" in VoiceReadingSettingsResponse.model_fields
    response = VoiceReadingSettingsResponse(
        member_required=False,
        enabled=True,
        available_voice_colors=[],
        selected_voice_color="clear_neutral",
        uploaded_voice_available=False,
        auto_read_enabled=False,
        tts_provider="minimax",
        tts_model="speech-2.8-turbo",
        tts_provider_available=True,
        backend_audio_enabled=True,
        playback_mode="audio",
    )

    assert response.selected_voice_color == "clear_neutral"


def test_play_page_uses_one_daily_story_listening_experience() -> None:
    play_page = (ROOT / "frontend/src/app/play/page.tsx").read_text(encoding="utf-8")

    assert "StoryListeningExperience" in play_page
    assert "CompletedStoryMediaGate" not in play_page
    assert "useStoryVoiceStore" not in play_page
    assert "setActiveStoryText(storyText)" not in play_page
