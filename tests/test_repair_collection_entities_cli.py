"""Operator contracts for the collection entity repair CLI."""

import json

import pytest
from sqlalchemy.orm import sessionmaker

from scripts.repair_collection_entities import build_report
from src.database.models import Game, GameState
from src.game.state import PlayerState

pytestmark = pytest.mark.unit


def test_collection_repair_report_is_read_only_and_hashable(db_engine) -> None:
    sessions = sessionmaker(bind=db_engine)
    state = PlayerState(
        player_name="唐三藏",
        characters={"金箍棒": {"name": "金箍棒"}},
        day_history=[
            {
                "event_id": "day-1",
                "day_index": 0,
                "event_description": "花果山有金箍棒。",
            }
        ],
    )
    with sessions() as db:
        game = Game(language="zh", initial_state={})
        db.add(game)
        db.flush()
        db.add(
            GameState(
                game_id=game.game_id, week=0, age=25, state_json=state.model_dump()
            )
        )
        db.commit()
        game_id = int(game.game_id)

        report = build_report(db, game_id)
        assert report["would_change"] is True
        assert report["report_hash"]
        assert report["candidates"][0]["detail"]["removed_characters"] == ["金箍棒"]

        db.expire_all()
        row = db.query(GameState).filter(GameState.game_id == game_id).one()
        assert "金箍棒" in row.state_json["characters"]

    json.dumps(report, ensure_ascii=False)
