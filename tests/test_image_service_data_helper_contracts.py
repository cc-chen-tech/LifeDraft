"""No-provider contracts for ImageService data normalization helpers."""

from src.database.models import Game, GameState
from src.services.image_service import ImageService


def _service(db_session) -> ImageService:
    service = ImageService.__new__(ImageService)
    service.db = db_session
    return service


def test_prompt_description_and_metadata_era_fallbacks(db_session):
    service = _service(db_session)

    assert service._extract_description_from_prompt("人物描述：年轻画师。其余约束") == "年轻画师"
    assert service._extract_description_from_prompt("plain prompt") == "plain prompt"
    assert service._extract_era_from_metadata({"era": "民国"}) == "民国"
    assert service._extract_era_from_metadata(None) == "现代"


def test_character_settings_normalize_structured_and_legacy_fields(db_session):
    service = _service(db_session)
    settings = {
        "age": {"age": 28, "age_range": "25-30岁"},
        "gender": {"gender": "女性"},
        "world": {"cultural_context": "海港城市", "special_features": "常年多雨"},
        "era": {"era_description": "1920年代上海。报馆林立。"},
    }

    assert service._build_description_from_settings(settings) == "28岁，女性，海港城市，常年多雨"
    assert service._extract_era_from_settings(settings) == "1920年代上海"
    assert service._build_char_info(settings, "沈青") == {
        "name": "沈青",
        "era": "1920年代上海",
        "gender": "女性",
        "age": 28,
    }


def test_current_week_prefers_latest_saved_state_then_initial_state(db_session):
    service = _service(db_session)
    game = Game(language="zh", initial_state={"week": 2})
    db_session.add(game)
    db_session.commit()
    db_session.add(GameState(game_id=game.game_id, week=7, age=26, state_json={"week": 7}))
    db_session.commit()

    assert service._get_current_week_from_db(int(game.game_id)) == 7
    assert service._get_current_week_from_db(999999) == 0
