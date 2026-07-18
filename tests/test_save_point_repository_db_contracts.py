"""Real-database contracts for manual rewind save points."""

from src.database.models import Game, GameState, SessionLocal, User
from src.database.save_point_repository import SavePointRepository
from src.game.state import PlayerState


def _owned_game(player_name: str) -> tuple[int, int, int]:
    session = SessionLocal()
    try:
        sequence = session.query(User).count() + 1
        owner = User(
            private_id=f"save-point-owner-{sequence}",
            public_id=f"s{sequence:07d}",
            display_name=f"Save Point Owner {sequence}",
        )
        foreign_user = User(
            private_id=f"save-point-foreign-{sequence}",
            public_id=f"f{sequence:07d}",
            display_name=f"Save Point Foreign {sequence}",
        )
        session.add_all([owner, foreign_user])
        session.flush()
        game = Game(user_id=owner.user_id, language="zh", initial_state={"player_name": player_name})
        session.add(game)
        session.commit()
        return int(game.game_id), int(owner.user_id), int(foreign_user.user_id)
    finally:
        session.close()


def _add_automatic_snapshot(game_id: int, player_state: PlayerState) -> int:
    session = SessionLocal()
    try:
        snapshot = GameState(
            game_id=game_id,
            week=player_state.week,
            age=player_state.age,
            state_json=player_state.to_dict(),
            is_save_point=False,
        )
        session.add(snapshot)
        session.commit()
        return int(snapshot.state_id)
    finally:
        session.close()


def test_manual_save_point_is_distinct_from_automatic_timeline_snapshots() -> None:
    state = PlayerState(player_name="林岚", age=28, week=5, current_round=1)
    game_id, owner_id, _ = _owned_game(state.player_name)
    automatic_state_id = _add_automatic_snapshot(game_id, state)
    repository = SavePointRepository()

    save_point_id = repository.create_save_point(game_id, owner_id, state, "雨夜档案")

    assert save_point_id is not None
    save_points = repository.list_save_points(game_id, owner_id)
    assert save_points == [
        {
            "state_id": save_point_id,
            "game_id": game_id,
            "week": 5,
            "age": 28,
            "save_name": "雨夜档案",
            "created_at": save_points[0]["created_at"],
            "player_name": "林岚",
        }
    ]

    timeline = repository.get_all_states_for_game(game_id, owner_id)
    timeline_flags = {entry["state_id"]: entry["is_save_point"] for entry in timeline}
    assert timeline_flags[automatic_state_id] is False
    assert timeline_flags[save_point_id] is True


def test_save_point_load_and_delete_require_the_owner() -> None:
    state = PlayerState(player_name="周宁", age=31, week=7, current_round=2)
    game_id, owner_id, foreign_user_id = _owned_game(state.player_name)
    repository = SavePointRepository()
    save_point_id = repository.create_save_point(game_id, owner_id, state, "关键选择前")

    assert save_point_id is not None
    assert repository.load_save_point(save_point_id, foreign_user_id) is None
    assert repository.delete_save_point(save_point_id, foreign_user_id) is False

    loaded = repository.load_save_point(save_point_id, owner_id)
    assert loaded is not None
    assert loaded["_game_id"] == game_id
    assert loaded["player_name"] == "周宁"
    assert loaded["current_round"] == 2
    assert repository.delete_save_point(save_point_id, owner_id) is True
    assert repository.load_save_point(save_point_id, owner_id) is None
