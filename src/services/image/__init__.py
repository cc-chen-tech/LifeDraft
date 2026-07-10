"""Image service - 图像生成调度服务.

协调图像生成、存储和数据库记录。
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.ai.image_client import ImageClient
from src.ai.image_exceptions import ImageProviderError
from src.database.models import Image as ImageModel
from src.services.image_storage import ImageStorageService

logger = logging.getLogger(__name__)


class ImageServiceError(Exception):
    """图像服务错误"""


class ImageContentError(ImageServiceError):
    """图像内容审核错误"""

    def __init__(self, message: str, original_prompt: Optional[str] = None):
        super().__init__(message)
        self.original_prompt = original_prompt


class ImageProviderServiceError(ImageServiceError):
    """Safe provider failure preserved across the service boundary."""

    def __init__(self, provider_error: ImageProviderError) -> None:
        super().__init__(provider_error.public_message)
        self.code = provider_error.code
        self.category = provider_error.category
        self.retryable = provider_error.retryable
        self.public_message = provider_error.public_message
        self.provider_trace_id = provider_error.provider_trace_id

    @classmethod
    def from_provider(cls, error: ImageProviderError) -> "ImageProviderServiceError":
        return cls(error)


class ImageService:
    """图像生成调度服务

    整合各个子服务，提供统一的图像生成接口。
    """

    def __init__(
        self,
        db: Session,
        image_client: Optional[ImageClient] = None,
        storage_service: Optional[ImageStorageService] = None,
    ):
        """
        初始化图像服务

        Args:
            db: 数据库会话
            image_client: 图像生成客户端
            storage_service: 存储服务
        """
        self.db = db
        self.image_client = image_client or ImageClient()
        self.storage_service = storage_service or ImageStorageService()

    # ==================== 查询方法 ====================

    def get_image(self, image_id: int) -> Optional[ImageModel]:
        """获取图片记录"""
        return self.db.query(ImageModel).filter(ImageModel.image_id == image_id).first()

    def get_active_image(
        self,
        game_id: int,
        image_type: str,
        entity_name: str,
    ) -> Optional[ImageModel]:
        """
        获取活跃的图片记录

        Args:
            game_id: 游戏ID
            image_type: 图片类型
            entity_name: 实体名称

        Returns:
            活跃的Image模型，如果不存在返回None
        """
        return (
            self.db.query(ImageModel)
            .filter(
                ImageModel.game_id == game_id,
                ImageModel.image_type == image_type,
                ImageModel.entity_name == entity_name,
                ImageModel.is_active.is_(True),
            )
            .order_by(ImageModel.version.desc())
            .first()
        )

    def get_all_images_for_game(
        self,
        game_id: int,
        image_type: Optional[str] = None,
    ) -> List[ImageModel]:
        """
        获取游戏的所有图片

        Args:
            game_id: 游戏ID
            image_type: 可选的类型过滤

        Returns:
            图片列表
        """
        query = self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.is_active.is_(True),
        )

        if image_type:
            query = query.filter(ImageModel.image_type == image_type)

        return query.all()

    def get_image_url(self, image_model: ImageModel) -> str:
        """获取图片访问URL"""
        return self.storage_service.get_image_url(
            str(image_model.storage_path),  # type: ignore[arg-type]
            str(image_model.storage_type) if image_model.storage_type else None,  # type: ignore[arg-type]
        )

    def get_image_data(self, image_model: ImageModel) -> bytes:
        """获取图片二进制数据"""
        return self.storage_service.get_image_data(
            str(image_model.storage_path),  # type: ignore[arg-type]
            str(image_model.storage_type) if image_model.storage_type else None,  # type: ignore[arg-type]
        )

    # ==================== 辅助方法 ====================

    def _extract_description_from_prompt(self, prompt: str) -> str:
        """从prompt中提取描述"""
        if "人物描述：" in prompt:
            start = prompt.find("人物描述：") + 5
            end = prompt.find("。", start)
            if end > start:
                return prompt[start:end]
        return prompt

    def _extract_era_from_metadata(self, metadata: Optional[Dict[str, Any]]) -> str:
        """从元数据中提取时代"""
        if metadata and "era" in metadata:
            return metadata["era"]  # type: ignore[no-any-return]
        return "现代"

    def _build_description_from_settings(self, char_settings: Dict[str, Any]) -> str:
        """
        从角色设定构建人物描述

        Args:
            char_settings: 角色设定字典，包含 era, age, gender, world 等

        Returns:
            人物描述字符串
        """
        parts = []

        # 年龄
        age = char_settings.get("age")
        if age:
            if isinstance(age, dict):
                if age.get("age"):
                    parts.append(f"{age['age']}岁")
                elif age.get("age_range"):
                    parts.append(str(age["age_range"]))
            elif isinstance(age, (int, float)):
                parts.append(f"{age}岁")

        # 性别
        gender = char_settings.get("gender")
        if gender:
            if isinstance(gender, dict) and gender.get("gender"):
                parts.append(str(gender["gender"]))
            elif isinstance(gender, str):
                parts.append(gender)

        # 世界观
        world = char_settings.get("world")
        if world and isinstance(world, dict):
            if world.get("cultural_context"):
                parts.append(str(world["cultural_context"]))
            if world.get("special_features"):
                parts.append(str(world["special_features"]))

        return "，".join(parts) if parts else "一个普通人"

    def _extract_era_from_settings(self, char_settings: Dict[str, Any]) -> Optional[str]:
        """
        从角色设定中提取时代名称（用于图片生成）

        Args:
            char_settings: 角色设定字典

        Returns:
            简短的时代名称，如果不存在返回 None

        Note:
            图片生成需要简短的时代描述，不能使用完整的 era_description。
        """
        era = char_settings.get("era")
        if era:
            if isinstance(era, dict):
                era_name = era.get("era_name")
                if era_name and era_name.strip():
                    return era_name.strip()  # type: ignore[no-any-return]

                era_desc = era.get("era_description")
                if era_desc and era_desc.strip():
                    desc = era_desc.strip()
                    for sep in ["。", "，", ",", "."]:
                        if sep in desc:
                            desc = desc.split(sep)[0]
                            break
                    if len(desc) > 30:
                        desc = desc[:30]
                    return desc  # type: ignore[no-any-return]

                return None
            elif isinstance(era, str):
                if len(era) > 30:
                    return era[:30]
                return era
        return None

    def _get_current_week_from_db(self, game_id: int) -> int:
        """
        从数据库获取游戏当前的周数

        Args:
            game_id: 游戏ID

        Returns:
            当前周数，默认返回 0
        """
        from src.database.models import Game, GameState

        try:
            game_state = (
                self.db.query(GameState)
                .filter(GameState.game_id == game_id)
                .order_by(GameState.state_id.desc())
                .first()
            )

            if game_state and game_state.state_json:
                week = game_state.state_json.get("week")
                if week is not None:
                    return week  # type: ignore[no-any-return]

            game = self.db.query(Game).filter(Game.game_id == game_id).first()
            if game and game.initial_state:
                week = game.initial_state.get("week")
                if week is not None:
                    return week  # type: ignore[no-any-return]
        except Exception as e:
            logger.warning(f"Failed to get current week from database: {e}")

        return 0

    def _build_char_info(
        self, character_settings: Dict[str, Any], player_name: str
    ) -> Dict[str, Any]:
        """
        构建角色信息字典

        Args:
            character_settings: 角色设定
            player_name: 玩家名称

        Returns:
            角色信息字典
        """
        char_info = {
            "name": player_name,
            "era": self._extract_era_from_settings(character_settings) or "现代",
        }

        gender = character_settings.get("gender")
        if gender:
            if isinstance(gender, dict):
                char_info["gender"] = gender.get("gender", "")
            elif isinstance(gender, str):
                char_info["gender"] = gender

        age = character_settings.get("age")
        if age:
            if isinstance(age, dict):
                char_info["age"] = age.get("age", "")
            elif isinstance(age, (int, float)):
                char_info["age"] = str(age)

        return char_info

    def _get_player_image_base64(self, game_id: int, player_image_id: Optional[int]) -> tuple:
        """
        获取玩家形象的 Base64 编码

        Args:
            game_id: 游戏ID
            player_image_id: 玩家形象图片ID

        Returns:
            (base64_url, image_id) 或 (None, None)
        """
        import base64

        player_image = None
        if player_image_id:
            player_image = (
                self.db.query(ImageModel)
                .filter(
                    ImageModel.image_id == player_image_id,
                    ImageModel.game_id == game_id,
                )
                .first()
            )
            if not player_image:
                logger.warning(
                    f"player_image_id={player_image_id} does not belong to game_id={game_id}"
                )

        if not player_image:
            player_image = (
                self.db.query(ImageModel)
                .filter(
                    ImageModel.game_id == game_id,
                    ImageModel.image_type == "character",
                    ImageModel.is_primary.is_(True),
                )
                .order_by(ImageModel.image_id.desc())
                .first()
            )
            if player_image:
                logger.info(f"Auto-selected primary player image: {player_image.image_id}")

        if player_image:
            try:
                image_data = self.get_image_data(player_image)
                ext = player_image.storage_path.rsplit(".", 1)[-1].lower()
                mime_type = "image/png" if ext == "png" else "image/jpeg"
                base64_data = base64.b64encode(image_data).decode("utf-8")
                return f"data:{mime_type};base64,{base64_data}", player_image.image_id
            except Exception as e:
                logger.warning(f"Failed to get player image: {e}")

        return None, None

    def _image_to_base64(self, image_model: ImageModel) -> Optional[str]:
        """
        将图片模型转换为 Base64 URL

        Args:
            image_model: 图片模型

        Returns:
            Base64 URL 或 None
        """
        import base64

        try:
            image_data = self.get_image_data(image_model)
            ext = image_model.storage_path.rsplit(".", 1)[-1].lower()
            mime_type = "image/png" if ext == "png" else "image/jpeg"
            base64_data = base64.b64encode(image_data).decode("utf-8")
            return f"data:{mime_type};base64,{base64_data}"
        except Exception as e:
            logger.warning(f"Failed to convert image to base64: {e}")
            return None
