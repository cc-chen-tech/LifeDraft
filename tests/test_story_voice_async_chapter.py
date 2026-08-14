from __future__ import annotations

from threading import Barrier, Event, Thread
from uuid import uuid4

from src.api.schemas import StoryVoiceReadingRequest
from src.database.models import GeneratedVoiceAsset, SessionLocal, User, VoiceReadingJob, init_db
from src.services.story_tts_provider import DeterministicTTSProvider
from src.services.story_voice_reading import StoryVoiceReadingService, normalize_text_hash
from src.services.story_voice_repository import StoryVoiceReadingRepository


def _request(text: str) -> StoryVoiceReadingRequest:
    return StoryVoiceReadingRequest(
        context={
            "source_type": "current_story",
            "game_id": 777,
            "week": 3,
            "round_number": 4,
            "stage": "event",
            "attempt_id": "async-chapter",
            "day_index": 12,
            "story_date": "2026-08-15",
            "text_hash": normalize_text_hash(text),
            "text": text,
        },
        voice_id="clear_neutral",
        speed=1.0,
    )


def test_chapter_request_is_idempotent_and_processes_ordered_paragraph_audio() -> None:
    init_db()
    session = SessionLocal()
    try:
        user = User(
            private_id=f"async-{uuid4().hex[:20]}",
            public_id=f"A{uuid4().hex[:7]}",
            display_name="Async listener",
        )
        session.add(user)
        session.flush()
        user_id = int(user.user_id)
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session),
            provider=DeterministicTTSProvider(),
        )
        request = _request("第一段完整故事。\n\n第二段继续故事。")

        queued = service.request_reading(user_id, request)
        duplicate = service.request_reading(user_id, request)

        assert queued.status == "queued"
        assert duplicate.job_id == queued.job_id
        assert [segment.paragraph_index for segment in queued.segments] == [0, 1]
        assert [segment.status for segment in queued.segments] == ["queued", "queued"]
        assert session.query(GeneratedVoiceAsset).filter_by(user_id=user_id).count() == 0
        assert session.query(VoiceReadingJob).filter_by(user_id=user_id).count() == 1

        service.process_job(user_id, queued.job_id)
        ready = service.get_job(user_id, queued.job_id)

        assert ready.status == "ready"
        assert [segment.status for segment in ready.segments] == ["ready", "ready"]
        assert all(segment.audio_url for segment in ready.segments)
        assert session.query(GeneratedVoiceAsset).filter_by(user_id=user_id).count() == 2
    finally:
        session.rollback()
        session.close()


def test_failed_segment_marks_chapter_failed_without_browser_audio() -> None:
    class FailingProvider(DeterministicTTSProvider):
        def synthesize(self, context, voice_id, speed):
            raise RuntimeError("provider timeout")

    init_db()
    session = SessionLocal()
    try:
        user = User(
            private_id=f"fail-{uuid4().hex[:20]}",
            public_id=f"F{uuid4().hex[:7]}",
            display_name="Failed listener",
        )
        session.add(user)
        session.flush()
        user_id = int(user.user_id)
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session),
            provider=FailingProvider(),
        )

        queued = service.request_reading(user_id, _request("失败也不能降级。"))
        service.process_job(user_id, queued.job_id)
        failed = service.get_job(user_id, queued.job_id)

        assert failed.status == "failed"
        assert failed.playback_mode == "unavailable"
        assert failed.error_code == "tts_generation_failed"
        assert failed.segments[0].status == "failed"
        assert failed.segments[0].audio_url is None
    finally:
        session.rollback()
        session.close()


