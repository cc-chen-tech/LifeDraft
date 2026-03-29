"""Character preset repository for preset CRUD operations."""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import or_

from src.database.models import CharacterPreset, SessionLocal

logger = logging.getLogger(__name__)


class CharacterPresetRepository:
    """Repository for character preset CRUD operations."""

    def save_character_preset(
        self,
        preset_name: str,
        player_name: str,
        life_vision: str,
        character_settings: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> int:
        """
        Save a character preset.

        Args:
            preset_name: Name for the preset
            player_name: Player name
            life_vision: Life vision text
            character_settings: Character settings dictionary
            user_id: 用户ID（可选）

        Returns:
            Preset ID
        """
        db = SessionLocal()
        try:
            preset = CharacterPreset(
                preset_name=preset_name,
                player_name=player_name,
                life_vision=life_vision,
                character_settings=character_settings,
                user_id=user_id,
            )
            db.add(preset)
            db.commit()
            db.refresh(preset)
            return int(preset.preset_id)  # type: ignore[return-value]
        finally:
            db.close()

    def load_character_preset(
        self, preset_id: int, user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Load a character preset.

        Args:
            preset_id: Preset ID
            user_id: 用户ID，如果提供则验证所有权（允许公共预设）

        Returns:
            Preset dictionary or None
        """
        db = SessionLocal()
        try:
            query = db.query(CharacterPreset).filter(CharacterPreset.preset_id == preset_id)
            # 如果提供了 user_id，验证所有权（允许自己的和公共的）
            if user_id is not None:
                query = query.filter(
                    or_(
                        CharacterPreset.user_id == user_id,
                        CharacterPreset.user_id.is_(None),
                    )
                )

            preset = query.first()

            if preset:
                return {
                    "preset_id": preset.preset_id,
                    "preset_name": preset.preset_name,
                    "player_name": preset.player_name,
                    "life_vision": preset.life_vision,
                    "character_settings": preset.character_settings,
                    "created_at": (preset.created_at.isoformat() if preset.created_at else None),
                }
            return None
        finally:
            db.close()

    def list_character_presets(
        self, limit: int = 50, user_id: Optional[int] = None
    ) -> List[CharacterPreset]:
        """
        List character presets.

        Args:
            limit: Maximum number of presets to return
            user_id: 用户ID，如果提供则返回该用户的预设 + 公共预设

        Returns:
            List of presets
        """
        db = SessionLocal()
        try:
            query = db.query(CharacterPreset)
            if user_id is not None:
                # 登录用户：看到自己的预设 + 公共预设（user_id 为 NULL 的）
                query = query.filter(
                    or_(
                        CharacterPreset.user_id == user_id,
                        CharacterPreset.user_id.is_(None),
                    )
                )
            else:
                # 未登录用户：只能看到公共预设
                query = query.filter(CharacterPreset.user_id.is_(None))
            return query.order_by(CharacterPreset.updated_at.desc()).limit(limit).all()
        finally:
            db.close()

    def delete_character_preset(self, preset_id: int, user_id: Optional[int] = None) -> bool:
        """
        Delete a character preset.

        Args:
            preset_id: Preset ID
            user_id: 用户ID，如果提供则验证所有权

        Returns:
            True if deleted, False if not found or not authorized
        """
        db = SessionLocal()
        try:
            query = db.query(CharacterPreset).filter(CharacterPreset.preset_id == preset_id)
            # 如果提供了 user_id，验证所有权（但允许删除 user_id 为 NULL 的旧数据）
            if user_id is not None:
                query = query.filter(
                    or_(
                        CharacterPreset.user_id == user_id,
                        CharacterPreset.user_id.is_(None),  # Allow deleting orphaned presets
                    )
                )

            preset = query.first()

            if preset:
                db.delete(preset)
                db.commit()
                return True
            return False
        finally:
            db.close()
