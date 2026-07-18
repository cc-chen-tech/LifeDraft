"""Real database contracts for active-game recovery ownership."""

from uuid import uuid4

from src.database.models import Game, SessionLocal, User, init_db
from src.database.session_repository import SessionRepository


def test_cross_user_active_game_pointer_is_rejected_and_cleared_durably() -> None:
    """A stale pointer must not restore another user's game session."""
    init_db()
    suffix = uuid4().hex[:10]
    session = SessionLocal()
    user_ids = []
    game_id = None

    try:
        owner = User(
            private_id="active-owner-{}".format(suffix),
            public_id="AO{}".format(suffix[:6]),
            display_name="Active Game Owner",
        )
        intruder = User(
            private_id="active-intruder-{}".format(suffix),
            public_id="AI{}".format(suffix[:6]),
            display_name="Active Game Intruder",
        )
        session.add_all([owner, intruder])
        session.flush()
        user_ids = [int(owner.user_id), int(intruder.user_id)]

        game = Game(user_id=owner.user_id, language="zh", initial_state={"week": 1})
        session.add(game)
        session.flush()
        game_id = int(game.game_id)

        # Model a stale persisted pointer written before ownership validation.
        intruder.last_active_game_id = game_id
        session.commit()

        assert SessionRepository().get_active_game(int(intruder.user_id)) is None

        session.expire_all()
        recovered_user = session.query(User).filter(User.user_id == intruder.user_id).one()
        assert recovered_user.last_active_game_id is None
    finally:
        session.rollback()
        if user_ids:
            session.query(User).filter(User.user_id.in_(user_ids)).update(
                {User.last_active_game_id: None},
                synchronize_session=False,
            )
        if game_id is not None:
            session.query(Game).filter(Game.game_id == game_id).delete(synchronize_session=False)
        if user_ids:
            session.query(User).filter(User.user_id.in_(user_ids)).delete(synchronize_session=False)
        session.commit()
        session.close()
