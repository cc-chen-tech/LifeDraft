from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from src.api.services.session_service import SessionService


class _FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)
        self.deleted = 0

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *_):
        return self

    def delete(self):
        self.deleted += len(self.rows)
        return self.deleted


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.commit_count = 0
        self.closed = False

    def query(self, model):
        return _FakeQuery(self.rows)

    def commit(self):
        self.commit_count += 1

    def close(self):
        self.closed = True


class _Storage:
    def __init__(self, exists=True, exists_by_path=None):
        self.exists = exists
        self.exists_by_path = exists_by_path

    def image_exists(self, *_):
        if len(_) < 1:
            return False
        path = _[0]
        if self.exists_by_path is not None:
            return self.exists_by_path.get(path, self.exists)
        return self.exists


class TestSessionServiceEraExtraction:
    """Era extraction contracts in session service."""

    def test_extract_era_prefers_era_name(self):
        service = SessionService()

        era = service._extract_era_from_settings({"era": {"era_name": "唐朝", "era_description": "大唐"}})

        assert era == "唐朝"

    def test_extract_era_uses_description_when_name_missing(self):
        service = SessionService()

        era = service._extract_era_from_settings(
            {"era": {"era_description": "宋朝，经济繁荣时期，商贸发展", "era_name": ""}}
        )

        assert era == "宋朝"

    def test_extract_era_truncates_long_string(self):
        service = SessionService()

        era = service._extract_era_from_settings(
            {"era": "这是一个非常非常非常非常非常非常非常非常非常非常长的时代描述"}
        )

        assert len(era) <= 30
        assert era == era[:30]

    def test_extract_era_none_when_unusable(self):
        service = SessionService()

        assert service._extract_era_from_settings({}) is None
        assert service._extract_era_from_settings({"era": 123}) is None


class TestSessionServiceImageHealthContracts:
    """Image health and regeneration contracts."""

    def test_check_character_images_missing_files_triggers_regen(self):
        img = MagicMock()
        img.storage_path = "/tmp/missing.png"
        img.storage_type = "local"
        img.image_id = 11
        img.image_type = "character"
        img.entity_name = "主角"
        img.entity_key = "pc_main"
        img.is_active = True

        db = _FakeDb([img])
        service = SessionService()

        with patch.object(service, "_trigger_character_image_regeneration") as regen:
            service._check_character_images(
                db=db,
                game_id=88,
                player_state=MagicMock(),
                image_storage=_Storage(exists=False),
                character_settings={"era": "现代"},
            )

        assert img.is_active is False
        assert db.commit_count == 1
        assert regen.call_count == 1
        assert regen.call_args.kwargs["game_id"] == 88
        assert regen.call_args.kwargs["missing_images"] == [img]

    def test_check_character_images_with_existing_files_no_regen(self):
        img = MagicMock()
        img.storage_path = "/tmp/exists.png"
        img.storage_type = "local"
        img.image_type = "character"
        img.entity_name = "主角"
        img.image_id = 11
        img.is_active = True

        db = _FakeDb([img])
        service = SessionService()

        with patch.object(service, "_trigger_character_image_regeneration") as regen:
            service._check_character_images(
                db=db,
                game_id=88,
                player_state=MagicMock(),
                image_storage=_Storage(exists=True),
                character_settings={},
            )

        assert img.is_active is True
        assert db.commit_count == 0
        regen.assert_not_called()

    def test_check_recent_scene_images_marks_missing_scene_images(self):
        scene_ok = SimpleNamespace(
            scene_id=1,
            week=2,
            round_number=0,
            stage="event",
            storage_path="/tmp/exist.png",
            storage_type="local",
            importance_score="high",
        )
        scene_missing = SimpleNamespace(
            scene_id=2,
            week=2,
            round_number=1,
            stage="event",
            storage_path="/tmp/missing.png",
            storage_type="local",
            importance_score="high",
        )
        db = _FakeDb([scene_ok, scene_missing])
        service = SessionService()

        storage = _Storage(exists_by_path={"/tmp/exist.png": True, "/tmp/missing.png": False})
        service._check_recent_scene_images(db=db, game_id=88, player_state=MagicMock(), image_storage=storage)

        assert scene_missing.importance_score == "missing"
        assert scene_ok.importance_score == "high"
        assert db.commit_count == 1

    def test_check_and_generate_illustration_triggers_regen_when_missing(self):
        service = SessionService()
        db = _FakeDb([])

        with patch.object(service, "_trigger_illustration_generation") as regen:
            service._check_and_generate_illustration(
                db=db,
                game_id=88,
                week=7,
                round_number=1,
                stage="event",
                story_text="第一幕故事",
                character_settings={},
                player_name="主角",
                image_storage=_Storage(exists=False),
            )

        regen.assert_called_once_with(
            game_id=88,
            week=7,
            round_number=1,
            stage="event",
            story_text="第一幕故事",
            character_settings={},
            player_name="主角",
        )

    def test_check_and_generate_illustration_skips_when_existing_and_file_ok(self):
        service = SessionService()
        existing = SimpleNamespace(importance_score="high", storage_path="/tmp/exist.png", storage_type="local")
        db = _FakeDb([existing])

        with patch.object(service, "_trigger_illustration_generation") as regen:
            service._check_and_generate_illustration(
                db=db,
                game_id=88,
                week=7,
                round_number=1,
                stage="event",
                story_text="第一幕故事",
                character_settings={},
                player_name="主角",
                image_storage=_Storage(exists=True),
            )

        assert regen.call_count == 0

    def test_check_and_generate_illustration_marks_missing_file_before_regen(self):
        service = SessionService()
        existing = SimpleNamespace(
            scene_id=3,
            importance_score="high",
            storage_path="/tmp/missing.png",
            storage_type="local",
        )
        db = _FakeDb([existing])

        with patch.object(service, "_trigger_illustration_generation") as regen:
            service._check_and_generate_illustration(
                db=db,
                game_id=88,
                week=7,
                round_number=1,
                stage="event",
                story_text="第一幕故事",
                character_settings={},
                player_name="主角",
                image_storage=_Storage(exists_by_path={"/tmp/missing.png": False}),
            )

        assert existing.importance_score == "missing"
        assert db.commit_count == 1
        assert regen.call_count == 1
