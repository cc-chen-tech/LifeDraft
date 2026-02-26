"""Gameplay router package.

This package provides the gameplay API endpoints:
- events: Event generation endpoints (SSE and sync)
- choices: Choice processing endpoints (SSE and sync)
- summary: Summary and ending endpoints
- sse_helpers: SSE streaming utilities
"""

from fastapi import APIRouter

from src.api.routers.gameplay.events import router as events_router
from src.api.routers.gameplay.choices import router as choices_router
from src.api.routers.gameplay.summary import router as summary_router

# Main router that combines all sub-routers
router = APIRouter()

# Include all sub-routers
router.include_router(events_router)
router.include_router(choices_router)
router.include_router(summary_router)

__all__ = ["router", "events_router", "choices_router", "summary_router"]
