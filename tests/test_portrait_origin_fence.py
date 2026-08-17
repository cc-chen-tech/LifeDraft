"""A portrait worker must not publish results for an obsolete origin revision."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import Base, Game, PortraitImageGenerationJob, User
from src.services.portrait_image_jobs import run_portrait_image_job
import pytest

pytestmark = [pytest.mark.unit]



def test_worker_discards_job_from_an_obsolete_origin_revision():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    user = User(private_id="PORTRAIT-FENCE", public_id="PRTFNC01")
    db.add(user)
    db.commit()
    game = Game(
        user_id=user.user_id,
        initial_state={
            "character_settings": {
                "story_origin": {
                    "revision": 2,
                    "start_date": "2026-08-13",
                    "starting_age": 28,
                    "era_description": "现代都市",
                    "life_stage_description": "职业探索期",
                    "world_context": "AI行业快速变化",
                }
            }
        },
    )
    db.add(game)
    db.commit()
    job = PortraitImageGenerationJob(
        game_id=game.game_id,
        user_id=user.user_id,
        entity_key="player_main",
        status="queued",
        request_json={
            "game_id": game.game_id,
            "entity_name": "阿衡",
            "description": "20岁女性",
            "era": "北宋",
            "origin_revision": 1,
        },
    )
    db.add(job)
    db.commit()
    job_id = int(job.job_id)
    db.close()

    called = False

    class _UnexpectedImageService:
        def __init__(self, _db):
            nonlocal called
            called = True

    run_portrait_image_job(
        job_id,
        session_factory=Session,
        image_service_factory=_UnexpectedImageService,
    )

    verify = Session()
    stored = verify.get(PortraitImageGenerationJob, job_id)
    assert called is False
    assert stored.status == "failed"
    assert stored.error_code == "story_origin_superseded"
    verify.close()
    engine.dispose()
