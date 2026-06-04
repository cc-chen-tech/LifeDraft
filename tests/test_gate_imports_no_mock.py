"""No-mock gate tests for lazy import paths touched by gameplay fixes."""

import ast
import importlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_minimax_websocket_runtime_dependency_is_available() -> None:
    module = importlib.import_module("websockets.sync.client")
    assert hasattr(module, "connect")


def test_minimax_async_tts_provider_does_not_require_websocket_at_import_time() -> None:
    source_path = PROJECT_ROOT / "src" / "services" / "minimax_story_tts_provider.py"
    tree = ast.parse(source_path.read_text())

    top_level_imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_imports.extend(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            top_level_imports.append(node.module)

    assert "websockets.sync.client" not in top_level_imports


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


def test_minimax_story_audio_generation_import_paths_are_reachable() -> None:
    imports = [
        ("src.services.minimax_config", "MiniMaxConfig"),
        ("src.services.minimax_config", "build_minimax_config"),
        ("src.services.minimax_story_tts_provider", "MiniMaxTTSProvider"),
        ("src.services.minimax_story_tts_provider", "MiniMaxWebSocketTTSClient"),
        ("src.services.minimax_music_generation", "MiniMaxMusicGenerationProvider"),
        ("src.services.minimax_music_generation", "MiniMaxMusicGenerationRequest"),
        ("src.services.minimax_music_generation", "StoryMusicGenerationService"),
        ("src.services.minimax_music_generation", "GeneratedMusicAssetRepository"),
    ]

    for module_name, attr_name in imports:
        module = importlib.import_module(module_name)
        assert hasattr(module, attr_name), f"{module_name}.{attr_name} is not importable"
