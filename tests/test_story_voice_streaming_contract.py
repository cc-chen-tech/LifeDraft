"""TDD contracts for scene-first story narration playback."""

from uuid import uuid4

from src.api.schemas import StoryVoiceReadingRequest
from src.database.models import SessionLocal, User, VoiceReadingJob, init_db
from src.services.story_tts_provider import GeneratedSpeech, ParagraphCue, StoryTTSProviderMetadata
from src.services.story_voice_reading import StoryVoiceReadingService, normalize_text_hash
from src.services.story_voice_repository import StoryVoiceReadingRepository


def test_scene_capable_provider_exposes_first_segment_before_chapter_finishes() -> None:
    init_db()
    session = SessionLocal()
    try:
        user = User(
            private_id=f"priv_{uuid4().hex[:16]}",
            public_id=f"pub_{uuid4().hex[:8]}",
            display_name="Streaming Voice",
        )
        session.add(user)
        session.flush()
        first_visible = {"value": False}
        scene_contexts = []
        scene_speeds = []

        class SceneProvider:
            provider = "minimax"
            model = "speech-2.8-turbo"

            def metadata(self) -> StoryTTSProviderMetadata:
                return StoryTTSProviderMetadata(
                    provider=self.provider,
                    model=self.model,
                    playback_mode="audio",
                    media_type="audio/mpeg",
                    available=True,
                    backend_audio_enabled=True,
                )

            def synthesize_scene(self, context, voice_id, speed, on_progress=None):
                scene_contexts.append(dict(context))
                scene_speeds.append(speed)
                if context["text"].startswith("第二场"):
                    observer = SessionLocal()
                    try:
                        job = observer.query(VoiceReadingJob).order_by(VoiceReadingJob.job_id.desc()).first()
                        first_visible["value"] = bool(
                            job
                            and job.status == "processing"
                            and job.segments[0].status == "ready"
                            and job.segments[0].asset is not None
                        )
                    finally:
                        observer.close()
                return GeneratedSpeech(
                    storage_path=f"/api/voice-reading/audio/scene-{context['text_hash']}.mp3",
                    duration_ms=1_000,
                    provider=self.provider,
                    model=self.model,
                    media_type="audio/mpeg",
                    playback_mode="audio",
                    paragraph_cues=(ParagraphCue(0, 0, 1_000),),
                )

            def synthesize(self, context, voice_id, speed, on_progress=None):
                return GeneratedSpeech(
                    storage_path="/api/voice-reading/audio/chapter-final.mp3",
                    duration_ms=2_000,
                    provider=self.provider,
                    model=self.model,
                    media_type="audio/mpeg",
                    playback_mode="audio",
                    paragraph_cues=(ParagraphCue(0, 0, 1_000), ParagraphCue(1, 1_000, 2_000)),
                )

        text = "第一场已经开始。\n\n第二场还在后台生成。"
        context = {
            "source_type": "current_story",
            "game_id": 991,
            "week": 1,
            "round_number": 1,
            "stage": "event",
            "text_hash": normalize_text_hash(text),
            "text": text,
            "narration_plan": {
                "segments": [
                    {
                        "paragraph_index": 0,
                        "emotion": "calm",
                        "speed": 1.0,
                        "pause_after_ms": 400,
                        "vocal_cue": "",
                    },
                    {
                        "paragraph_index": 1,
                        "emotion": "fearful",
                        "speed": 0.9,
                        "pause_after_ms": 0,
                        "vocal_cue": "(whispers)",
                    },
                ],
                "source": "story-model",
            },
        }
        service = StoryVoiceReadingService(
            StoryVoiceReadingRepository(session), provider=SceneProvider()
        )
        queued = service.request_reading(
            int(user.user_id),
            StoryVoiceReadingRequest(context=context, voice_id="warm_female", speed=1.0),
        )

        response = service.process_job(int(user.user_id), int(queued.job_id))

        assert first_visible["value"] is True
        assert [scene["emotion"] for scene in scene_contexts] == ["calm", "fearful"]
        assert scene_speeds == [1.0, 0.9]
        assert scene_contexts[1]["speed"] == 0.9
        assert scene_contexts[1]["vocal_cue"] == "(whispers)"
        assert response.status == "ready"
        assert [segment.status for segment in response.segments] == ["ready", "ready"]
        assert response.audio_url == "/api/voice-reading/audio/chapter-final.mp3"
    finally:
        session.rollback()
        session.close()