def test_first_paragraph_is_visible_while_later_paragraphs_prefetch() -> None:
    second_started = Event()
    release_second = Event()

    class BlockingSecondParagraphProvider(DeterministicTTSProvider):
        calls = 0

        def synthesize(self, context, voice_id, speed):
            self.calls += 1
            if self.calls == 2:
                second_started.set()
                assert release_second.wait(timeout=5)
            return super().synthesize(context, voice_id, speed)

    init_db()
    setup_session = SessionLocal()
    worker_errors: list[BaseException] = []
    try:
        user = User(
            private_id=f"prefetch-{uuid4().hex[:20]}",
            public_id=f"P{uuid4().hex[:7]}",
            display_name="Prefetch listener",
        )
        setup_session.add(user)
        setup_session.flush()
        user_id = int(user.user_id)
        provider = BlockingSecondParagraphProvider()
        queued = StoryVoiceReadingService(
            StoryVoiceReadingRepository(setup_session), provider=provider
        ).request_reading(user_id, _request("首段可先播放。\n\n第二段仍在生成。"))
        setup_session.commit()

        def process() -> None:
            worker_session = SessionLocal()
            try:
                StoryVoiceReadingService(
                    StoryVoiceReadingRepository(worker_session), provider=provider
                ).process_job(user_id, queued.job_id)
            except BaseException as error:  # pragma: no cover - surfaced below
                worker_errors.append(error)
            finally:
                worker_session.close()

        worker = Thread(target=process)
        worker.start()
        assert second_started.wait(timeout=5)

        observer = SessionLocal()
        try:
            partial = StoryVoiceReadingService(
                StoryVoiceReadingRepository(observer), provider=provider
            ).get_job(user_id, queued.job_id)
            assert partial.status == "processing"
            assert partial.segments[0].status == "ready"
            assert partial.segments[0].audio_url
            assert partial.segments[1].status in {"queued", "processing"}
            assert partial.segments[1].audio_url is None
        finally:
            observer.close()

        release_second.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert worker_errors == []
    finally:
        release_second.set()
        setup_session.close()


def test_failed_chapter_retry_reuses_the_same_job_and_can_recover() -> None:
    class RecoveringProvider(DeterministicTTSProvider):
        should_fail = True

        def synthesize(self, context, voice_id, speed):
            if self.should_fail:
                raise RuntimeError("temporary provider failure")
            return super().synthesize(context, voice_id, speed)

    init_db()
    session = SessionLocal()
    try:
        user = User(
            private_id=f"retry-{uuid4().hex[:20]}",
            public_id=f"T{uuid4().hex[:7]}",
            display_name="Retry listener",
        )
        session.add(user)
        session.flush()
        user_id = int(user.user_id)
        provider = RecoveringProvider()
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session), provider=provider
        )
        request = _request("暂时失败的章节可以重试。")

        queued = service.request_reading(user_id, request)
        failed = service.process_job(user_id, queued.job_id)
        provider.should_fail = False
        retried = service.request_reading(user_id, request)
        ready = service.process_job(user_id, retried.job_id)

        assert failed.status == "failed"
        assert retried.job_id == queued.job_id
        assert retried.status == "queued"
        assert ready.status == "ready"
        assert ready.segments[0].audio_url
    finally:
        session.close()


def test_concurrent_identical_requests_converge_on_one_chapter_job() -> None:
    init_db()
    setup_session = SessionLocal()
    try:
        user = User(
            private_id=f"concurrent-{uuid4().hex[:20]}",
            public_id=f"C{uuid4().hex[:7]}",
            display_name="Concurrent listener",
        )
        setup_session.add(user)
        setup_session.commit()
        user_id = int(user.user_id)
    finally:
        setup_session.close()

    barrier = Barrier(2)
    job_ids: list[int] = []
    errors: list[BaseException] = []
    request = _request("并发请求也只创建一个章节任务。\n\n缓存键必须稳定。")

    def submit() -> None:
        session = SessionLocal()
        try:
            barrier.wait(timeout=5)
            response = StoryVoiceReadingService(
                StoryVoiceReadingRepository(session), provider=DeterministicTTSProvider()
            ).request_reading(user_id, request)
            session.commit()
            job_ids.append(response.job_id)
        except BaseException as error:  # pragma: no cover - surfaced below
            errors.append(error)
        finally:
            session.close()

    workers = [Thread(target=submit), Thread(target=submit)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=8)

    assert all(not worker.is_alive() for worker in workers)
    assert errors == []
    assert len(job_ids) == 2
    assert len(set(job_ids)) == 1

    observer = SessionLocal()
    try:
        assert observer.query(VoiceReadingJob).filter_by(user_id=user_id).count() == 1
    finally:
        observer.close()
