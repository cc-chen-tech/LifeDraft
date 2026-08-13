"""Tests for RoundIllustrationService."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from src.ai.image_client import ContentInspectionError, ImageGenerationError
from src.game.round.illustration_service import RoundIllustrationService


class TestRoundIllustrationServiceInit:
    """Test RoundIllustrationService initialization."""

    def test_init_with_dependencies(self):
        """Test initialization with all dependencies."""
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_db = MagicMock()

        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=mock_storage,
            db_session=mock_db,
        )

        assert service.image_client == mock_client
        assert service.image_storage == mock_storage
        assert service.db == mock_db


class TestRoundIllustrationIntegrity:
    """Round illustration persistence should be idempotent under duplicate triggers."""

    def test_unique_scene_conflict_rolls_back_and_returns_existing_without_error(self):
        mock_client = MagicMock()
        mock_client.analyze_story_for_illustration.return_value = ("茶楼雅室", "林见微坐在窗边。")
        mock_storage = MagicMock()
        mock_storage.save_image.return_value = ("2/round_scene/week_2_round_0_event.jpg", "local")
        mock_db = MagicMock()
        mock_db.commit.side_effect = IntegrityError(
            "(sqlite3.IntegrityError) UNIQUE constraint failed: "
            "scene_images.game_id, scene_images.week, scene_images.round_number, scene_images.stage",
            "",
            "",
        )
        existing_scene = MagicMock(scene_id=9)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_scene

        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=mock_storage,
            db_session=mock_db,
        )
        service._generate_scene_image = MagicMock(return_value=(b"image-bytes", "final prompt"))

        service._generate_round_illustration_sync(
            game_id=2,
            round_number=0,
            story_text="林见微在归云客栈后院准备出发。",
            character_settings={"identity": {"name": "林见微"}},
            player_name="林见微",
            existing_images=[],
            stage="event",
            week=1,
        )

        mock_db.rollback.assert_called_once()
        mock_db.query.assert_called()


class TestGetPlayerImage:
    """Test _get_player_image method."""

    def test_get_player_image_with_player_main(self):
        """Test getting player image with player_main key."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        images = [
            {"image_type": "character", "entity_key": "npc_1"},
            {"image_type": "character", "entity_key": "player_main", "image_id": 1},
        ]

        result = service._get_player_image(images)
        assert result["image_id"] == 1

    def test_get_player_image_fallback_to_first_character(self):
        """Test fallback to first character image."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        images = [
            {"image_type": "character", "entity_key": "npc_1", "image_id": 2},
            {"image_type": "location", "entity_key": "home"},
        ]

        result = service._get_player_image(images)
        assert result["image_id"] == 2

    def test_get_player_image_no_character_images(self):
        """Test when no character images exist."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        images = [
            {"image_type": "location", "entity_key": "home"},
        ]

        result = service._get_player_image(images)
        assert result is None


class TestFindEntityImage:
    """Test _find_entity_image method."""

    def test_find_entity_image_found(self):
        """Test finding entity image."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        images = [
            {"entity_name": "Mom", "image_id": 1},
            {"entity_name": "Dad", "image_id": 2},
        ]

        result = service._find_entity_image(images, "Mom")
        assert result["image_id"] == 1

    def test_find_entity_image_not_found(self):
        """Test when entity image not found."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        images = [
            {"entity_name": "Mom", "image_id": 1},
        ]

        result = service._find_entity_image(images, "Dad")
        assert result is None


class TestExtractEraFromSettings:
    """Test _extract_era_from_settings method."""

    def test_extract_era_dict(self):
        """Test extracting era from dict settings."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        settings = {"era": {"era_name": "古代", "era_description": "唐朝"}}

        result = service._extract_era_from_settings(settings)
        assert result == "古代"

    def test_extract_era_dict_description_only(self):
        """Test extracting era from dict with only description."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        settings = {"era": {"era_description": "唐朝盛世"}}

        result = service._extract_era_from_settings(settings)
        assert result == "唐朝盛世"

    def test_extract_era_string(self):
        """Test extracting era from string settings."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        settings = {"era": "现代"}

        result = service._extract_era_from_settings(settings)
        assert result == "现代"

    def test_extract_era_missing(self):
        """Test extracting era when missing."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        settings = {}

        result = service._extract_era_from_settings(settings)
        assert result == "现代"


