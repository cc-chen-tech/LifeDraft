"""Provider-free contracts for round illustration shaping and persistence."""

import io

from PIL import Image

from src.game.round.illustration_service import RoundIllustrationService
import pytest

pytestmark = [pytest.mark.unit]



class _SceneClient:
    def __init__(self):
        self.analysis_inputs = []
        self.edit_inputs = []
        self.generated_prompts = []

    def analyze_story_for_illustration(self, **kwargs):
        self.analysis_inputs.append(kwargs)
        return "旧书院的雨夜门廊", "林岚握着祖传罗盘。"

    def edit_image(self, **kwargs):
        self.edit_inputs.append(kwargs)
        return []

    def generate_image(self, **kwargs):
        self.generated_prompts.append(kwargs)
        return b"scene-image", "provider-prompt"


class _SceneStorage:
    def __init__(self):
        self.saved = []

    def save_image(self, **kwargs):
        self.saved.append(kwargs)
        return "7/round_scene/week_4_round_1_result.jpg", "local"


class _SceneDb:
    def __init__(self):
        self.records = []
        self.commit_count = 0
        self.rollback_count = 0

    def add(self, record):
        self.records.append(record)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def _service():
    client = _SceneClient()
    storage = _SceneStorage()
    db = _SceneDb()
    return RoundIllustrationService(client, storage, db), client, storage, db


def test_reference_compression_resizes_transparent_image_to_decodable_jpeg():
    service, _client, _storage, _db = _service()
    original = Image.new("RGBA", (1024, 512), (30, 90, 180, 140))
    source = io.BytesIO()
    original.save(source, format="PNG")

    compressed = service._compress_reference_image(source.getvalue(), max_dimension=256, quality=90)
    decoded = Image.open(io.BytesIO(compressed))

    assert decoded.format == "JPEG"
    assert decoded.mode == "RGB"
    assert decoded.size == (256, 128)


def test_involved_entities_prioritize_people_then_repeated_item_then_location():
    service, _client, _storage, _db = _service()
    facts = [
        {"category": "item", "subject": "祖传罗盘", "fact": "祖传罗盘是旧案线索"},
        {"category": "memory", "subject": "档案", "fact": "祖传罗盘曾指向书院"},
        {"category": "memory", "subject": "雨夜", "fact": "祖传罗盘再次发热"},
        {"category": "landmark", "subject": "旧书院", "fact": "旧书院保存着档案"},
    ]

    entities = service._extract_involved_entities(
        "文叔在旧书院门口递给林岚祖传罗盘。",
        {"relationships": {"key_people": [{"name": "文叔", "relationship": "导师"}]}},
        world_model_data={"dynamic_facts": [{"fact_type": "possession", "subject": "祖传罗盘"}]},
        established_facts=facts,
    )

    assert [(entity["name"], entity["type"]) for entity in entities] == [
        ("文叔", "character"),
        ("祖传罗盘", "item"),
        ("旧书院", "location"),
    ]


def test_scene_persistence_records_week_round_stage_and_fallback_prompt_without_provider():
    service, client, storage, db = _service()

    service._generate_round_illustration_sync(
        game_id=7,
        round_number=1,
        story_text="林岚走进旧书院。",
        character_settings={"era": {"era_name": "民国"}},
        player_name="林岚",
        existing_images=[],
        stage="result",
        week=3,
    )

    assert client.analysis_inputs[0]["character_info"] == {"name": "林岚", "era": "民国"}
    assert client.generated_prompts[0]["size"] == "1664*928"
    assert storage.saved[0]["entity_name"] == "林岚_week_4_round_1"
    assert storage.saved[0]["stage"] == "result"
    assert db.commit_count == 1
    scene = db.records[0]
    assert (scene.game_id, scene.week, scene.round_number, scene.stage) == (7, 3, 1, "result")
    assert scene.referenced_images == []
