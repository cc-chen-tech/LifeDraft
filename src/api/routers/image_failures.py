"""Safe HTTP representation for typed image-provider failures."""

from typing import Dict

from fastapi import HTTPException

from src.services.image_service import ImageProviderServiceError


def public_image_failure(error: ImageProviderServiceError) -> Dict[str, object]:
    detail: Dict[str, object] = {
        "code": error.code,
        "message": error.public_message,
        "retryable": error.retryable,
    }
    if error.provider_trace_id:
        detail["provider_trace_id"] = error.provider_trace_id
    return detail


def image_failure_http_exception(error: ImageProviderServiceError) -> HTTPException:
    status = 422 if error.category == "invalid_request" else 503
    return HTTPException(status_code=status, detail=public_image_failure(error))
