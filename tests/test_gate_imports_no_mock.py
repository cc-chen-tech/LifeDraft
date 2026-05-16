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
        ("src.services.music_service", "MusicProviderPolicy"),
        ("src.services.music_service", "MusicGenerationCoordinator"),
        ("src.services.music_playlist_service", "MusicPlaylistService"),
        ("src.database.models", "GeneratedMusicAsset"),
    ]

    for module_name, attr_name in imports:
        module = importlib.import_module(module_name)
        assert hasattr(module, attr_name), f"{module_name}.{attr_name} is not importable"
