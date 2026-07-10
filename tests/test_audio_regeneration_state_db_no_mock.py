"""Real DB round-trip for a non-default selected voice."""

from uuid import uuid4

from src.database.models import SessionLocal, User, init_db
from src.services.story_voice_repository import StoryVoiceReadingRepository


def test_clear_neutral_voice_survives_real_settings_save_read() -> None:
    init_db()
    session = SessionLocal()
    try:
        suffix = uuid4().hex[:10]
        user = User(
            private_id=f"audio-state-{suffix}",
            public_id=f"AS{suffix[:6].upper()}",
            display_name="音频状态测试",
        )
        session.add(user)
        session.flush()
        repository = StoryVoiceReadingRepository(session)
        repository.upsert_settings(
            user_id=int(user.user_id),
            selected_voice_color="clear_neutral",
            auto_read_enabled=True,
        )
        session.commit()
        session.expire_all()

        loaded = repository.get_settings(int(user.user_id))

        assert loaded is not None
        assert loaded.selected_voice_color == "clear_neutral"
        assert loaded.auto_read_enabled is True
    finally:
        session.rollback()
        session.close()