class TestExtractInvolvedEntities:
    """Test _extract_involved_entities method."""

    def test_extract_from_key_people(self):
        """Test extracting entities from key_people."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        settings = {
            "relationships": {
                "key_people": [
                    {"name": "张三"},
                    {"name": "李四"},
                ]
            }
        }

        result = service._extract_involved_entities("张三来了", settings)
        assert len(result) == 1
        assert result[0]["name"] == "张三"
        assert result[0]["type"] == "character"

    def test_extract_from_family(self):
        """Test extracting entities from family."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        settings = {
            "family": {
                "family_members": [
                    {"name": "妈妈"},
                    {"name": "爸爸"},
                ]
            }
        }

        result = service._extract_involved_entities("妈妈做了饭，爸爸在看电视", settings)
        names = [e["name"] for e in result]
        assert "妈妈" in names
        assert "爸爸" in names

    def test_extract_max_three_entities(self):
        """Test that maximum 3 entities are returned."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        settings = {
            "relationships": {
                "key_people": [
                    {"name": "A"},
                    {"name": "B"},
                    {"name": "C"},
                    {"name": "D"},
                ]
            }
        }

        result = service._extract_involved_entities("A B C D 都在", settings)
        assert len(result) == 3


class TestGenerateSceneImage:
    """Test _generate_scene_image method."""

    def test_generate_with_reference(self):
        """Test generating scene with reference image."""
        mock_client = MagicMock()
        mock_client.edit_image = MagicMock(return_value=[(b"fake_image_data", "prompt1")])

        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        image_data, prompt = service._generate_scene_image(
            scene_desc="A beautiful sunset",
            illustration_prompt="cinematic lighting",
            reference_urls=["base64_data"],
            era="现代",
        )

        assert image_data == b"fake_image_data"
        mock_client.edit_image.assert_called_once()

    def test_generate_without_reference(self):
        """Test generating scene without reference image."""
        mock_client = MagicMock()
        mock_client.generate_image = MagicMock(return_value=(b"fake_image_data", "prompt1"))

        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        image_data, prompt = service._generate_scene_image(
            scene_desc="A beautiful sunset",
            illustration_prompt="cinematic lighting",
            reference_urls=[],
            era="现代",
        )

        assert image_data == b"fake_image_data"
        mock_client.generate_image.assert_called_once()

    def test_generate_with_reference_falls_back(self):
        """Test fallback to text-to-image when reference generation returns empty."""
        mock_client = MagicMock()
        mock_client.edit_image = MagicMock(return_value=[])
        mock_client.generate_image = MagicMock(return_value=(b"fallback_image_data", "prompt1"))

        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        image_data, prompt = service._generate_scene_image(
            scene_desc="A beautiful sunset",
            illustration_prompt="cinematic lighting",
            reference_urls=["base64_data"],
            era="现代",
        )

        assert image_data == b"fallback_image_data"
        mock_client.edit_image.assert_called_once()
        mock_client.generate_image.assert_called_once()


class TestGetImageUrlAsBase64:
    """Test _get_image_url_as_base64 method."""

    def test_get_image_as_base64_no_image_id(self):
        """Test when no image_id in info."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        result = service._get_image_url_as_base64({})
        assert result is None

    def test_get_image_as_base64_image_not_found(self):
        """Test when image not found in database."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=mock_db,
        )

        result = service._get_image_url_as_base64({"image_id": 1})
        assert result is None

    def test_get_image_as_base64_success(self):
        """Test successful base64 conversion."""
        mock_db = MagicMock()
        mock_image = MagicMock()
        mock_image.storage_path = "test/image.png"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_image

        mock_storage = MagicMock()
        mock_storage.get_image_data = MagicMock(return_value=b"fake_image_bytes")

        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=mock_storage,
            db_session=mock_db,
        )

        result = service._get_image_url_as_base64({"image_id": 1})
        assert result is not None
        assert result.startswith("data:image/jpeg;base64,")

    def test_get_image_as_base64_jpeg(self):
        """Test base64 conversion for JPEG."""
        mock_db = MagicMock()
        mock_image = MagicMock()
        mock_image.storage_path = "test/image.jpg"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_image

        mock_storage = MagicMock()
        mock_storage.get_image_data = MagicMock(return_value=b"fake_image_bytes")

        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=mock_storage,
            db_session=mock_db,
        )

        result = service._get_image_url_as_base64({"image_id": 1})
        assert result.startswith("data:image/jpeg;base64,")


class TestGenerateRoundIllustrationAsync:
    """Test generate_round_illustration_async method."""

    def test_async_generation_starts_thread(self):
        """Test that async generation starts a thread."""
        service = RoundIllustrationService(
            image_client=MagicMock(),
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        with patch("threading.Thread") as mock_thread:
            service.generate_round_illustration_async(
                game_id=1,
                round_number=1,
                story_text="Test story",
                character_settings={},
                player_name="Player",
                existing_images=[],
            )

            mock_thread.assert_called_once()
            mock_thread.return_value.start.assert_called_once()


class TestSyncGeneration:
    """Test _generate_round_illustration_sync method."""

    def test_sync_generation_skips_missing_entity_image_backfill_by_default(self, monkeypatch):
        """场景插画默认不应因缺少实体参考图而额外生成人物/物品图。"""
        from src.game.round import illustration_service

        monkeypatch.setattr(
            illustration_service.settings,
            "AUTO_GENERATE_ENTITY_IMAGES_FOR_SCENES",
            False,
        )

        mock_client = MagicMock()
        mock_client.analyze_story_for_illustration.return_value = (
            "会议室讨论",
            "陈晓雨在会议室里看向白板。",
        )
        mock_storage = MagicMock()
        mock_storage.save_image.return_value = ("1/round_scene/week_1_round_0_event.jpg", "local")
        mock_db = MagicMock()

        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=mock_storage,
            db_session=mock_db,
        )
        service._extract_involved_entities = MagicMock(
            return_value=[
                {
                    "name": "陈晓雨",
                    "type": "character",
                    "description": "产品团队导师",
                }
            ]
        )
        service._find_entity_image = MagicMock(return_value=None)
        service._generate_entity_image = MagicMock()
        service._generate_scene_image = MagicMock(return_value=(b"image-bytes", "final prompt"))

        service._generate_round_illustration_sync(
            game_id=1,
            round_number=0,
            story_text="陈晓雨把 AI 项目的排期写在会议室白板上。",
            character_settings={"era": {"era": "2020年代中国互联网"}},
            player_name="林舟",
            existing_images=[],
            stage="event",
            week=0,
        )

        service._generate_entity_image.assert_not_called()
        service._generate_scene_image.assert_called_once()
        mock_storage.save_image.assert_called_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_sync_generation_discards_stale_daily_revision_before_storage(self):
        mock_client = MagicMock()
        mock_client.analyze_story_for_illustration.return_value = (
            "雨夜码头",
            "主角站在码头旧仓库前。",
        )
        mock_storage = MagicMock()
        mock_db = MagicMock()
        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=mock_storage,
            db_session=mock_db,
        )
        service._generate_scene_image = MagicMock(
            return_value=(b"stale-image", "stale prompt")
        )

        service._generate_round_illustration_sync(
            game_id=1,
            round_number=0,
            story_text="已被改写替换的旧故事",
            character_settings={},
            player_name="林舟",
            existing_images=[],
            stage="event",
            week=0,
            story_date="2026-08-13",
            day_index=0,
            validity_callback=lambda: False,
        )

        mock_storage.save_image.assert_not_called()
        mock_db.add.assert_not_called()

    def test_sync_generation_content_error(self):
        """Test handling of ContentInspectionError."""
        mock_client = MagicMock()
        mock_client.analyze_story_for_illustration = MagicMock(
            side_effect=ContentInspectionError("Bad content")
        )

        mock_db = MagicMock()

        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=MagicMock(),
            db_session=mock_db,
        )

        # Should re-raise ContentInspectionError
        with pytest.raises(ContentInspectionError):
            service._generate_round_illustration_sync(
                game_id=1,
                round_number=1,
                story_text="Test",
                character_settings={},
                player_name="Player",
                existing_images=[],
            )

        # Should not add anything to DB
        mock_db.add.assert_not_called()

    def test_sync_generation_image_error(self):
        """Test handling of ImageGenerationError."""
        mock_client = MagicMock()
        mock_client.analyze_story_for_illustration = MagicMock(
            side_effect=ImageGenerationError("API error")
        )

        mock_db = MagicMock()

        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=MagicMock(),
            db_session=mock_db,
        )

        # Should re-raise ImageGenerationError
        with pytest.raises(ImageGenerationError):
            service._generate_round_illustration_sync(
                game_id=1,
                round_number=1,
                story_text="Test",
                character_settings={},
                player_name="Player",
                existing_images=[],
            )

        mock_db.add.assert_not_called()

    def test_sync_generation_unexpected_error(self):
        """Test handling of unexpected errors."""
        mock_client = MagicMock()
        mock_client.analyze_story_for_illustration = MagicMock(
            side_effect=RuntimeError("Unexpected")
        )

        mock_db = MagicMock()

        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=MagicMock(),
            db_session=mock_db,
        )

        # Should rollback and re-raise
        with pytest.raises(RuntimeError):
            service._generate_round_illustration_sync(
                game_id=1,
                round_number=1,
                story_text="Test",
                character_settings={},
                player_name="Player",
                existing_images=[],
            )

        mock_db.rollback.assert_called_once()


class TestAutoGenerateEntityImage:
    """Test auto-generating entity images."""

    def test_build_character_desc_from_key_people(self):
        """Test building character description."""
        mock_client = MagicMock()
        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        char_data = {
            "name": "张三",
            "age": 25,
            "gender": "男",
            "relationship_desc": "朋友",
        }
        desc = service._build_character_desc(char_data)
        assert "25岁" in desc
        assert "男" in desc
        assert "朋友" in desc

    def test_build_character_desc_from_family(self):
        """Test building character description from family member."""
        mock_client = MagicMock()
        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        char_data = {"name": "李四", "age": 30, "gender": "女", "relationship": "姐姐"}
        desc = service._build_character_desc(char_data)
        assert "30岁" in desc
        assert "女" in desc
        assert "姐姐" in desc

    def test_build_character_desc_empty(self):
        """Test building character description with empty data."""
        mock_client = MagicMock()
        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        desc = service._build_character_desc({})
        assert desc == "一个普通人"

    def test_extract_items_from_story_weapon(self):
        """Test extracting weapon items from story."""
        mock_client = MagicMock()
        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        items = service._extract_items_from_story("他手持一把青云剑，威风凛凛")
        assert len(items) >= 1
        assert items[0]["type"] == "item"
        assert "剑" in items[0]["name"]

    def test_extract_items_from_story_treasure(self):
        """Test extracting treasure items from story."""
        mock_client = MagicMock()
        service = RoundIllustrationService(
            image_client=mock_client,
            image_storage=MagicMock(),
            db_session=MagicMock(),
        )

        items = service._extract_items_from_story("她佩戴着一枚龙凤玉")
        assert len(items) >= 1
        assert items[0]["type"] == "item"
        assert "玉" in items[0]["name"]
