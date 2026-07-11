"""Import reachability for audio regeneration state paths."""


def test_audio_regeneration_backend_paths_are_reachable() -> None:
    from src.api.routers.voice_reading import get_voice_reading_settings
    from src.services.story_voice_reading import StoryVoiceReadingService
    from src.services.story_voice_repository import StoryVoiceReadingRepository

    assert callable(get_voice_reading_settings)
    assert callable(StoryVoiceReadingService.get_settings)
    assert callable(StoryVoiceReadingRepository.upsert_settings)

