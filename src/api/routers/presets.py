"""Presets router — CRUD for character presets."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user_optional, get_db
from src.api.schemas import CreatePresetRequest, MessageResponse, PresetInfo

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=PresetInfo, status_code=201)
async def create_preset(
    req: CreatePresetRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Save a character preset."""
    db = get_db()
    try:
        preset_id = db.save_character_preset(
            preset_name=req.preset_name,
            player_name=req.player_name,
            life_vision=req.life_vision,
            character_settings=req.character_settings,
            user_id=user_id,
        )
        return PresetInfo(
            preset_id=preset_id,
            preset_name=req.preset_name,
            player_name=req.player_name,
            life_vision=req.life_vision,
            character_settings=req.character_settings,
        )
    except Exception as e:
        logger.error(f"Failed to create preset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[PresetInfo])
async def list_presets(
    limit: int = 50,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """List character presets for the current user."""
    db = get_db()
    presets = db.list_character_presets(limit=limit, user_id=user_id)
    return [
        PresetInfo(
            preset_id=int(p.preset_id),  # type: ignore[arg-type]
            preset_name=str(p.preset_name),  # type: ignore[arg-type]
            player_name=str(p.player_name),  # type: ignore[arg-type]
            life_vision=str(p.life_vision) if p.life_vision else None,  # type: ignore[arg-type]
            character_settings=p.character_settings or {},  # type: ignore[arg-type]
            created_at=p.created_at.isoformat() if p.created_at else None,
        )
        for p in presets
    ]


@router.get("/{preset_id}", response_model=PresetInfo)
async def get_preset(
    preset_id: int,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Get a single character preset."""
    db = get_db()
    preset = db.load_character_preset(preset_id, user_id=user_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")
    return PresetInfo(
        preset_id=preset["preset_id"],
        preset_name=preset["preset_name"],
        player_name=preset["player_name"],
        life_vision=preset.get("life_vision"),
        character_settings=preset.get("character_settings", {}),
        created_at=preset.get("created_at"),
    )


@router.delete("/{preset_id}", response_model=MessageResponse)
async def delete_preset(
    preset_id: int,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Delete a character preset."""
    db = get_db()
    success = db.delete_character_preset(preset_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Preset not found")
    return MessageResponse(message="Preset deleted")
