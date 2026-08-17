"""Real database collection field and image-version contracts."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.database.models import Game, Image, SessionLocal, User, init_db
from src.game.state import PlayerState
from src.services.collection_service import CollectionService, EntityNotFoundError
from src.services.image_storage import ImageStorageService

pytestmark = [pytest.mark.integration]



def _image(game_id, image_type, entity_name, path, active, created_at):
    return Image(game_id=game_id, image_type=image_type, entity_name=entity_name, prompt_text="test", storage_path=path, storage_type="local", is_active=active, created_at=created_at)


def test_collection_fields_use_owned_latest_active_images_and_preserve_lifecycle_data():
    init_db()
    suffix = uuid4().hex[:12]
    db = SessionLocal()
    game_id = foreign_game_id = owner_id = intruder_id = None
    try:
        owner = User(private_id=f"collection-owner-{suffix}", public_id=f"COL{suffix[:7]}", display_name="Collection Owner")
        intruder = User(private_id=f"collection-intruder-{suffix}", public_id=f"INTR{suffix[:6]}", display_name="Collection Intruder")
        db.add_all([owner, intruder]); db.flush()
        owner_id, intruder_id = int(owner.user_id), int(intruder.user_id)
        game = Game(user_id=owner_id, language="zh", initial_state={})
        foreign_game = Game(user_id=intruder_id, language="zh", initial_state={})
        db.add_all([game, foreign_game]); db.flush()
        game_id, foreign_game_id = int(game.game_id), int(foreign_game.game_id)
        now = datetime.utcnow()
        image_root = ImageStorageService().local_path
        db.add_all([
            _image(game_id, "character", "林舟", str(image_root / str(game_id) / "character" / "old.png"), False, now - timedelta(minutes=2)),
            _image(game_id, "character", "林舟", str(image_root / str(game_id) / "character" / "current.png"), True, now),
            _image(game_id, "item", "铜制令牌", str(image_root / str(game_id) / "item" / "token.png"), True, now),
            _image(foreign_game_id, "character", "林舟", str(image_root / str(foreign_game_id) / "character" / "foreign.png"), True, now + timedelta(seconds=1)),
        ])
        db.commit()

        state = PlayerState(player_name="林舟", character_settings={"age": {"age": 29}, "gender": {"gender": "男"}, "occupation": {"occupation": "记者"}}, items={"铜制令牌": {"description": "旧仓库的钥匙线索", "importance": "critical", "category": "keepsake", "acquired_week": 4, "acquired_context": "雨夜仓库", "is_key_item": True, "description_generated": True, "metadata": {"source": "round-story"}}}, landmarks={"旧码头": {"description": "第一次交易的地点", "category": "area", "importance": "important", "first_appear_week": 2, "appear_count": 3, "last_appear_week": 4, "context": "与线人会面", "is_key_location": True, "metadata": {"district": "港区"}}})
        result = CollectionService(db).get_collection(game_id, state)

        assert (result.total_characters, result.total_items, result.total_landmarks) == (1, 1, 1)
        character, item, landmark = result.characters[0], result.items[0], result.landmarks[0]
        assert (character.age, character.gender, character.occupation) == (29, "男", "记者")
        assert character.image_url == f"/api/images/file/{game_id}/character/current.png"
        assert character.image_generated is True
        assert item.model_dump() == {"name": "铜制令牌", "description": "旧仓库的钥匙线索", "importance": "critical", "category": "keepsake", "acquired_week": 4, "acquired_context": "雨夜仓库", "is_key_item": True, "image_url": f"/api/images/file/{game_id}/item/token.png", "image_generated": True, "description_generated": True, "metadata": {"source": "round-story"}}
        assert landmark.model_dump() == {"name": "旧码头", "description": "第一次交易的地点", "category": "area", "importance": "important", "first_appear_week": 2, "appear_count": 3, "last_appear_week": 4, "context": "与线人会面", "is_key_location": True, "image_url": None, "image_generated": False, "metadata": {"district": "港区"}}
        with pytest.raises(EntityNotFoundError):
            CollectionService(db).verify_game_ownership(game_id, intruder_id)
    finally:
        db.rollback()
        for candidate_game_id in (game_id, foreign_game_id):
            if candidate_game_id is not None:
                db.query(Image).filter(Image.game_id == candidate_game_id).delete()
                db.query(Game).filter(Game.game_id == candidate_game_id).delete()
        for user_id in (owner_id, intruder_id):
            if user_id is not None:
                db.query(User).filter(User.user_id == user_id).delete()
        db.commit(); db.close()
