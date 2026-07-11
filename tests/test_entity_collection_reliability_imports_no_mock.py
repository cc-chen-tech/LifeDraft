"""Import verification for entity collection reliability paths."""


def test_entity_collection_reliability_paths_are_reachable() -> None:
    from src.api.routers.collection import add_entities
    from src.services.collection_service import CollectionService
    from src.services.entity_recognition_service import EntityRecognitionService

    assert callable(add_entities)
    assert callable(CollectionService.add_entities)
    assert callable(EntityRecognitionService._first_context)
    assert callable(EntityRecognitionService._supplement_with_story_entities)
