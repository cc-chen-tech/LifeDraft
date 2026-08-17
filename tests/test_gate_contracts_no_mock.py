"""No-mock producer/consumer contract tests for changed gameplay surfaces."""

from pathlib import Path

from src.api.schemas import (CharacterCollectionItem, CollectionResponse,
                             GameStateResponse, ItemCollectionItem,
                             LandmarkCollectionItem, PhoneLoginRequest,
                             RoundSceneResponse, VoiceReadingSettingsResponse,
                             VoiceReadingSettingsUpdateRequest,
                             VoiceUploadConsentRequest)
import pytest

pytestmark = [pytest.mark.unit]


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_TYPES = (ROOT / "frontend" / "src" / "lib" / "types.ts").read_text(encoding="utf-8")


def _fields(model: type) -> set[str]:
    return set(model.model_fields.keys())


def test_round_scene_response_matches_frontend_scene_image_contract() -> None:
    required = {
        "scene_id",
        "game_id",
        "week",
        "round_number",
        "stage",
        "image_url",
        "scene_description",
        "created_at",
    }

    assert required <= _fields(RoundSceneResponse)
    for field in required - {"game_id"}:
        assert f"{field}:" in FRONTEND_TYPES


def test_collection_response_matches_frontend_collection_contract() -> None:
    assert {"characters", "items", "landmarks"} <= _fields(CollectionResponse)
    assert "characters: CharacterCollectionItem[]" in FRONTEND_TYPES
    assert "items: ItemCollectionItem[]" in FRONTEND_TYPES
    assert "landmarks: LandmarkCollectionItem[]" in FRONTEND_TYPES

    for model in (CharacterCollectionItem, ItemCollectionItem, LandmarkCollectionItem):
        fields = _fields(model)
        assert {"name", "description", "image_url", "image_generated"} <= fields
        for field in ("name", "description", "image_url", "image_generated"):
            assert f"{field}:" in FRONTEND_TYPES


def test_game_state_response_preserves_history_and_current_event_contract() -> None:
    assert {"game_id", "player_state", "progress", "round_info", "current_event"} <= _fields(
        GameStateResponse
    )
    assert "round_history?: RoundHistoryEntry[]" in FRONTEND_TYPES
    assert "current_event_data?: CurrentEventData | null" in FRONTEND_TYPES
    assert "current_event: CurrentEventData | null" in FRONTEND_TYPES


def test_member_voice_placeholders_match_frontend_contract() -> None:
    assert {"phone_number", "verification_code"} <= _fields(PhoneLoginRequest)
    assert "export interface PhoneLoginRequest" in FRONTEND_TYPES
    assert "phone_number: string" in FRONTEND_TYPES
    assert "verification_code?: string | null" in FRONTEND_TYPES

    required_response = {
        "member_required",
        "enabled",
        "available_voice_colors",
        "selected_voice_color",
        "uploaded_voice_available",
        "auto_read_enabled",
    }
    assert required_response <= _fields(VoiceReadingSettingsResponse)
    assert {"selected_voice_color", "auto_read_enabled"} <= _fields(
        VoiceReadingSettingsUpdateRequest
    )
    assert {"consent_confirmed", "sample_name"} <= _fields(VoiceUploadConsentRequest)

    for field in required_response:
        assert f"{field}:" in FRONTEND_TYPES
    assert "export interface VoiceReadingSettingsResponse" in FRONTEND_TYPES
    assert "export interface VoiceReadingSettingsUpdateRequest" in FRONTEND_TYPES
    assert "export interface VoiceUploadConsentRequest" in FRONTEND_TYPES


def test_frontend_image_api_paths_match_backend_routes() -> None:
    api_source = (ROOT / "frontend" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert "'/images/generate'" in api_source
    assert "'/images/opening-illustration'" in api_source
    assert "'/images/opening-illustration/regenerate'" in api_source
    assert "'/images', {" not in api_source
    assert "'/images/opening'" not in api_source
    assert "'/images/opening/regenerate'" not in api_source
