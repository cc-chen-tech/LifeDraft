"""Public request-size contracts for new writes."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.input_limits import (
    CHARACTER_SETTINGS_MAX_BYTES,
    CUSTOM_ACTION_MAX_CHARS,
    FEEDBACK_MAX_CHARS,
    FULL_STORY_MAX_CHARS,
    LIFE_VISION_MAX_CHARS,
    NAME_MAX_CHARS,
    REPLACEMENT_SEGMENT_MAX_CHARS,
    STORY_DIALOGUE_MAX_CHARS,
    STORY_REWRITE_INSTRUCTION_MAX_CHARS,
    VOICE_TEXT_MAX_CHARS,
    compact_json_size_bytes,
)
from src.api.main import app
from src.api.routers.music import MusicGenerationRequest, MusicRecommendationRequest
from src.api.schemas import (
    AddEntitiesRequest,
    BatchGenerateCharactersRequest,
    CreateGameRequest,
    CreateItemRequest,
    CreatePresetRequest,
    CreateSavePointRequest,
    CustomChoiceRequest,
    GenerateOpeningIllustrationRequest,
    GenerateImageRequest,
    GenerateRelationshipRequest,
    GenerateRoundSceneRequest,
    GenerateSettingRequest,
    OpeningStoryRequest,
    PresetInfo,
    ReadingContext,
    RecognizedEntity,
    RegenerateCharacterImageRequest,
    RegenerateItemImageRequest,
    RegenerateImageRequest,
    RegenerateOpeningIllustrationRequest,
    RegenerateRoundSceneRequest,
    RelationshipsSummaryRequest,
    RewriteStoryRequest,
    StoryChatRequest,
    UpdateCharacterSettingsRequest,
    VoiceUploadConsentRequest,
)


@pytest.mark.parametrize(
    ("model", "field", "limit", "payload"),
    [
        (
            CreateGameRequest,
            "player_name",
            NAME_MAX_CHARS,
            {"character_settings": {"era": "modern"}, "life_vision": "vision"},
        ),
        (
            CreateGameRequest,
            "life_vision",
            LIFE_VISION_MAX_CHARS,
            {"character_settings": {"era": "modern"}, "player_name": "name"},
        ),
        (CustomChoiceRequest, "custom_text", CUSTOM_ACTION_MAX_CHARS, {}),
        (StoryChatRequest, "message", STORY_DIALOGUE_MAX_CHARS, {}),
        (
            RegenerateCharacterImageRequest,
            "feedback",
            FEEDBACK_MAX_CHARS,
            {},
        ),
        (
            RewriteStoryRequest,
            "user_instruction",
            STORY_REWRITE_INSTRUCTION_MAX_CHARS,
            {"full_story": "story"},
        ),
        (
            RewriteStoryRequest,
            "segment_to_replace",
            REPLACEMENT_SEGMENT_MAX_CHARS,
            {"full_story": "story", "user_instruction": "rewrite"},
        ),
        (
            RewriteStoryRequest,
            "full_story",
            FULL_STORY_MAX_CHARS,
            {"user_instruction": "rewrite"},
        ),
        (
            ReadingContext,
            "text",
            VOICE_TEXT_MAX_CHARS,
            {
                "source_type": "current_story",
                "game_id": 1,
                "text_hash": "hash",
            },
        ),
    ],
)
def test_request_text_limits_accept_boundary_and_reject_one_more(
    model: type, field: str, limit: int, payload: dict[str, object]
) -> None:
    boundary = "界" * limit
    parsed = model.model_validate({**payload, field: boundary})
    assert getattr(parsed, field) == boundary

    with pytest.raises(ValidationError) as exc_info:
        model.model_validate({**payload, field: boundary + "外"})

    error = next(error for error in exc_info.value.errors() if error["loc"] == (field,))
    assert error["type"] == "string_too_long"
    assert error["ctx"]["max_length"] == limit


def test_character_settings_limit_is_compact_utf8_json_bytes() -> None:
    base = {"player_name": "林", "life_vision": "愿景"}
    low = 0
    high = CHARACTER_SETTINGS_MAX_BYTES
    while low < high:
        midpoint = (low + high + 1) // 2
        candidate = {"bio": "界" * midpoint}
        if compact_json_size_bytes(candidate) <= CHARACTER_SETTINGS_MAX_BYTES:
            low = midpoint
        else:
            high = midpoint - 1

    boundary = {"bio": "界" * low}
    parsed = CreateGameRequest.model_validate({**base, "character_settings": boundary})
    assert parsed.character_settings == boundary

    oversized = {"bio": "界" * (low + 1)}
    assert compact_json_size_bytes(oversized) > CHARACTER_SETTINGS_MAX_BYTES
    with pytest.raises(ValidationError) as exc_info:
        CreateGameRequest.model_validate({**base, "character_settings": oversized})

    error = next(
        error for error in exc_info.value.errors() if error["loc"] == ("character_settings",)
    )
    assert error["type"] == "json_too_large"
    assert error["ctx"]["limit"] == CHARACTER_SETTINGS_MAX_BYTES
    assert error["ctx"]["actual_length"] == compact_json_size_bytes(oversized)
    assert error["ctx"]["unit"] == "bytes"


def test_api_422_reports_field_limit_and_actual_length_without_echoing_input() -> None:
    client = TestClient(app)
    actual = NAME_MAX_CHARS + 1
    response = client.post(
        "/api/games",
        json={
            "player_name": "名" * actual,
            "life_vision": "愿景",
            "character_settings": {"era": "现代"},
        },
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["field"] == "player_name"
    assert error["limit"] == NAME_MAX_CHARS
    assert error["actual_length"] == actual
    assert error["unit"] == "characters"
    assert "input" not in error


def test_unrelated_api_validation_errors_keep_standard_fastapi_shape() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/games",
        json={"life_vision": "愿景", "character_settings": {"era": "现代"}},
    )

    assert response.status_code == 422
    error = next(item for item in response.json()["detail"] if item["loc"][-1] == "player_name")
    assert error["type"] == "missing"
    assert error["input"] == {
        "life_vision": "愿景",
        "character_settings": {"era": "现代"},
    }
    assert "field" not in error


def test_openapi_publishes_named_limits_and_field_max_lengths() -> None:
    schema = app.openapi()
    assert schema["x-input-limits"] == {
        "name": NAME_MAX_CHARS,
        "lifeVision": LIFE_VISION_MAX_CHARS,
        "feedback": FEEDBACK_MAX_CHARS,
        "customAction": CUSTOM_ACTION_MAX_CHARS,
        "storyDialogue": STORY_DIALOGUE_MAX_CHARS,
        "rewriteInstruction": STORY_REWRITE_INSTRUCTION_MAX_CHARS,
        "replacementSegment": REPLACEMENT_SEGMENT_MAX_CHARS,
        "fullStory": FULL_STORY_MAX_CHARS,
        "voiceText": VOICE_TEXT_MAX_CHARS,
        "characterSettingsBytes": CHARACTER_SETTINGS_MAX_BYTES,
    }
    create_schema = schema["components"]["schemas"]["CreateGameRequest"]
    assert create_schema["properties"]["player_name"]["maxLength"] == NAME_MAX_CHARS
    assert create_schema["properties"]["life_vision"]["maxLength"] == LIFE_VISION_MAX_CHARS
    assert (
        create_schema["properties"]["character_settings"]["x-maxBytes"]
        == CHARACTER_SETTINGS_MAX_BYTES
    )


def test_limit_registry_is_json_serializable_for_contract_generation() -> None:
    encoded = json.dumps(app.openapi()["x-input-limits"], sort_keys=True)
    assert '"fullStory": 32000' in encoded


def test_generated_typescript_limits_match_backend_registry(tmp_path: Path) -> None:
    generated = tmp_path / "input-limits.generated.ts"
    subprocess.run(
        [sys.executable, "scripts/export_input_limits.py", str(generated)],
        check=True,
    )
    tracked = Path("frontend/src/types/input-limits.generated.ts")
    assert generated.read_text(encoding="utf-8") == tracked.read_text(encoding="utf-8")


def test_legacy_response_models_do_not_reject_or_truncate_saved_text() -> None:
    oversized_name = "旧" * (NAME_MAX_CHARS + 10)
    oversized_vision = "存" * (LIFE_VISION_MAX_CHARS + 10)
    restored = PresetInfo(
        preset_id=1,
        preset_name="旧存档",
        player_name=oversized_name,
        life_vision=oversized_vision,
    )
    assert restored.player_name == oversized_name
    assert restored.life_vision == oversized_vision


@pytest.mark.parametrize(
    ("model", "field", "limit"),
    [
        (CreateGameRequest, "player_name", NAME_MAX_CHARS),
        (CreateGameRequest, "life_vision", LIFE_VISION_MAX_CHARS),
        (GenerateSettingRequest, "player_name", NAME_MAX_CHARS),
        (GenerateSettingRequest, "life_vision", LIFE_VISION_MAX_CHARS),
        (GenerateSettingRequest, "feedback", FEEDBACK_MAX_CHARS),
        (GenerateRelationshipRequest, "player_name", NAME_MAX_CHARS),
        (GenerateRelationshipRequest, "life_vision", LIFE_VISION_MAX_CHARS),
        (GenerateRelationshipRequest, "feedback", FEEDBACK_MAX_CHARS),
        (UpdateCharacterSettingsRequest, "player_name", NAME_MAX_CHARS),
        (UpdateCharacterSettingsRequest, "life_vision", LIFE_VISION_MAX_CHARS),
        (OpeningStoryRequest, "player_name", NAME_MAX_CHARS),
        (OpeningStoryRequest, "life_vision", LIFE_VISION_MAX_CHARS),
        (RelationshipsSummaryRequest, "player_name", NAME_MAX_CHARS),
        (RelationshipsSummaryRequest, "life_vision", LIFE_VISION_MAX_CHARS),
        (CreatePresetRequest, "player_name", NAME_MAX_CHARS),
        (CreatePresetRequest, "life_vision", LIFE_VISION_MAX_CHARS),
        (CreatePresetRequest, "preset_name", NAME_MAX_CHARS),
        (VoiceUploadConsentRequest, "sample_name", NAME_MAX_CHARS),
        (GenerateImageRequest, "entity_name", NAME_MAX_CHARS),
        (CreateSavePointRequest, "save_name", NAME_MAX_CHARS),
        (CreateItemRequest, "name", NAME_MAX_CHARS),
        (CustomChoiceRequest, "custom_text", CUSTOM_ACTION_MAX_CHARS),
        (ReadingContext, "text", VOICE_TEXT_MAX_CHARS),
        (RewriteStoryRequest, "full_story", FULL_STORY_MAX_CHARS),
        (RewriteStoryRequest, "segment_to_replace", REPLACEMENT_SEGMENT_MAX_CHARS),
        (
            RewriteStoryRequest,
            "user_instruction",
            STORY_REWRITE_INSTRUCTION_MAX_CHARS,
        ),
        (StoryChatRequest, "message", STORY_DIALOGUE_MAX_CHARS),
        (GenerateImageRequest, "feedback", FEEDBACK_MAX_CHARS),
        (RegenerateImageRequest, "feedback", FEEDBACK_MAX_CHARS),
        (RegenerateCharacterImageRequest, "feedback", FEEDBACK_MAX_CHARS),
        (RegenerateItemImageRequest, "feedback", FEEDBACK_MAX_CHARS),
        (GenerateOpeningIllustrationRequest, "story_text", FULL_STORY_MAX_CHARS),
        (GenerateOpeningIllustrationRequest, "player_name", NAME_MAX_CHARS),
        (RegenerateOpeningIllustrationRequest, "story_text", FULL_STORY_MAX_CHARS),
        (RegenerateOpeningIllustrationRequest, "player_name", NAME_MAX_CHARS),
        (RegenerateOpeningIllustrationRequest, "user_prompt", FEEDBACK_MAX_CHARS),
        (RegenerateRoundSceneRequest, "story_text", FULL_STORY_MAX_CHARS),
        (RegenerateRoundSceneRequest, "player_name", NAME_MAX_CHARS),
        (RegenerateRoundSceneRequest, "user_prompt", FEEDBACK_MAX_CHARS),
        (GenerateRoundSceneRequest, "story_text", FULL_STORY_MAX_CHARS),
        (GenerateRoundSceneRequest, "player_name", NAME_MAX_CHARS),
        (MusicRecommendationRequest, "story_text", FULL_STORY_MAX_CHARS),
        (MusicGenerationRequest, "story_text", FULL_STORY_MAX_CHARS),
    ],
)
def test_all_public_text_request_fields_publish_their_limit(
    model: type, field: str, limit: int
) -> None:
    property_schema = model.model_json_schema()["properties"][field]
    if "anyOf" in property_schema:
        property_schema = next(
            candidate for candidate in property_schema["anyOf"] if candidate.get("type") == "string"
        )
    assert property_schema["maxLength"] == limit


@pytest.mark.parametrize(
    ("model", "field"),
    [
        (CreateGameRequest, "character_settings"),
        (GenerateSettingRequest, "previous_settings"),
        (GenerateRelationshipRequest, "previous_settings"),
        (UpdateCharacterSettingsRequest, "character_settings"),
        (OpeningStoryRequest, "character_settings"),
        (RelationshipsSummaryRequest, "previous_settings"),
        (CreatePresetRequest, "character_settings"),
        (BatchGenerateCharactersRequest, "character_settings"),
        (GenerateOpeningIllustrationRequest, "character_settings"),
        (RegenerateOpeningIllustrationRequest, "character_settings"),
        (RegenerateRoundSceneRequest, "character_settings"),
        (GenerateRoundSceneRequest, "character_settings"),
        (MusicRecommendationRequest, "character_settings"),
    ],
)
def test_all_character_setting_request_fields_publish_byte_limit(model: type, field: str) -> None:
    property_schema = model.model_json_schema()["properties"][field]
    if "anyOf" in property_schema:
        property_schema = next(
            candidate for candidate in property_schema["anyOf"] if candidate.get("type") == "object"
        )
    assert property_schema["x-maxBytes"] == CHARACTER_SETTINGS_MAX_BYTES


def test_nested_entity_writes_reject_long_names_without_constraining_legacy_response() -> None:
    payload = {
        "name": "新" * (NAME_MAX_CHARS + 1),
        "description": "新实体",
    }
    with pytest.raises(ValidationError) as exc_info:
        AddEntitiesRequest.model_validate({"items": [payload]})
    assert exc_info.value.errors()[0]["loc"] == ("items", 0, "name")

    legacy_name = "旧" * (NAME_MAX_CHARS + 1)
    assert RecognizedEntity(name=legacy_name, description="旧记录").name == legacy_name


def test_add_entities_route_uses_the_constrained_request_model() -> None:
    route_schema = app.openapi()["paths"]["/api/collection/{game_id}/add-entities"]["post"]
    body_schema = route_schema["requestBody"]["content"]["application/json"]["schema"]
    assert body_schema["$ref"] == "#/components/schemas/AddEntitiesRequest"

    write_schema = app.openapi()["components"]["schemas"]["RecognizedEntityWrite"]
    assert write_schema["properties"]["name"]["maxLength"] == NAME_MAX_CHARS
