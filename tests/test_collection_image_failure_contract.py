"""HTTP contracts for provider failures in collection image actions."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.image_exceptions import ImageProviderError
from src.api.deps import get_current_user_optional
from src.api.routers.collection import router
from src.api.routers.image_failures import image_failure_http_exception
from src.services.image import ImageServiceError as package_error
from src.services.image.character_service import CharacterImageService
from src.services.image_service import (ImageProviderServiceError,
                                        ImageService,
                                        ImageServiceError as facade_error)

pytestmark = pytest.mark.api


def capacity_service_error() -> ImageProviderServiceError:
    return ImageProviderServiceError.from_provider(
        ImageProviderError(
            code="minimax_2056",
            category="capacity",
            retryable=False,
            public_message="图片生成额度暂时不可用，请稍后再试",
        )
    )


def test_image_service_uses_one_exception_identity():
    assert facade_error is package_error


def test_character_service_preserves_provider_failure_fields():
    image_client = MagicMock()
    image_client.generate_appearance_anchor.return_value = {}
    provider_error = ImageProviderError(
        code="minimax_2056",
        category="capacity",
        retryable=False,
        public_message="图片生成额度暂时不可用，请稍后再试",
    )
    image_client.generate_character_images.side_effect = provider_error
    service = CharacterImageService(
        MagicMock(),
        image_client=image_client,
        storage_service=MagicMock(),
    )

    with pytest.raises(ImageProviderServiceError) as raised:
        service.generate_character_image(1, "林见微", "现代职场人物")

    assert raised.value.code == "minimax_2056"
    assert raised.value.category == "capacity"
    assert raised.value.retryable is False


def test_location_service_preserves_provider_failure_fields():
    image_client = MagicMock()
    image_client.generate_location_image.side_effect = ImageProviderError(
        code="minimax_2056",
        category="capacity",
        retryable=False,
        public_message="图片生成额度暂时不可用，请稍后再试",
    )
    service = ImageService(
        MagicMock(),
        image_client=image_client,
        storage_service=MagicMock(),
    )

    with pytest.raises(ImageProviderServiceError) as raised:
        service.generate_location_image(1, "车站", "城市车站")

    assert raised.value.code == "minimax_2056"


def test_invalid_request_provider_failure_maps_to_structured_422():
    service_error = ImageProviderServiceError.from_provider(
        ImageProviderError(
            code="minimax_2013",
            category="invalid_request",
            retryable=False,
            public_message="图片生成参数无效，请调整后重试",
            provider_trace_id="trace-safe-1",
        )
    )

    error = image_failure_http_exception(service_error)

    assert error.status_code == 422
    assert error.detail == {
        "code": "minimax_2013",
        "message": "图片生成参数无效，请调整后重试",
        "retryable": False,
        "provider_trace_id": "trace-safe-1",
    }


def test_collection_character_capacity_failure_returns_same_503():
    app = FastAPI()
    app.include_router(router, prefix="/collection")
    app.dependency_overrides[get_current_user_optional] = lambda: 1

    with (
        patch("src.api.routers.collection._get_player_state") as get_state,
        patch("src.api.routers.collection.SessionLocal") as session_local,
        patch("src.api.routers.collection.CollectionService") as service_class,
    ):
        get_state.return_value = (MagicMock(), MagicMock())
        session_local.return_value = MagicMock()
        service_class.return_value.generate_character_image.side_effect = (
            capacity_service_error()
        )

        response = TestClient(app, raise_server_exceptions=False).post(
            "/collection/1/characters/林见微/generate-image"
        )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "minimax_2056",
        "message": "图片生成额度暂时不可用，请稍后再试",
        "retryable": False,
    }
