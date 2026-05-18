"""No-mock gate tests for lazy import paths touched by gameplay fixes."""

import importlib


def test_gameplay_lazy_import_paths_are_reachable() -> None:
    imports = [
        ("src.ai.consistency_validator", "ConsistencyValidator"),
        ("src.ai.option_generator", "OptionGenerator"),
        ("src.ai.quick_validator", "quick_validate_story"),
        ("src.ai.story_generator", "StoryGenerator"),
        ("src.game.round.event_generator", "RoundEventGenerator"),
        ("src.game.round.choice_processor", "RoundChoiceProcessor"),
        ("src.game.world_model", "WorldModel"),
        ("src.game.world_model_updater", "WorldModelUpdater"),
    ]

    for module_name, attr_name in imports:
        module = importlib.import_module(module_name)
        assert hasattr(module, attr_name), f"{module_name}.{attr_name} is not importable"


def test_scene_image_and_collection_lazy_import_paths_are_reachable() -> None:
    imports = [
        ("src.api.routers.images", "get_round_scene_image"),
        ("src.api.routers.images", "get_all_round_scene_images"),
        ("src.api.routers.collection", "get_collection"),
        ("src.database.models", "SceneImage"),
        ("src.database.models", "SessionLocal"),
        ("src.services.image_service", "ImageService"),
        ("src.services.image_storage", "ImageStorageService"),
    ]

    for module_name, attr_name in imports:
        module = importlib.import_module(module_name)
        assert hasattr(module, attr_name), f"{module_name}.{attr_name} is not importable"


def test_story_music_recommendation_import_paths_are_reachable() -> None:
    imports = [
        ("src.services.music_service", "MusicBrief"),
        ("src.services.music_service", "MusicContextBuilder"),
        ("src.services.music_service", "MusicResultRanker"),
        ("src.services.music_service", "MusicGenerationJob"),
        ("src.services.music_service", "MusicProviderPolicy"),
        ("src.services.music_service", "MusicGenerationCoordinator"),
        ("src.services.music_playlist_service", "PlaylistQueuePolicy"),
        ("src.services.music_playlist_service", "MusicPlaylistService"),
        ("src.database.models", "GeneratedMusicAsset"),
    ]

    for module_name, attr_name in imports:
        module = importlib.import_module(module_name)
        assert hasattr(module, attr_name), f"{module_name}.{attr_name} is not importable"


def test_story_voice_reading_import_paths_are_reachable() -> None:
    imports = [
        ("src.api.routers.voice_reading", "router"),
        ("src.api.routers.voice_reading", "request_story_reading"),
        ("src.services.story_voice_reading", "StoryVoiceReadingService"),
        ("src.services.story_voice_reading", "ReadingContextValidator"),
        ("src.services.story_voice_reading", "DeterministicTTSProvider"),
        ("src.services.story_tts_provider", "StoryTTSProvider"),
        ("src.services.story_tts_provider", "BrowserSpeechTTSProvider"),
        ("src.services.story_tts_provider", "OpenAICompatibleTTSProvider"),
        ("src.services.story_tts_provider", "build_story_tts_provider"),
        ("src.services.story_voice_repository", "StoryVoiceReadingRepository"),
        ("src.database.models", "VoiceReadingSetting"),
        ("src.database.models", "VoiceReadingJob"),
        ("src.database.models", "GeneratedVoiceAsset"),
    ]

    for module_name, attr_name in imports:
        module = importlib.import_module(module_name)
        assert hasattr(module, attr_name), f"{module_name}.{attr_name} is not importable"
